import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import PestDetection from './pages/PestDetection'
import FieldManagement from './pages/FieldManagement'
import DroneControl from './pages/DroneControl'
import DataAnalysis from './pages/DataAnalysis'
import KnowledgeBase from './pages/KnowledgeBase'
import Settings from './pages/Settings'
import Profile from './pages/Profile'

function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="detection" element={<PestDetection />} />
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