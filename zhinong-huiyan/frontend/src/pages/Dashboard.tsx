import { useEffect, useRef } from 'react'
import * as echarts from 'echarts'

const stats = [
  {
    title: '今日识别次数',
    value: '1,284',
    change: '+12.5%',
    icon: <ScanIcon />,
    color: 'bg-blue-50 text-blue-600',
  },
  {
    title: '病虫害预警',
    value: '23',
    change: '-5.2%',
    icon: <BugIcon />,
    color: 'bg-red-50 text-red-600',
  },
  {
    title: '节约农药(L)',
    value: '486',
    change: '+18.3%',
    icon: <MedicineIcon />,
    color: 'bg-green-50 text-green-600',
  },
  {
    title: '作业面积(亩)',
    value: '3,856',
    change: '+8.7%',
    icon: <AreaIcon />,
    color: 'bg-purple-50 text-purple-600',
  },
]

export default function Dashboard() {
  const chartRef = useRef<HTMLDivElement>(null)
  const pieRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (chartRef.current) {
      const chart = echarts.init(chartRef.current)
      chart.setOption({
        tooltip: { trigger: 'axis' },
        legend: { data: ['识别准确率', '施药节省率'], bottom: 0 },
        grid: { left: '3%', right: '4%', bottom: '10%', top: '10%', containLabel: true },
        xAxis: {
          type: 'category',
          data: ['1月', '2月', '3月', '4月', '5月', '6月', '7月', '8月', '9月', '10月', '11月', '12月'],
        },
        yAxis: { type: 'value', max: 100, axisLabel: { formatter: '{value}%' } },
        series: [
          {
            name: '识别准确率',
            type: 'line',
            smooth: true,
            data: [92, 93, 94, 95, 95.5, 96, 96.2, 96.5, 96.8, 97, 97.2, 97.5],
            areaStyle: { color: 'rgba(22, 163, 74, 0.1)' },
            itemStyle: { color: '#16a34a' },
          },
          {
            name: '施药节省率',
            type: 'line',
            smooth: true,
            data: [20, 22, 25, 28, 30, 32, 33, 34, 35, 35.5, 36, 36.5],
            areaStyle: { color: 'rgba(59, 130, 246, 0.1)' },
            itemStyle: { color: '#3b82f6' },
          },
        ],
      })
    }

    if (pieRef.current) {
      const chart = echarts.init(pieRef.current)
      chart.setOption({
        tooltip: { trigger: 'item' },
        legend: {
          orient: 'horizontal',
          bottom: 0,
          left: 'center',
          icon: 'circle',
          itemWidth: 10,
          itemHeight: 10,
          textStyle: { fontSize: 12 }
        },
        series: [
          {
            name: '病虫害分布',
            type: 'pie',
            radius: ['35%', '55%'],
            center: ['50%', '45%'],
            avoidLabelOverlap: false,
            itemStyle: { borderRadius: 10, borderColor: '#fff', borderWidth: 2 },
            label: { show: false },
            emphasis: { label: { show: true, fontSize: 14, fontWeight: 'bold' } },
            data: [
              { value: 35, name: '芒果炭疽病', itemStyle: { color: '#ef4444' } },
              { value: 25, name: '荔枝霜疫霉病', itemStyle: { color: '#f59e0b' } },
              { value: 20, name: '槟榔黄化病', itemStyle: { color: '#eab308' } },
              { value: 12, name: '香蕉枯萎病', itemStyle: { color: '#84cc16' } },
              { value: 8, name: '其他', itemStyle: { color: '#10b981' } },
            ],
          },
        ],
      })
    }
  }, [])

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-900">数据看板</h2>
        <p className="text-gray-500 mt-1">实时监控热带作物病虫害防治全局态势</p>
      </div>

      {/* 统计卡片 */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {stats.map((stat) => (
          <div key={stat.title} className="card">
            <div className="flex items-start justify-between">
              <div>
                <p className="stat-label">{stat.title}</p>
                <p className="stat-value mt-2">{stat.value}</p>
                <p className={`text-sm mt-2 ${stat.change.startsWith('+') ? 'text-green-600' : 'text-red-600'}`}>
                  {stat.change} 较上月
                </p>
              </div>
              <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${stat.color}`}>
                {stat.icon}
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* 图表区域 */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="card lg:col-span-2">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">年度识别准确率与施药节省趋势</h3>
          <div ref={chartRef} style={{ height: '320px' }} />
        </div>
        <div className="card">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">病虫害类型分布</h3>
          <div ref={pieRef} style={{ height: '320px' }} />
        </div>
      </div>

      {/* 最近预警 */}
      <div className="card">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">最近病虫害预警</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200">
                <th className="text-left py-3 px-4 text-gray-600 font-medium">时间</th>
                <th className="text-left py-3 px-4 text-gray-600 font-medium">田块</th>
                <th className="text-left py-3 px-4 text-gray-600 font-medium">作物</th>
                <th className="text-left py-3 px-4 text-gray-600 font-medium">病虫害类型</th>
                <th className="text-left py-3 px-4 text-gray-600 font-medium">严重程度</th>
                <th className="text-left py-3 px-4 text-gray-600 font-medium">状态</th>
              </tr>
            </thead>
            <tbody>
              {[
                { time: '2024-06-01 09:23', field: 'A-03号田', crop: '芒果', pest: '炭疽病', level: '重度', status: '已处理' },
                { time: '2024-06-01 08:45', field: 'B-07号田', crop: '荔枝', pest: '霜疫霉病', level: '中度', status: '处理中' },
                { time: '2024-05-31 16:30', field: 'C-12号田', crop: '槟榔', pest: '黄化病', level: '轻度', status: '已处理' },
                { time: '2024-05-31 14:12', field: 'A-05号田', crop: '香蕉', pest: '枯萎病', level: '重度', status: '待处理' },
                { time: '2024-05-30 11:08', field: 'B-02号田', crop: '芒果', pest: '介壳虫', level: '中度', status: '已处理' },
              ].map((row, i) => (
                <tr key={i} className="border-b border-gray-100 hover:bg-gray-50">
                  <td className="py-3 px-4 text-gray-700">{row.time}</td>
                  <td className="py-3 px-4 text-gray-700">{row.field}</td>
                  <td className="py-3 px-4">
                    <span className="px-2 py-1 bg-primary-50 text-primary-700 rounded text-xs">{row.crop}</span>
                  </td>
                  <td className="py-3 px-4 text-gray-700">{row.pest}</td>
                  <td className="py-3 px-4">
                    <span className={`px-2 py-1 rounded text-xs ${
                      row.level === '重度' ? 'bg-red-50 text-red-600' :
                      row.level === '中度' ? 'bg-yellow-50 text-yellow-600' :
                      'bg-green-50 text-green-600'
                    }`}>
                      {row.level}
                    </span>
                  </td>
                  <td className="py-3 px-4">
                    <span className={`px-2 py-1 rounded text-xs ${
                      row.status === '已处理' ? 'bg-green-50 text-green-600' :
                      row.status === '处理中' ? 'bg-blue-50 text-blue-600' :
                      'bg-red-50 text-red-600'
                    }`}>
                      {row.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

function ScanIcon() {
  return (
    <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
    </svg>
  )
}

function BugIcon() {
  return (
    <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4m15.364 6.364l-12.728-12.728m12.728 0L6.364 21.364" />
    </svg>
  )
}

function MedicineIcon() {
  return (
    <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" />
    </svg>
  )
}

function AreaIcon() {
  return (
    <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0121 18.382V7.618a1 1 0 00-.553-.894L15 7m0 13V7" />
    </svg>
  )
}