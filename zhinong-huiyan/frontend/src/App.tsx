import { useEffect, type ReactElement } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import PestDetection from './pages/PestDetection'
import FieldManagement from './pages/FieldManagement'
import DroneControl from './pages/DroneControl'
import DataAnalysis from './pages/DataAnalysis'
import KnowledgeBase from './pages/KnowledgeBase'
import Settings from './pages/Settings'
import Profile from './pages/Profile'
import Login from './pages/Login'
import ReviewQueue from './pages/ReviewQueue'
import { useAuth } from './store/auth'

/** 未登录一律回登录页。后端所有业务接口都要 Bearer token，没有 token 进来只会满屏 401 */
function RequireAuth({ children }: { children: ReactElement }) {
  const token = useAuth((s) => s.token)
  if (!token) return <Navigate to="/login" replace />
  return children
}

function App() {
  const restore = useAuth((s) => s.restore)

  // 刷新页面后 token 还在 localStorage 但 user 丢了，这里补拉一次
  useEffect(() => {
    restore()
  }, [restore])

  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        path="/"
        element={
          <RequireAuth>
            <Layout />
          </RequireAuth>
        }
      >
        <Route index element={<Dashboard />} />
        <Route path="detection" element={<PestDetection />} />
        <Route path="review" element={<ReviewQueue />} />
        <Route path="fields" element={<FieldManagement />} />
        <Route path="drone" element={<DroneControl />} />
        <Route path="analysis" element={<DataAnalysis />} />
        <Route path="knowledge" element={<KnowledgeBase />} />
        <Route path="settings" element={<Settings />} />
        <Route path="profile" element={<Profile />} />
      </Route>
    </Routes>
  )
}

export default App
