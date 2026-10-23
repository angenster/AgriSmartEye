import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { BellOutlined, UserOutlined, CheckCircleOutlined, WarningOutlined, InfoOutlined } from '@ant-design/icons'
import { Badge, Avatar, Dropdown, Popover, List, Empty } from 'antd'
import { fetchDetectionHistory, fetchDetectionStats, fetchQueueStats } from '../api/endpoints'
import { useAuth } from '../store/auth'

interface Notice {
  id: string
  title: string
  desc: string
  time: string
  type: 'warning' | 'success' | 'info'
}

const typeIcon = {
  warning: <WarningOutlined className="text-orange-500" />,
  success: <CheckCircleOutlined className="text-green-500" />,
  info: <InfoOutlined className="text-blue-500" />,
}

function ago(iso: string): string {
  const mins = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 60000))
  if (mins < 1) return '刚刚'
  if (mins < 60) return `${mins} 分钟前`
  if (mins < 1440) return `${Math.round(mins / 60)} 小时前`
  return `${Math.round(mins / 1440)} 天前`
}

export default function Navbar() {
  const navigate = useNavigate()
  const { user, logout } = useAuth()
  const [notices, setNotices] = useState<Notice[]>([])

  // 通知全部由真实数据派生，不再使用写死的示例消息
  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const [queue, stats, history] = await Promise.all([
          fetchQueueStats(), fetchDetectionStats(), fetchDetectionHistory(4),
        ])
        if (cancelled) return
        const list: Notice[] = []
        const pending = queue.counts.pending ?? 0
        if (pending > 0) {
          list.push({
            id: 'queue',
            title: `有 ${pending} 条样本待复核`,
            desc: '模型低置信或 CNN/VLM 分歧的样本已进入复核队列',
            time: '实时',
            type: 'warning',
          })
        }
        if (stats.is_demo) {
          list.push({
            id: 'demo',
            title: '模型处于 DEMO 模式',
            desc: `当前版本 ${stats.model_version} 未训练，识别结果无业务参考价值`,
            time: '系统',
            type: 'info',
          })
        }
        for (const h of history) {
          list.push({
            id: `d${h.id}`,
            title: `${h.crop_type ?? '未知作物'}识别到${h.disease_name ?? '未知病害'}`,
            desc: `置信度 ${((h.confidence ?? 0) * 100).toFixed(1)}%，严重度 ${h.severity ?? '—'}`,
            time: ago(h.created_at),
            type: h.severity === '重度' ? 'warning' : 'success',
          })
        }
        setNotices(list)
      } catch {
        // 通知是辅助信息，失败不打扰用户
      }
    })()
    return () => { cancelled = true }
  }, [])

  const userMenuItems = [
    { key: 'profile', label: '个人中心' },
    { key: 'review', label: '复核队列' },
    { key: 'settings', label: '系统设置' },
    { type: 'divider' as const },
    { key: 'logout', label: '退出登录' },
  ]

  const handleUserMenuClick = ({ key }: { key: string }) => {
    if (key === 'profile') navigate('/profile')
    else if (key === 'review') navigate('/review')
    else if (key === 'settings') navigate('/settings')
    else if (key === 'logout') {
      logout()
      navigate('/login', { replace: true })
    }
  }

  const unreadCount = notices.length

  const notificationContent = (
    <div className="w-80">
      <div className="flex items-center justify-between mb-3">
        <span className="font-semibold text-gray-900">通知消息</span>
        <span className="text-xs text-gray-500">{unreadCount} 条</span>
      </div>
      {notices.length === 0 ? (
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无通知" />
      ) : (
        <List
          dataSource={notices}
          renderItem={(item) => (
            <List.Item className="px-2 rounded-lg">
              <List.Item.Meta
                avatar={<div className="mt-1">{typeIcon[item.type]}</div>}
                title={<span className="text-sm font-medium text-gray-900">{item.title}</span>}
                description={
                  <div>
                    <p className="text-xs text-gray-500">{item.desc}</p>
                    <p className="text-xs text-gray-400 mt-1">{item.time}</p>
                  </div>
                }
              />
            </List.Item>
          )}
        />
      )}
    </div>
  )

  return (
    <header className="h-16 bg-white border-b border-gray-200 flex items-center justify-between px-6 sticky top-0 z-10">
      <div className="flex items-center gap-2">
        <span className="text-lg font-semibold text-gray-800">智农慧眼</span>
        <span className="text-xs bg-primary-100 text-primary-700 px-2 py-0.5 rounded-full">v1.0</span>
      </div>
      <div className="flex items-center gap-4">
        <Popover content={notificationContent} placement="bottomRight" trigger="click" arrow={false}>
          <Badge count={unreadCount} size="small">
            <BellOutlined className="text-xl text-gray-600 cursor-pointer hover:text-primary-600 transition-colors" />
          </Badge>
        </Popover>
        <Dropdown menu={{ items: userMenuItems, onClick: handleUserMenuClick }} placement="bottomRight">
          <div className="flex items-center gap-2 cursor-pointer">
            <Avatar icon={<UserOutlined />} className="bg-primary-600" />
            <span className="text-sm text-gray-700">
              {user?.full_name || user?.username || '未登录'}
            </span>
          </div>
        </Dropdown>
      </div>
    </header>
  )
}
