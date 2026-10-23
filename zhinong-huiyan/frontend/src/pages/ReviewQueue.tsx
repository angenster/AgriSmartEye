import { useCallback, useEffect, useState } from 'react'
import {
  Alert, Button, Card, Col, Empty, Image, Modal, Row, Segmented,
  Select, Space, Spin, Statistic, Tag, Tooltip, message,
} from 'antd'
import { CheckOutlined, CloseOutlined, EditOutlined, ReloadOutlined } from '@ant-design/icons'
import {
  confirmSample, fetchLabels, fetchQueue, fetchQueueStats,
} from '../api/endpoints'
import { describeError } from '../api/client'
import type { LabelOptions, QueueStats, SampleItem } from '../api/types'

const REASON_LABEL: Record<string, { text: string; color: string }> = {
  cnn_vlm_disagree: { text: 'CNN/VLM 分歧', color: 'red' },
  low_conf: { text: 'CNN 低置信', color: 'orange' },
  vlm_low_conf: { text: 'VLM 低置信', color: 'gold' },
  manual: { text: '人工标记', color: 'blue' },
}

const STATUS_LABEL: Record<string, { text: string; color: string }> = {
  pending: { text: '待复核', color: 'processing' },
  confirmed: { text: '已确认', color: 'success' },
  rejected: { text: '已剔除', color: 'default' },
}

function imageUrl(path: string) {
  // 后端把 uploads 挂成静态目录；vite 已代理 /uploads
  return path.startsWith('/') ? path : `/${path}`
}

