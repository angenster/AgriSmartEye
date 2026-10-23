import { useCallback, useEffect, useState } from 'react'
import {
  Alert, Button, Card, Descriptions, Empty, Progress, Segmented, Spin,
  Table, Tag, Timeline, Upload, message,
} from 'antd'
import { CameraOutlined, EyeOutlined, FileImageOutlined } from '@ant-design/icons'
import type { UploadFile } from 'antd/es/upload/interface'
import { detectUpload, diagnoseStream, fetchDetectionHistory, fetchDetectionStats } from '../api/endpoints'
import { describeError } from '../api/client'
import type { AgentStep, DetectionRecord, DetectionStats, DiagnoseResult, Evidence } from '../api/types'

type Mode = 'quick' | 'agent'

const severityColors: Record<string, string> = {
  轻度: 'green',
  中度: 'orange',
  重度: 'red',
}

function toImageUrl(path: string) {
  return path.startsWith('/') ? path : `/${path}`
}

function StepTimeline({ steps }: { steps: AgentStep[] }) {
  return (
    <Timeline
      className="mt-2"
      items={steps.map((s) => {
        const payload = (s.result ?? s.tool_result?.data ?? s.tool_result?.error) as unknown
        return {
          color: s.ok === false ? 'red' : 'green',
          children: (
            <div>
              <div className="flex items-center gap-2 flex-wrap">
                <Tag color={s.ok === false ? 'red' : 'blue'}>{s.tool_name}</Tag>
                <span className="text-sm text-gray-700">{s.thought}</span>
              </div>
              <pre className="mt-1 text-xs text-gray-500 bg-gray-50 rounded p-2 overflow-auto max-h-40">
                {JSON.stringify(payload, null, 2)}
              </pre>
            </div>
          ),
        }
      })}
    />
  )
}

function ReportView({ result }: { result: DiagnoseResult }) {
  const r = result.report

  return (
    <div className="space-y-3">
      <Alert
        type={r.needs_human ? 'warning' : 'success'}
        showIcon
        message={r.needs_human ? '需要人工复核' : '自动诊断完成'}
        description={r.human_review_reason || undefined}
      />

      <Descriptions column={{ xs: 1, md: 2 }} size="small" bordered>
        <Descriptions.Item label="作物">{r.crop.name ?? '—'}</Descriptions.Item>
        <Descriptions.Item label="病害">
          {r.disease.name ?? '—'}{' '}
          <span className="text-gray-500">
            ({r.disease.source} {(r.disease.confidence ?? 0).toFixed(3)})
          </span>
        </Descriptions.Item>
        <Descriptions.Item label="严重度">
          <Tag color={severityColors[r.severity.level] ?? 'default'}>{r.severity.level}</Tag>
        </Descriptions.Item>
        <Descriptions.Item label="证据核对">
          {result.evidence_valid ? <Tag color="green">通过</Tag> : <Tag color="red">未通过</Tag>}
        </Descriptions.Item>
        <Descriptions.Item label="成本" span={2}>
          VLM 调用 {r.cost.vlm_calls} 次 · LLM tokens {r.cost.llm_tokens} · 总耗时{' '}
          {r.cost.latency_ms ?? 0} ms
        </Descriptions.Item>
      </Descriptions>

      {r.disease.candidates.length > 0 && (
        <div>
          <div className="text-sm font-medium text-gray-700 mb-1">候选类别</div>
          {r.disease.candidates.map((c) => (
            <div key={c.name} className="flex items-center gap-2 mb-1">
              <span className="text-xs w-40 truncate">{c.name}</span>
              <Progress percent={Math.round(c.confidence * 100)} size="small" className="flex-1" />
            </div>
          ))}
        </div>
      )}

      <div>
        <div className="text-sm font-medium text-gray-700 mb-1">证据（{r.evidence.length}）</div>
        {r.evidence.map((e: Evidence, i) => (
          <div key={i} className="text-xs bg-gray-50 rounded p-2 mb-1">
            <Tag>{e.type}</Tag>
            <span className="text-gray-500">{e.ref}</span>
            {e.title && <span className="ml-2">{e.title}</span>}
            {e.quote && <div className="text-gray-600 mt-1">{e.quote}</div>}
          </div>
        ))}
      </div>

      <div>
        <div className="text-sm font-medium text-green-800 mb-1">防治建议</div>
        {r.treatment.steps.length > 0 ? (
          <ul className="text-sm text-green-700 list-disc pl-5 space-y-1">
            {r.treatment.steps.map((s, i) => <li key={i}>{s}</li>)}
          </ul>
        ) : (
          <p className="text-sm text-gray-500">无可用防治措施</p>
        )}
        {r.treatment.medicines.length > 0 && (
          <div>
            <div className="text-sm font-medium text-gray-700 mb-1 mt-2">
              登记农药（{r.treatment.medicines.length}）
            </div>
            {r.treatment.medicines.map((m, i) => (
              <div key={i} className="text-xs bg-gray-50 rounded p-2 mb-1">
                <span className="font-medium">{m.name}</span>
                <Tag color={m.verified ? 'green' : 'orange'} className="ml-2">
                  {m.verified ? '已校审' : '未校审'}
                </Tag>
                <div className="text-gray-600 mt-1">
                  {m.dosage ? `剂量：${m.dosage}` : '剂量：需人工核对后提供'}
                  {m.safe_interval_days != null && ` ｜ 安全间隔期：${m.safe_interval_days} 天`}
                </div>
              </div>
            ))}
          </div>
        )}
        {r.treatment.note && (
          <p className="text-xs text-orange-600 mt-2">{r.treatment.note}</p>
        )}
      </div>

      <div>
        <div className="text-sm font-medium text-gray-700 mb-1">Agent 思考过程（{result.steps.length} 步）</div>
        <StepTimeline steps={result.steps} />
      </div>

      <p className="text-xs text-gray-400 border-t pt-2">{r.disclaimer}</p>
    </div>
  )
}

