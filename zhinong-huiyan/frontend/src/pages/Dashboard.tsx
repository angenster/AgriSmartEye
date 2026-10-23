import { useEffect, useRef, useState } from 'react'
import * as echarts from 'echarts'
import { Alert, Empty, Spin, Tag, message } from 'antd'
import {
  fetchAnalysisSummary, fetchDetectionHistory, fetchDetectionStats,
  fetchDiseaseDistribution, fetchQueueStats,
} from '../api/endpoints'
import { describeError } from '../api/client'
import type { AnalysisSummary, DetectionRecord, DetectionStats, DiseaseDistribution, QueueStats } from '../api/types'

const severityTag: Record<string, string> = { 轻度: 'green', 中度: 'orange', 重度: 'red' }

export default function Dashboard() {
  const lineRef = useRef<HTMLDivElement>(null)
  const pieRef = useRef<HTMLDivElement>(null)
  const [summary, setSummary] = useState<AnalysisSummary | null>(null)
  const [stats, setStats] = useState<DetectionStats | null>(null)
  const [queue, setQueue] = useState<QueueStats | null>(null)
  const [distribution, setDistribution] = useState<DiseaseDistribution[]>([])
  const [recent, setRecent] = useState<DetectionRecord[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const [s, d, dist, hist, q] = await Promise.all([
          fetchAnalysisSummary(),
          fetchDetectionStats(),
          fetchDiseaseDistribution(),
          fetchDetectionHistory(8),
          fetchQueueStats(),
        ])
        if (cancelled) return
        setSummary(s)
        setStats(d)
        setDistribution(dist)
        setRecent(hist)
        setQueue(q)
      } catch (e) {
        message.error(describeError(e))
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => { cancelled = true }
  }, [])

  // 月度趋势：真实数据来自 detection_records 按月聚合
  useEffect(() => {
    if (!lineRef.current || !summary) return
    const chart = echarts.init(lineRef.current)
    const months = summary.monthly_stats.map((m) => m.month.slice(5) + '月')
    chart.setOption({
      tooltip: { trigger: 'axis' },
      legend: { data: ['识别次数', '施药面积(亩)'], bottom: 0 },
      grid: { left: '3%', right: '4%', bottom: '12%', top: '8%', containLabel: true },
      xAxis: { type: 'category', data: months },
      yAxis: [
        { type: 'value', name: '次数' },
        { type: 'value', name: '亩' },
      ],
      series: [
        {
          name: '识别次数', type: 'line', smooth: true,
          data: summary.monthly_stats.map((m) => m.detections),
          areaStyle: { color: 'rgba(22, 163, 74, 0.1)' },
          itemStyle: { color: '#16a34a' },
        },
        {
          name: '施药面积(亩)', type: 'line', smooth: true, yAxisIndex: 1,
          data: summary.monthly_stats.map((m) => m.sprayed_area),
          itemStyle: { color: '#3b82f6' },
        },
      ],
    })
    const onResize = () => chart.resize()
    window.addEventListener('resize', onResize)
    return () => { window.removeEventListener('resize', onResize); chart.dispose() }
  }, [summary])

  useEffect(() => {
    if (!pieRef.current) return
    const chart = echarts.init(pieRef.current)
    const colors = ['#ef4444', '#f59e0b', '#eab308', '#84cc16', '#10b981', '#3b82f6', '#8b5cf6']
    chart.setOption({
      tooltip: { trigger: 'item' },
      legend: {
        orient: 'horizontal', bottom: 0, left: 'center',
        icon: 'circle', itemWidth: 10, itemHeight: 10, textStyle: { fontSize: 12 },
      },
      series: [{
        name: '病虫害分布', type: 'pie', radius: ['35%', '55%'],
        center: ['50%', '45%'], avoidLabelOverlap: false,
        itemStyle: { borderRadius: 10, borderColor: '#fff', borderWidth: 2 },
        label: { show: false },
        emphasis: { label: { show: true, fontSize: 14, fontWeight: 'bold' } },
        data: distribution.length
          ? distribution.map((d, i) => ({ ...d, itemStyle: { color: colors[i % colors.length] } }))
          : [{ value: 1, name: '暂无数据', itemStyle: { color: '#e5e7eb' } }],
      }],
    })
    const onResize = () => chart.resize()
    window.addEventListener('resize', onResize)
    return () => { window.removeEventListener('resize', onResize); chart.dispose() }
  }, [distribution])

  const cards = [
    { title: '累计识别次数', value: summary?.total_detections ?? 0, hint: `今日 ${stats?.today_count ?? 0} 次`, color: 'bg-blue-50 text-blue-600' },
    { title: '平均置信度', value: `${((stats?.avg_confidence ?? 0) * 100).toFixed(1)}%`, hint: `模型 ${stats?.model_version ?? '—'}`, color: 'bg-green-50 text-green-600' },
    { title: '管理田块', value: summary?.total_fields ?? 0, hint: `施药 ${summary?.total_sprayed_area ?? 0} 亩`, color: 'bg-purple-50 text-purple-600' },
    { title: '待复核样本', value: queue?.counts.pending ?? 0, hint: `已确认 ${queue?.counts.confirmed ?? 0}`, color: 'bg-amber-50 text-amber-600' },
  ]

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-900">数据看板</h2>
        <p className="text-gray-500 mt-1">实时监控热带作物病虫害防治全局态势</p>
      </div>

      {stats?.is_demo && (
        <Alert
          type="warning"
          showIcon
          message="模型处于 DEMO 模式"
          description="当前权重未训练，识别结果仅用于验证链路，不具备业务参考价值。"
        />
      )}

      <Spin spinning={loading}>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {cards.map((c) => (
            <div key={c.title} className="card">
              <div className="flex items-start justify-between">
                <div>
                  <p className="stat-label">{c.title}</p>
                  <p className="stat-value mt-2">{c.value}</p>
                  <p className="text-sm mt-2 text-gray-500">{c.hint}</p>
                </div>
                <div className={`w-12 h-12 rounded-xl ${c.color}`} />
              </div>
            </div>
          ))}
        </div>
      </Spin>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="card lg:col-span-2">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">近半年识别与施药趋势</h3>
          <div ref={lineRef} style={{ height: 320 }} />
        </div>
        <div className="card">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">病虫害类型分布</h3>
          <div ref={pieRef} style={{ height: 320 }} />
        </div>
      </div>

      <div className="card">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">最近识别记录</h3>
        {recent.length === 0 ? (
          <Empty description="暂无识别记录，去「AI病虫害识别」页上传一张图" />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200">
                  {['时间', '作物', '病虫害', '置信度', '严重程度', '模型'].map((h) => (
                    <th key={h} className="text-left py-3 px-4 text-gray-600 font-medium">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {recent.map((row) => (
                  <tr key={row.id} className="border-b border-gray-100 hover:bg-gray-50">
                    <td className="py-3 px-4 text-gray-700">
                      {new Date(row.created_at).toLocaleString('zh-CN')}
                    </td>
                    <td className="py-3 px-4">
                      <span className="px-2 py-1 bg-primary-50 text-primary-700 rounded text-xs">
                        {row.crop_type ?? '—'}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-gray-700">{row.disease_name ?? '—'}</td>
                    <td className="py-3 px-4 text-gray-700">
                      {((row.confidence ?? 0) * 100).toFixed(1)}%
                    </td>
                    <td className="py-3 px-4">
                      <Tag color={severityTag[row.severity ?? ''] ?? 'default'}>
                        {row.severity ?? '—'}
                      </Tag>
                    </td>
                    <td className="py-3 px-4 text-gray-500 text-xs">{row.model_version}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
