import { useEffect, useRef, useState } from 'react'
import { Card, Empty, Spin, Table, Tag, message } from 'antd'
import * as echarts from 'echarts'
import {
  fetchAnalysisSummary, fetchCostComparison, fetchDiseaseDistribution, fetchSprayRecords,
} from '../api/endpoints'
import { describeError } from '../api/client'
import type { AnalysisSummary, CostComparison, DiseaseDistribution, SprayRecord } from '../api/types'

const columns = [
  { title: '田块 ID', dataIndex: 'field_id', key: 'field_id' },
  { title: '无人机', dataIndex: 'drone_id', key: 'drone_id' },
  { title: '面积(亩)', dataIndex: 'area', key: 'area' },
  { title: '传统用药(L)', dataIndex: 'traditional_usage', key: 'traditional_usage' },
  { title: '实际用药(L)', dataIndex: 'actual_usage', key: 'actual_usage' },
  {
    title: '节省比例',
    dataIndex: 'saved_percentage',
    key: 'saved_percentage',
    render: (v: number) => <Tag color="green">{v.toFixed(1)}%</Tag>,
  },
  { title: '作业日期', dataIndex: 'date', key: 'date' },
]

export default function DataAnalysis() {
  const barRef = useRef<HTMLDivElement>(null)
  const pieRef = useRef<HTMLDivElement>(null)
  const [summary, setSummary] = useState<AnalysisSummary | null>(null)
  const [cost, setCost] = useState<CostComparison[]>([])
  const [records, setRecords] = useState<SprayRecord[]>([])
  const [distribution, setDistribution] = useState<DiseaseDistribution[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const [s, c, r, d] = await Promise.all([
          fetchAnalysisSummary(),
          fetchCostComparison(),
          fetchSprayRecords(50),
          fetchDiseaseDistribution(),
        ])
        if (cancelled) return
        setSummary(s); setCost(c); setRecords(r); setDistribution(d)
      } catch (e) {
        message.error(describeError(e))
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => { cancelled = true }
  }, [])

  useEffect(() => {
    if (!barRef.current) return
    const chart = echarts.init(barRef.current)
    chart.setOption({
      tooltip: { trigger: 'axis' },
      legend: { data: ['传统施药', '智农慧眼'], bottom: 0 },
      grid: { left: '3%', right: '4%', bottom: '15%', top: '10%', containLabel: true },
      xAxis: { type: 'category', data: cost.map((d) => d.month) },
      yAxis: { type: 'value', name: '用药量(L)' },
      series: [
        { name: '传统施药', type: 'bar', data: cost.map((d) => d.traditional), itemStyle: { color: '#9ca3af' } },
        { name: '智农慧眼', type: 'bar', data: cost.map((d) => d.smart), itemStyle: { color: '#16a34a' } },
      ],
    })
    const onResize = () => chart.resize()
    window.addEventListener('resize', onResize)
    return () => { window.removeEventListener('resize', onResize); chart.dispose() }
  }, [cost])

  useEffect(() => {
    if (!pieRef.current) return
    const chart = echarts.init(pieRef.current)
    const colors = ['#ef4444', '#f59e0b', '#eab308', '#84cc16', '#10b981', '#3b82f6']
    chart.setOption({
      tooltip: { trigger: 'item' },
      legend: { bottom: 0, left: 'center', icon: 'circle', itemWidth: 10, itemHeight: 10 },
      series: [{
        type: 'pie', radius: ['35%', '55%'], center: ['50%', '45%'],
        itemStyle: { borderRadius: 10, borderColor: '#fff', borderWidth: 2 },
        label: { show: false },
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
    { title: '累计识别', value: summary?.total_detections ?? 0, unit: '次' },
    { title: '施药面积', value: summary?.total_sprayed_area ?? 0, unit: '亩' },
    { title: '节约农药', value: summary?.total_medicine_saved ?? 0, unit: 'L' },
    { title: '平均置信度', value: `${((summary?.avg_confidence ?? 0) * 100).toFixed(1)}%`, unit: '' },
  ]

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-900">数据分析</h2>
        <p className="text-gray-500 mt-1">基于真实识别与施药记录的成本与效果分析</p>
      </div>

      <Spin spinning={loading}>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {cards.map((c) => (
            <div key={c.title} className="card">
              <p className="stat-label">{c.title}</p>
              <p className="stat-value mt-2">
                {c.value}<span className="text-sm text-gray-400 ml-1">{c.unit}</span>
              </p>
            </div>
          ))}
        </div>
      </Spin>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card title="施药量对比" className="lg:col-span-2">
          {cost.some((d) => d.traditional > 0 || d.smart > 0) ? (
            <div ref={barRef} style={{ height: 320 }} />
          ) : (
            <Empty description="暂无施药记录" />
          )}
        </Card>
        <Card title="病虫害类型分布">
          <div ref={pieRef} style={{ height: 320 }} />
        </Card>
      </div>

      <Card title="施药记录">
        <Table
          rowKey="id"
          size="small"
          dataSource={records}
          columns={columns}
          pagination={{ pageSize: 8 }}
          scroll={{ x: 760 }}
          locale={{ emptyText: <Empty description="暂无施药记录" /> }}
        />
      </Card>
    </div>
  )
}