export default function PestDetection() {
  const [fileList, setFileList] = useState<UploadFile[]>([])
  const [imageUrl, setImageUrl] = useState('')
  const [mode, setMode] = useState<Mode>('quick')
  const [analyzing, setAnalyzing] = useState(false)
  const [quickResult, setQuickResult] = useState<DetectionRecord | null>(null)
  const [agentResult, setAgentResult] = useState<DiagnoseResult | null>(null)
  const [liveSteps, setLiveSteps] = useState<AgentStep[]>([])
  const [history, setHistory] = useState<DetectionRecord[]>([])
  const [stats, setStats] = useState<DetectionStats | null>(null)

  const load = useCallback(async () => {
    try {
      const [h, s] = await Promise.all([fetchDetectionHistory(20), fetchDetectionStats()])
      setHistory(h)
      setStats(s)
    } catch (e) {
      message.error(describeError(e))
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const handleUpload = ({ fileList }: { fileList: UploadFile[] }) => {
    setFileList(fileList)
    setQuickResult(null)
    setAgentResult(null)
    setLiveSteps([])
    if (fileList.length > 0 && fileList[0].originFileObj) {
      setImageUrl(URL.createObjectURL(fileList[0].originFileObj as Blob))
    } else {
      setImageUrl('')
    }
  }

  const startAnalysis = async () => {
    const file = fileList[0]?.originFileObj as File | undefined
    if (!file) return
    setAnalyzing(true)
    setQuickResult(null)
    setAgentResult(null)
    setLiveSteps([])
    try {
      if (mode === 'quick') {
        const res = await detectUpload(file)
        if (res.data.length === 0) {
          message.warning(res.message || '没有达到置信度阈值的结果')
        } else {
          setQuickResult(res.data[0])
          message.success(res.message)
        }
      } else {
        // 流式诊断：每完成一步就追加到时间线，最终报告到达后再整体替换
        const res = await diagnoseStream(file, undefined, {
          onStep: (step) => setLiveSteps((prev) => [...prev, step]),
          onError: (msg) => message.error(msg),
        })
        if (res) {
          setAgentResult(res)
          message.success(`Agent 诊断完成：${res.status}（${res.steps_used} 步）`)
        }
      }
      await load()
    } catch (e) {
      message.error(describeError(e))
    } finally {
      setAnalyzing(false)
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-900">AI 病虫害识别</h2>
        <p className="text-gray-500 mt-1">
          轻量化 CNN 快筛，或由诊断 Agent 自主决定是否升级多模态模型、查证知识库。
          当前不提供化学用药剂量（登记数据尚未校核），仅给出诊断与非化学防治建议。
        </p>
      </div>

      {stats?.is_demo && (
        <Alert
          type="warning"
          showIcon
          message="当前为 DEMO 未训练模型"
          description={`模型版本 ${stats.model_version}：ImageNet 骨干 + 随机分类头，链路真实但预测结果无业务意义。`}
        />
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-1 space-y-4">
          <Card title="图像上传" className="shadow-sm">
            <Segmented
              block
              value={mode}
              onChange={(v) => setMode(v as Mode)}
              options={[
                { label: '快速识别', value: 'quick' },
                { label: 'Agent 诊断', value: 'agent' },
              ]}
              className="mb-4"
            />
            <Upload
              listType="picture-card"
              fileList={fileList}
              onChange={handleUpload}
              beforeUpload={() => false}
              maxCount={1}
              className="w-full"
            >
              {fileList.length === 0 && (
                <div className="text-center py-8">
                  <FileImageOutlined className="text-3xl text-gray-400" />
                  <p className="mt-2 text-gray-500">点击或拖拽上传作物图像</p>
                  <p className="text-xs text-gray-400 mt-1">支持 JPG、PNG 格式</p>
                </div>
              )}
            </Upload>

            <div className="flex gap-2 mt-4">
              <Button
                type="primary"
                icon={<EyeOutlined />}
                onClick={startAnalysis}
                loading={analyzing}
                disabled={fileList.length === 0}
                block
                className="bg-green-600 hover:bg-green-700"
              >
                {analyzing ? '处理中...' : mode === 'quick' ? '开始识别' : '运行 Agent'}
              </Button>
              <Button icon={<CameraOutlined />} disabled>
                实时拍照
              </Button>
            </div>
          </Card>

          <Card title="识别统计" className="shadow-sm">
            <div className="space-y-3">
              <div className="flex justify-between">
                <span className="text-gray-600">累计识别次数</span>
                <span className="font-semibold">{stats?.total_detections ?? 0}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">今日识别</span>
                <span className="font-semibold">{stats?.today_count ?? 0}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">平均置信度</span>
                <span className="font-semibold text-green-600">
                  {stats ? `${(stats.avg_confidence * 100).toFixed(1)}%` : '—'}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">模型版本</span>
                <span className="font-semibold text-xs">{stats?.model_version ?? '—'}</span>
              </div>
            </div>
          </Card>
        </div>

        <div className="lg:col-span-1">
          <Card title="识别图像" className="shadow-sm h-full">
            {imageUrl ? (
              <div className="relative">
                <img
                  src={imageUrl}
                  alt="作物图像"
                  className="w-full rounded-lg"
                  style={{ maxHeight: 400, objectFit: 'contain' }}
                />
              </div>
            ) : (
              <div className="h-80 bg-gray-50 rounded-lg flex items-center justify-center border-2 border-dashed border-gray-200">
                <div className="text-center">
                  <EyeOutlined className="text-4xl text-gray-300" />
                  <p className="mt-2 text-gray-400">上传图像后将在此显示</p>
                </div>
              </div>
            )}
          </Card>
        </div>

        <div className="lg:col-span-1">
          <Card title={mode === 'agent' ? '诊断报告' : '识别结果'} className="shadow-sm h-full">
            <Spin spinning={analyzing}>
              {mode === 'quick' ? (
                quickResult ? (
                  <div className="space-y-3">
                    <div className="flex items-start justify-between">
                      <div>
                        <h4 className="font-semibold text-gray-900">{quickResult.disease_name}</h4>
                        <p className="text-sm text-gray-500">{quickResult.crop_type}</p>
                      </div>
                      <Tag color={severityColors[quickResult.severity ?? ''] ?? 'default'}>
                        {quickResult.severity ?? '—'}
                      </Tag>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-sm text-gray-600">置信度</span>
                      <Progress
                        percent={Math.round((quickResult.confidence ?? 0) * 100)}
                        size="small"
                        strokeColor={(quickResult.confidence ?? 0) > 0.85 ? '#16a34a' : '#f59e0b'}
                        className="flex-1"
                      />
                    </div>
                    <Descriptions column={1} size="small">
                      <Descriptions.Item label="推理耗时">
                        {quickResult.inference_time?.toFixed(1)} ms
                      </Descriptions.Item>
                      <Descriptions.Item label="模型版本">
                        {quickResult.model_version}
                      </Descriptions.Item>
                      <Descriptions.Item label="图像">
                        <a href={toImageUrl(quickResult.image_path)} target="_blank" rel="noreferrer">
                          查看
                        </a>
                      </Descriptions.Item>
                    </Descriptions>
                    <Alert
                      type="info"
                      showIcon
                      message="本次为快速识别"
                      description="不会查证知识库，也不会给出防治建议。需要完整报告请切换到 Agent 诊断。"
                    />
                  </div>
                ) : (
                  <Empty description="识别结果将显示在这里" />
                )
              ) : agentResult ? (
                <ReportView result={agentResult} />
              ) : mode === 'agent' && liveSteps.length > 0 ? (
                <div>
                  <div className="text-sm font-medium text-gray-700 mb-2">
                    Agent 实时思考（{liveSteps.length} 步）
                  </div>
                  <StepTimeline steps={liveSteps} />
                </div>
              ) : (
                <Empty description="Agent 诊断完成后在此显示报告与思考过程" />
              )}
            </Spin>
          </Card>
        </div>
      </div>

      <Card title="识别历史" className="shadow-sm">
        <Table
          rowKey="id"
          size="small"
          dataSource={history}
          pagination={{ pageSize: 8 }}
          scroll={{ x: 820 }}
          columns={[
            {
              title: '时间',
              dataIndex: 'created_at',
              render: (v: string) => new Date(v).toLocaleString('zh-CN'),
            },
            { title: '作物', dataIndex: 'crop_type' },
            { title: '病害', dataIndex: 'disease_name' },
            {
              title: '置信度',
              dataIndex: 'confidence',
              render: (v: number) => `${(v * 100).toFixed(1)}%`,
            },
            {
              title: '严重度',
              dataIndex: 'severity',
              render: (v: string) => <Tag color={severityColors[v] ?? 'default'}>{v}</Tag>,
            },
            { title: '耗时(ms)', dataIndex: 'inference_time' },
            { title: '模型', dataIndex: 'model_version' },
          ]}
        />
      </Card>
    </div>
  )
}
