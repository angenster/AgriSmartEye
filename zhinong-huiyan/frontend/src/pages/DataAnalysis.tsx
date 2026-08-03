import { useEffect, useRef } from 'react'
import { Card, Table, Tag } from 'antd'
import * as echarts from 'echarts'

const costData = [
  { month: '1月', traditional: 45000, smart: 32000, saved: 28.9 },
  { month: '2月', traditional: 42000, smart: 29000, saved: 31.0 },
  { month: '3月', traditional: 48000, smart: 31000, saved: 35.4 },
  { month: '4月', traditional: 52000, smart: 33000, saved: 36.5 },
  { month: '5月', traditional: 55000, smart: 35000, saved: 36.4 },
  { month: '6月', traditional: 50000, smart: 30000, saved: 40.0 },
]

const sprayRecords = [
  { id: 1, field: 'A-03', crop: '芒果', area: 15.6, traditional: 234, actual: 156, saved: 33.3, date: '2024-06-01' },
  { id: 2, field: 'B-07', crop: '荔枝', area: 12.3, traditional: 185, actual: 126, saved: 31.9, date: '2024-06-01' },
  { id: 3, field: 'C-12', crop: '槟榔', area: 28.5, traditional: 342, actual: 228, saved: 33.3, date: '2024-05-31' },
  { id: 4, field: 'A-05', crop: '香蕉', area: 20.0, traditional: 280, actual: 182, saved: 35.0, date: '2024-05-31' },
]

const columns = [
  { title: '田块编号', dataIndex: 'field', key: 'field' },
  { title: '作物', dataIndex: 'crop', key: 'crop' },
  { title: '面积(亩)', dataIndex: 'area', key: 'area' },
  { title: '传统用药(L)', dataIndex: 'traditional', key: 'traditional' },
  { title: '实际用药(L)', dataIndex: 'actual', key: 'actual' },
  {
    title: '节省比例',
    dataIndex: 'saved',
    key: 'saved',
    render: (val: number) => (
      <Tag color="green">{val.toFixed(1)}%</Tag>
    ),
  },
  { title: '作业日期', dataIndex: 'date', key: 'date' },
]

export default function DataAnalysis() {
  const barRef = useRef<HTMLDivElement>(null)
  const radarRef = useRef<HTMLDivElement>(null)
  const lineRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (barRef.current) {
      const chart = echarts.init(barRef.current)
      chart.setOption({
        tooltip: { trigger: 'axis' },
        legend: { data: ['传统施药', '智农慧眼'], bottom: 0 },
        grid: { left: '3%', right: '4%', bottom: '15%', top: '10%', containLabel: true },
        xAxis: { type: 'category', data: costData.map(d => d.month) },
        yAxis: { type: 'value', name: '用药量(L)' },
        series: [
          {
            name: '传统施药',
            type: 'bar',
            data: costData.map(d => d.traditional),
            itemStyle: { color: '#9ca3af' },
          },
          {
            name: '智农慧眼',
            type: 'bar',
            data: costData.map(d => d.smart),
            itemStyle: { color: '#16a34a' },
          },
        ],
      })
    }

    if (radarRef.current) {
      const chart = echarts.init(radarRef.current)
      chart.setOption({
        tooltip: {},
        legend: { data: ['传统方式', '智农慧眼'], bottom: 0 },
        radar: {
          indicator: [
            { name: '识别准确率', max: 100 },
            { name: '施药精准度', max: 100 },
            { name: '作业效率', max: 100 },
            { name: '成本节约', max: 100 },
            { name: '环保指数', max: 100 },
            { name: '操作便捷性', max: 100 },
          ],
          radius: '65%',
        },
        series: [{
          type: 'radar',
          data: [
            {
              value: [60, 40, 50, 30, 35, 45],
              name: '传统方式',
              areaStyle: { color: 'rgba(156, 163, 175, 0.3)' },
              itemStyle: { color: '#9ca3af' },
            },
            {
              value: [97, 92, 88, 85, 90, 82],
              name: '智农慧眼',
              areaStyle: { color: 'rgba(22, 163, 74, 0.3)' },
              itemStyle: { color: '#16a34a' },
            },
          ],
        }],
      })
    }

    if (lineRef.current) {
      const chart = echarts.init(lineRef.current)
      chart.setOption({
        tooltip: { trigger: 'axis' },
        legend: { data: ['节省农药(L)', '节约成本(元)'], bottom: 0 },
        grid: { left: '3%', right: '4%', bottom: '15%', top: '10%', containLabel: true },
        xAxis: { type: 'category', data: costData.map(d => d.month) },
        yAxis: [
          { type: 'value', name: '农药(L)', position: 'left' },
          { type: 'value', name: '成本(元)', position: 'right' },
        ],
        series: [
          {
            name: '节省农药(L)',
            type: 'bar',
            data: costData.map(d => d.traditional - d.smart),
            itemStyle: { color: '#22c55e' },
          },
          {
            name: '节约成本(元)',
            type: 'line',
            yAxisIndex: 1,
            data: costData.map(d => (d.traditional - d.smart) * 35),
            itemStyle: { color: '#f59e0b' },
            lineStyle: { width: 3 },
          },
        ],
      })
    }
  }, [])

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-900">数据分析</h2>
        <p className="text-gray-500 mt-1">防治效果量化分析，精准评估经济效益与环保价值</p>
      </div>

      {/* 核心指标 */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {[
          { label: '累计节药量', value: '2,456 L', change: '+35.2%', color: 'text-green-600' },
          { label: '累计节约成本', value: '¥85,960', change: '+40.1%', color: 'text-green-600' },
          { label: '平均识别准确率', value: '97.5%', change: '+2.3%', color: 'text-blue-600' },
          { label: '农药残留降低', value: '52.8%', change: '-12.5%', color: 'text-green-600' },
        ].map((item) => (
          <Card key={item.label} className="shadow-sm">
            <p className="text-sm text-gray-500">{item.label}</p>
            <p className="text-2xl font-bold text-gray-900 mt-1">{item.value}</p>
            <p className={`text-sm mt-1 ${item.color}`}>{item.change} 较去年同期</p>
          </Card>
        ))}
      </div>

      {/* 图表 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card title="施药量对比分析" className="shadow-sm">
          <div ref={barRef} style={{ height: '300px' }} />
        </Card>
        <Card title="综合效能雷达图" className="shadow-sm">
          <div ref={radarRef} style={{ height: '300px' }} />
        </Card>
      </div>

      <Card title="经济效益分析" className="shadow-sm">
        <div ref={lineRef} style={{ height: '300px' }} />
      </Card>

      {/* 详细记录 */}
      <Card title="施药作业详细记录" className="shadow-sm">
        <Table dataSource={sprayRecords} columns={columns} pagination={false} />
      </Card>
    </div>
  )
}
