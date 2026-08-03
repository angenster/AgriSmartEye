import { useNavigate } from 'react-router-dom'
import { BellOutlined, UserOutlined, CheckCircleOutlined, WarningOutlined, InfoOutlined } from '@ant-design/icons'
import { Badge, Avatar, Dropdown, Popover, List, message } from 'antd'

const notifications = [
  {
    id: 1,
    title: 'A-03号田发现中度炭疽病',
    desc: 'AI巡检识别到芒果炭疽病，置信度97.8%',
    time: '10分钟前',
    type: 'warning',
    read: false,
  },
  {
    id: 2,
    title: '无人机作业完成',
    desc: '智农一号已完成B-07号田施药，面积12.3亩',
    time: '35分钟前',
    type: 'success',
    read: false,
  },
  {
    id: 3,
    title: '系统升级提醒',
    desc: 'AI模型v1.1版本已发布，识别准确率提升至98.2%',
    time: '2小时前',
    type: 'info',
    read: false,
  },
  {
    id: 4,
    title: 'C-12号田轻度黄化病',
    desc: '槟榔植株检测到轻度黄化病，建议预防性施药',
    time: '3小时前',
    type: 'warning',
    read: true,
  },
  {
    id: 5,
    title: '施药效果评估报告',
    desc: '本周累计节省农药156L，节约成本¥5,460',
    time: '昨天',
    type: 'success',
    read: true,
  },
]

const typeIcon = {
  warning: <WarningOutlined className="text-orange-500" />,
  success: <CheckCircleOutlined className="text-green-500" />,
  info: <InfoOutlined className="text-blue-500" />,
}

export default function Navbar() {
  const navigate = useNavigate()

  const userMenuItems = [
    { key: 'profile', label: '个人中心' },
    { key: 'settings', label: '系统设置' },
    { key: 'logout', label: '退出登录' },
  ]

  const handleUserMenuClick = ({ key }: { key: string }) => {
    if (key === 'profile') {
      navigate('/profile')
    } else if (key === 'settings') {
      navigate('/settings')
    } else if (key === 'logout') {
      message.success('已成功退出登录')
      setTimeout(() => {
        window.location.reload()
      }, 1000)
    }
  }

  const unreadCount = notifications.filter(n => !n.read).length

  const notificationContent = (
    <div className="w-80">
      <div className="flex items-center justify-between mb-3">
        <span className="font-semibold text-gray-900">通知消息</span>
        <span className="text-xs text-gray-500">{unreadCount} 条未读</span>
      </div>
      <List
        dataSource={notifications}
        renderItem={(item) => (
          <List.Item className="cursor-pointer hover:bg-gray-50 px-2 rounded-lg transition-colors">
            <List.Item.Meta
              avatar={
                <div className="mt-1">
                  {typeIcon[item.type as keyof typeof typeIcon]}
                </div>
              }
              title={
                <div className="flex items-center gap-2">
                  <span className={`text-sm font-medium ${item.read ? 'text-gray-600' : 'text-gray-900'}`}>
                    {item.title}
                  </span>
                  {!item.read && <span className="w-2 h-2 bg-red-500 rounded-full" />}
                </div>
              }
              description={
                <div>
                  <p className="text-xs text-gray-500 line-clamp-1">{item.desc}</p>
                  <p className="text-xs text-gray-400 mt-1">{item.time}</p>
                </div>
              }
            />
          </List.Item>
        )}
      />
      <div className="text-center mt-2 pt-2 border-t border-gray-100">
        <span className="text-xs text-primary-600 cursor-pointer hover:underline">查看全部消息</span>
      </div>
    </div>
  )

  return (
    <header className="h-16 bg-white border-b border-gray-200 flex items-center justify-between px-6 sticky top-0 z-10">
      <div className="flex items-center gap-2">
        <span className="text-lg font-semibold text-gray-800">智农慧眼</span>
        <span className="text-xs bg-primary-100 text-primary-700 px-2 py-0.5 rounded-full">
          v1.0
        </span>
      </div>
      <div className="flex items-center gap-4">
        <Popover
          content={notificationContent}
          placement="bottomRight"
          trigger="click"
          arrow={false}
        >
          <Badge count={unreadCount} size="small">
            <BellOutlined className="text-xl text-gray-600 cursor-pointer hover:text-primary-600 transition-colors" />
          </Badge>
        </Popover>
        <Dropdown menu={{ items: userMenuItems, onClick: handleUserMenuClick }} placement="bottomRight">
          <div className="flex items-center gap-2 cursor-pointer">
            <Avatar icon={<UserOutlined />} className="bg-primary-600" />
            <span className="text-sm text-gray-700">管理员</span>
          </div>
        </Dropdown>
      </div>
    </header>
  )
}