export default function ReviewQueue() {
  const [items, setItems] = useState<SampleItem[]>([])
  const [stats, setStats] = useState<QueueStats | null>(null)
  const [labels, setLabels] = useState<LabelOptions | null>(null)
  const [status, setStatus] = useState('pending')
  const [loading, setLoading] = useState(false)
  const [busyId, setBusyId] = useState<number | null>(null)
  const [correcting, setCorrecting] = useState<SampleItem | null>(null)
  const [correctLabel, setCorrectLabel] = useState<string>()

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [queue, s] = await Promise.all([fetchQueue(status), fetchQueueStats()])
      setItems(queue)
      setStats(s)
    } catch (e) {
      message.error(describeError(e))
    } finally {
      setLoading(false)
    }
  }, [status])

  useEffect(() => {
    load()
  }, [load])

  useEffect(() => {
    fetchLabels().then(setLabels).catch(() => undefined)
  }, [])

  const submit = async (
    item: SampleItem,
    action: 'adopt' | 'correct' | 'reject',
    finalLabel?: string,
  ) => {
    setBusyId(item.sample_id)
    try {
      const res = await confirmSample(item.sample_id, action, finalLabel)
      message.success(
        action === 'reject'
          ? `已剔除样本 #${item.sample_id}`
          : `已确认 #${item.sample_id} → ${res.final_label}（+${res.points} 积分）`,
      )
      setCorrecting(null)
      setCorrectLabel(undefined)
      await load()
    } catch (e) {
      message.error(describeError(e))
    } finally {
      setBusyId(null)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">数据飞轮 · 复核队列</h2>
          <p className="text-gray-500 mt-1">
            模型「拿不准」的样本会自动入队，确认后的标签是增量微调的唯一数据来源
          </p>
        </div>
        <Button icon={<ReloadOutlined />} onClick={load} loading={loading}>
          刷新
        </Button>
      </div>

      {stats && (
        <Row gutter={16}>
          <Col span={4}>
            <Card size="small">
              <Statistic title="待复核" value={stats.counts.pending ?? 0} />
            </Card>
          </Col>
          <Col span={4}>
            <Card size="small">
              <Statistic title="已确认" value={stats.counts.confirmed ?? 0} />
            </Card>
          </Col>
          <Col span={4}>
            <Card size="small">
              <Statistic title="已剔除" value={stats.counts.rejected ?? 0} />
            </Card>
          </Col>
          <Col span={4}>
            <Card size="small">
              <Tooltip title="已确认样本中被人工修正的比例。越高说明模型越需要这批数据">
                <Statistic
                  title="人工修正率"
                  value={stats.corrected_ratio == null ? '—' : `${(stats.corrected_ratio * 100).toFixed(0)}%`}
                />
              </Tooltip>
            </Card>
          </Col>
          <Col span={4}>
            <Card size="small">
              <Statistic title="可用训练标签" value={stats.training_ready_labels} />
            </Card>
          </Col>
          <Col span={4}>
            <Card size="small">
              <Statistic title="累计积分" value={stats.total_points} />
            </Card>
          </Col>
        </Row>
      )}

      <Segmented
        value={status}
        onChange={(v) => setStatus(v as string)}
        options={[
          { label: '待复核', value: 'pending' },
          { label: '已确认', value: 'confirmed' },
          { label: '已剔除', value: 'rejected' },
          { label: '全部', value: 'all' },
        ]}
      />

      <Spin spinning={loading}>
        {items.length === 0 ? (
          <Card>
            <Empty description={status === 'pending' ? '暂无待复核样本' : '暂无记录'} />
          </Card>
        ) : (
          <Row gutter={[16, 16]}>
            {items.map((item) => {
              const conf = item.cnn_conf ?? 0
              const statusMeta = STATUS_LABEL[item.status] ?? { text: item.status, color: 'default' }
              return (
                <Col key={item.sample_id} xs={24} lg={12} xxl={8}>
                  <Card
                    size="small"
                    title={<span className="text-sm">样本 #{item.sample_id}</span>}
                    extra={<Tag color={statusMeta.color}>{statusMeta.text}</Tag>}
                  >
                    <div className="flex gap-3">
                      <Image
                        src={imageUrl(item.image_path)}
                        width={110}
                        height={110}
                        style={{ objectFit: 'cover', borderRadius: 8, flexShrink: 0 }}
                        fallback="data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxMTAiIGhlaWdodD0iMTEwIj48cmVjdCB3aWR0aD0iMTEwIiBoZWlnaHQ9IjExMCIgZmlsbD0iI2YzZjRmNiIvPjwvc3ZnPg=="
                      />
                      <div className="flex-1 min-w-0">
                        <Space wrap size={[4, 4]} className="mb-2">
                          {item.trigger_reason.map((r) => {
                            const meta = REASON_LABEL[r] ?? { text: r, color: 'default' }
                            return <Tag key={r} color={meta.color}>{meta.text}</Tag>
                          })}
                        </Space>

                        <div className="text-xs text-gray-500">CNN 预标注</div>
                        <div className="text-sm text-gray-900 truncate">
                          {item.cnn_top1 ?? '—'}{' '}
                          <span className={conf < 0.6 ? 'text-orange-600' : 'text-gray-500'}>
                            ({conf.toFixed(3)})
                          </span>
                        </div>

                        {item.vlm_pred ? (
                          <>
                            <div className="text-xs text-gray-500 mt-1">VLM 预标注</div>
                            <div className="text-sm text-gray-900 truncate">
                              {item.vlm_pred}{' '}
                              <span className="text-gray-500">
                                ({(item.vlm_conf ?? 0).toFixed(3)})
                              </span>
                            </div>
                          </>
                        ) : (
                          <div className="text-xs text-gray-400 mt-1">VLM 未升级或不可用</div>
                        )}

                        {item.confirmation && (
                          <div className="text-xs mt-2 text-green-700">
                            结论：{item.confirmation.final_label ?? '剔除'}（
                            {item.confirmation.confirm_source}）
                          </div>
                        )}
                      </div>
                    </div>

                    {item.status === 'pending' && (
                      <Space className="mt-3" wrap>
                        <Button
                          type="primary"
                          size="small"
                          icon={<CheckOutlined />}
                          loading={busyId === item.sample_id}
                          onClick={() => submit(item, 'adopt')}
                          className="bg-green-600 hover:bg-green-700"
                        >
                          采纳预标注
                        </Button>
                        <Button
                          size="small"
                          icon={<EditOutlined />}
                          onClick={() => {
                            setCorrecting(item)
                            setCorrectLabel(undefined)
                          }}
                        >
                          修正
                        </Button>
                        <Button
                          size="small"
                          danger
                          icon={<CloseOutlined />}
                          onClick={() => submit(item, 'reject')}
                        >
                          剔除
                        </Button>
                      </Space>
                    )}
                  </Card>
                </Col>
              )
            })}
          </Row>
        )}
      </Spin>

      <Modal
        title={`修正样本 #${correcting?.sample_id ?? ''}`}
        open={correcting !== null}
        onCancel={() => setCorrecting(null)}
        onOk={() => {
          if (!correctLabel) {
            message.warning('请选择标签')
            return
          }
          if (correcting) submit(correcting, 'correct', correctLabel)
        }}
        okText="提交"
        cancelText="取消"
        confirmLoading={busyId === correcting?.sample_id}
      >
        <Alert
          type="info"
          showIcon
          className="mb-3"
          message="标签必须落在已知的 42 类之内"
          description={
            labels
              ? `若确属 42 类之外的新病害，请选「${labels.unknown}」，它会作为未知类别进入下一轮分析。`
              : undefined
          }
        />
        <Select
          className="w-full"
          placeholder="选择正确的病虫害类别"
          value={correctLabel}
          onChange={setCorrectLabel}
          showSearch
          options={[
            ...(labels?.diseases ?? []).map((d) => ({ label: d, value: d })),
            ...(labels ? [{ label: `${labels.unknown}（新病害）`, value: labels.unknown }] : []),
          ]}
        />
      </Modal>
    </div>
  )
}
