import { NavLink, useLocation } from 'react-router-dom'
import {
  DashboardOutlined,
  ScanOutlined,
  FieldTimeOutlined,
  ControlOutlined,
  BarChartOutlined,
  BookOutlined,
  SettingOutlined,
} from '@ant-design/icons'

const menuItems = [
  { path: '/', icon: <DashboardOutlined />, label: '数据看板' },
  { path: '/detection', icon: <ScanOutlined />, label: 'AI病虫害识别' },
  { path: '/fields', icon: <FieldTimeOutlined />, label: '农事管理' },
  { path: '/drone', icon: <ControlOutlined />, label: '无人机作业' },
  { path: '/analysis', icon: <BarChartOutlined />, label: '数据分析' },
  { path: '/knowledge', icon: <BookOutlined />, label: '知识库' },
  { path: '/settings', icon: <SettingOutlined />, label: '系统设置' },
]

export default function Sidebar() {
  const location = useLocation()

  return (
    <aside className="w-64 bg-white border-r border-gray-200 fixed left-0 top-0 h-full z-20 flex flex-col">
      <div className="h-16 flex items-center px-6 border-b border-gray-200">
        <div className="w-8 h-8 bg-primary-600 rounded-lg flex items-center justify-center mr-3">
          <span className="text-white font-bold text-sm">智</span>
        </div>
        <div>
          <h1 className="text-base font-bold text-gray-900">智农慧眼</h1>
          <p className="text-xs text-gray-500">AI精准植保平台</p>
        </div>
      </div>
      <nav className="flex-1 py-4 px-3">
        {menuItems.map((item) => {
          const isActive = location.pathname === item.path
          return (
            <NavLink
              key={item.path}
              to={item.path}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-lg mb-1 transition-colors ${
                isActive
                  ? 'bg-primary-50 text-primary-700 font-medium'
                  : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
              }`}
            >
              <span className={isActive ? 'text-primary-600' : 'text-gray-400'}>
                {item.icon}
              </span>
              <span className="text-sm">{item.label}</span>
            </NavLink>
          )
        })}
      </nav>
      <div className="p-4 border-t border-gray-200">
        <div className="bg-primary-50 rounded-lg p-3">
          <p className="text-xs text-primary-700 font-medium mb-1">系统状态</p>
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
            <span className="text-xs text-gray-600">边缘设备在线</span>
          </div>
        </div>
      </div>
    </aside>
  )
}