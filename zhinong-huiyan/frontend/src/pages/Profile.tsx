import { useEffect, useState } from 'react'
import { Avatar, Card, Descriptions, Empty, Tag, message } from 'antd'
import { UserOutlined } from '@ant-design/icons'
import { fetchAnalysisSummary, fetchDetectionHistory } from '../api/endpoints'
import { describeError } from '../api/client'
import { useAuth } from '../store/auth'
import type { AnalysisSummary, DetectionRecord } from '../api/types'

export default function Profile() {
  const { user, restore } = useAuth()
  const [summary, setSummary] = useState<AnalysisSummary | null>(null)
  const [recent, setRecent] = useState<DetectionRecord[]>([])

  useEffect(() => {
    if (!user) restore()
  }, [user, restore])

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const [s, h] = await Promise.all([fetchAnalysisSummary(), fetchDetectionHistory(6)])
        if (cancelled) return
        setSummary(s)
        setRecent(h)
      } catch (e) {
        message.error(describeError(e))
      }
    })()
    return () => { cancelled = true }
  }, [])

  const stats = [
    { title: '累计识别', value: summary?.total_detections ?? 0, suffix: '次' },
    { title: '管理田块', value: summary?.total_fields ?? 0, suffix: '块' },
    { title: '施药面积', value: summary?.total_sprayed_area ?? 0, suffix: '亩' },
    { title: '节约农药', value: summary?.total_medicine_saved ?? 0, suffix: 'L' },
  ]

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-900">个人中心</h2>
        <p className="text-gray-500 mt-1">账户信息与使用数据</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="space-y-4">
          <Card className="shadow-sm text-center">
            <Avatar size={96} icon={<UserOutlined />} className="bg-primary-600 text-4xl" />
            <h3 className="text-xl font-semibold mt-4 text-gray-900">
              {user?.full_name || user?.username || '未登录'}
            </h3>
            <Tag color="green" className="mt-2">
              {user?.role === 'admin' ? '管理员' : user?.role === 'operator' ? '操作员' : user?.role ?? '—'}
            </Tag>
            <p className="text-sm text-gray-500 mt-2">{user?.organization || '—'}</p>
            <p className="text-xs text-gray-400 mt-1">
              加入时间: {user?.created_at ? new Date(user.created_at).toLocaleDateString('zh-CN') : '—'}
            </p>
          </Card>

          <Card className="shadow-sm" title="使用统计">
            <div className="grid grid-cols-2 gap-4">
              {stats.map((stat) => (
                <div key={stat.title} className="text-center">
                  <p className="text-2xl font-bold text-primary-600">
                    {stat.value}
                    <span className="text-sm font-normal text-gray-500 ml-1">{stat.suffix}</span>
                  </p>
                  <p className="text-xs text-gray-500 mt-1">{stat.title}</p>
                </div>
              ))}
            </div>
          </Card>
        </div>

        <div className="lg:col-span-2 space-y-4">
          <Card className="shadow-sm" title="账户信息">
            <Descriptions column={{ xs: 1, md: 2 }} bordered>
              <Descriptions.Item label="姓名">{user?.full_name || '—'}</Descriptions.Item>
              <Descriptions.Item label="用户名">{user?.username || '—'}</Descriptions.Item>
              <Descriptions.Item label="邮箱">{user?.email || '—'}</Descriptions.Item>
              <Descriptions.Item label="角色">{user?.role || '—'}</Descriptions.Item>
              <Descriptions.Item label="所属组织" span={2}>
                {user?.organization || '—'}
              </Descriptions.Item>
              <Descriptions.Item label="账户状态">
                {user?.is_active ? <Tag color="green">正常</Tag> : <Tag color="red">停用</Tag>}
              </Descriptions.Item>
              <Descriptions.Item label="用户 ID">{user?.id ?? '—'}</Descriptions.Item>
            </Descriptions>
          </Card>

          <Card className="shadow-sm" title="最近识别记录">
            {recent.length === 0 ? (
              <Empty description="暂无记录" />
            ) : (
              <div className="space-y-3">
                {recent.map((item) => (
                  <div
                    key={item.id}
                    className="flex items-center justify-between py-2 border-b border-gray-100 last:border-0"
                  >
                    <div>
                      <p className="text-sm text-gray-900">
                        {item.crop_type ?? '未知作物'} · {item.disease_name ?? '未知病害'}
                      </p>
                      <p className="text-xs text-gray-400">
                        置信度 {((item.confidence ?? 0) * 100).toFixed(1)}% · {item.model_version}
                      </p>
                    </div>
                    <span className="text-xs text-gray-500">
                      {new Date(item.created_at).toLocaleString('zh-CN')}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>
      </div>
    </div>
  )
}
