import { useState, useEffect, useRef } from 'react'
import { Card, Button, Progress, Badge, Switch, Alert } from 'antd'
import {
  PlayCircleOutlined,
  PauseCircleOutlined,
  StopOutlined,
} from '@ant-design/icons'

interface DroneStatus {
  id: string
  name: string
  battery: number
  altitude: number
  speed: number
  sprayRate: number
  position: [number, number]
  status: 'standby' | 'flying' | 'spraying' | 'returning' | 'charging'
  signal: number
  temperature: number
}

const mockDrone: DroneStatus = {
  id: 'ZN-001',
  name: '智农一号',
  battery: 78,
  altitude: 12.5,
  speed: 4.2,
  sprayRate: 2.5,
  position: [109.5, 19.2],
  status: 'standby',
  signal: 95,
  temperature: 42,
}

const statusMap = {
  standby: { label: '待命', color: 'blue' },
  flying: { label: '飞行中', color: 'green' },
  spraying: { label: '施药中', color: 'orange' },
  returning: { label: '返航中', color: 'purple' },
  charging: { label: '充电中', color: 'cyan' },
}

export default function DroneControl() {
  const [drone, setDrone] = useState<DroneStatus>(mockDrone)
  const [missionProgress, setMissionProgress] = useState(0)
  const [isMissionActive, setIsMissionActive] = useState(false)
  const [variableSpray, setVariableSpray] = useState(true)
  const canvasRef = useRef<HTMLCanvasElement>(null)

  // 模拟无人机状态更新
  useEffect(() => {
    if (!isMissionActive) return
    const interval = setInterval(() => {
      setDrone((prev) => {
        const newBattery = Math.max(0, prev.battery - 0.5)
        return {
          ...prev,
          battery: newBattery,
          altitude: prev.status === 'flying' || prev.status === 'spraying' ? prev.altitude + (Math.random() - 0.5) * 0.5 : 0,
          speed: prev.status === 'flying' || prev.status === 'spraying' ? 4 + Math.random() * 2 : 0,
          sprayRate: prev.status === 'spraying' ? 2 + Math.random() * 1.5 : 0,
          status: newBattery < 20 ? 'returning' : prev.status,
        }
      })
      setMissionProgress((prev) => Math.min(100, prev + 1))
    }, 1000)
    return () => clearInterval(interval)
  }, [isMissionActive])

  const startMission = () => {
    setIsMissionActive(true)
    setDrone((prev) => ({ ...prev, status: 'flying' }))
    setTimeout(() => {
      setDrone((prev) => ({ ...prev, status: 'spraying' }))
    }, 3000)
  }

  const pauseMission = () => {
    setIsMissionActive(false)
    setDrone((prev) => ({ ...prev, status: 'standby' }))
  }

  const returnHome = () => {
    setIsMissionActive(false)
    setDrone((prev) => ({ ...prev, status: 'returning' }))
  }

  // 绘制航线图
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    canvas.width = canvas.offsetWidth * 2
    canvas.height = canvas.offsetHeight * 2
    ctx.scale(2, 2)

    // 绘制背景网格
    ctx.strokeStyle = '#e5e7eb'
    ctx.lineWidth = 0.5
    for (let i = 0; i < canvas.offsetWidth; i += 20) {
      ctx.beginPath()
      ctx.moveTo(i, 0)
      ctx.lineTo(i, canvas.offsetHeight)
      ctx.stroke()
    }
    for (let i = 0; i < canvas.offsetHeight; i += 20) {
      ctx.beginPath()
      ctx.moveTo(0, i)
      ctx.lineTo(canvas.offsetWidth, i)
      ctx.stroke()
    }

    // 绘制田块边界
    ctx.strokeStyle = '#16a34a'
    ctx.lineWidth = 2
    ctx.beginPath()
    ctx.rect(50, 50, 300, 200)
    ctx.stroke()

    // 绘制航线
    if (isMissionActive || missionProgress > 0) {
      ctx.strokeStyle = '#3b82f6'
      ctx.lineWidth = 2
      ctx.setLineDash([5, 5])
      ctx.beginPath()
      for (let i = 0; i < 10; i++) {
        const y = 60 + i * 18
        ctx.moveTo(60, y)
        ctx.lineTo(340, y)
      }
      ctx.stroke()
      ctx.setLineDash([])

      // 绘制无人机位置
      const progress = missionProgress / 100
      const droneX = 60 + progress * 280
      const droneY = 60 + Math.sin(progress * Math.PI * 4) * 80 + 80
      ctx.fillStyle = '#ef4444'
      ctx.beginPath()
      ctx.arc(droneX, droneY, 6, 0, Math.PI * 2)
      ctx.fill()
    }

    // 绘制喷洒热力图区域
    const gradient = ctx.createRadialGradient(150, 120, 10, 150, 120, 60)
    gradient.addColorStop(0, 'rgba(239, 68, 68, 0.4)')
    gradient.addColorStop(0.5, 'rgba(245, 158, 11, 0.3)')
    gradient.addColorStop(1, 'rgba(16, 185, 129, 0.1)')
    ctx.fillStyle = gradient
    ctx.fillRect(90, 60, 120, 120)

    // 图例
    ctx.fillStyle = '#ef4444'
    ctx.fillRect(360, 30, 12, 12)
    ctx.fillStyle = '#374151'
    ctx.font = '12px sans-serif'
    ctx.fillText('重病区', 380, 40)

    ctx.fillStyle = '#f59e0b'
    ctx.fillRect(360, 50, 12, 12)
    ctx.fillText('轻病区', 380, 60)

    ctx.fillStyle = '#10b981'
    ctx.fillRect(360, 70, 12, 12)
    ctx.fillText('健康区', 380, 80)
  }, [isMissionActive, missionProgress])

  const currentStatus = statusMap[drone.status]

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-900">无人机作业控制</h2>
        <p className="text-gray-500 mt-1">变量精准施药，根据病情图谱动态调节喷头流量</p>
      </div>

      {drone.battery < 20 && (
        <Alert
          message="低电量警告"
          description="无人机电量低于20%，建议立即返航充电"
          type="warning"
          showIcon
          closable
        />
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* 左侧：状态面板 */}
        <div className="space-y-4">
          <Card title="设备状态" className="shadow-sm">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-lg font-semibold">{drone.name}</h3>
                <p className="text-sm text-gray-500">{drone.id}</p>
              </div>
              <Badge status="processing" color={currentStatus.color} text={currentStatus.label} />
            </div>

            <div className="space-y-4">
              <div>
                <div className="flex justify-between text-sm mb-1">
                  <span className="text-gray-600">电量</span>
                  <span className={`font-medium ${drone.battery < 30 ? 'text-red-600' : 'text-gray-900'}`}>
                    {drone.battery.toFixed(0)}%
                  </span>
                </div>
                <Progress
                  percent={drone.battery}
                  status={drone.battery < 20 ? 'exception' : 'active'}
                  strokeColor={drone.battery > 50 ? '#16a34a' : drone.battery > 20 ? '#f59e0b' : '#ef4444'}
                  showInfo={false}
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="bg-gray-50 rounded-lg p-3">
                  <p className="text-xs text-gray-500">飞行高度</p>
                  <p className="text-lg font-semibold text-gray-900">{drone.altitude.toFixed(1)}m</p>
                </div>
                <div className="bg-gray-50 rounded-lg p-3">
                  <p className="text-xs text-gray-500">飞行速度</p>
                  <p className="text-lg font-semibold text-gray-900">{drone.speed.toFixed(1)}m/s</p>
                </div>
                <div className="bg-gray-50 rounded-lg p-3">
                  <p className="text-xs text-gray-500">喷洒速率</p>
                  <p className="text-lg font-semibold text-gray-900">{drone.sprayRate.toFixed(1)}L/min</p>
                </div>
                <div className="bg-gray-50 rounded-lg p-3">
                  <p className="text-xs text-gray-500">信号强度</p>
                  <p className="text-lg font-semibold text-gray-900">{drone.signal}%</p>
                </div>
              </div>

              <div className="bg-gray-50 rounded-lg p-3">
                <p className="text-xs text-gray-500">当前位置</p>
                <p className="text-sm text-gray-900 mt-1">
                  {drone.position[0].toFixed(4)}°E, {drone.position[1].toFixed(4)}°N
                </p>
              </div>
            </div>
          </Card>

          <Card title="任务控制" className="shadow-sm">
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-700">变量施药模式</span>
                <Switch checked={variableSpray} onChange={setVariableSpray} />
              </div>
              <p className="text-xs text-gray-500">
                开启后根据病情严重程度自动调节喷量：重病区多喷、轻病区少喷、健康区不喷
              </p>

              {variableSpray && (
                <div className="bg-primary-50 rounded-lg p-3 mt-2">
                  <p className="text-xs text-primary-700 font-medium mb-2">施药策略</p>
                  <div className="space-y-2">
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-red-600">● 重病区 (30%)</span>
                      <span className="font-medium">3.5 L/min</span>
                    </div>
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-yellow-600">● 轻病区 (45%)</span>
                      <span className="font-medium">2.0 L/min</span>
                    </div>
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-green-600">● 健康区 (25%)</span>
                      <span className="font-medium">0 L/min</span>
                    </div>
                  </div>
                </div>
              )}

              <div className="flex gap-2 mt-4">
                {!isMissionActive ? (
                  <Button type="primary" icon={<PlayCircleOutlined />} onClick={startMission} block className="bg-green-600 hover:bg-green-700">
                    开始作业
                  </Button>
                ) : (
                  <Button icon={<PauseCircleOutlined />} onClick={pauseMission} block>
                    暂停作业
                  </Button>
                )}
                <Button danger icon={<StopOutlined />} onClick={returnHome}>
                  紧急返航
                </Button>
              </div>
            </div>
          </Card>
        </div>

        {/* 中间：航线地图 */}
        <div className="lg:col-span-2">
          <Card title="作业航线与病情热力图" className="shadow-sm h-full">
            <div className="relative">
              <canvas
                ref={canvasRef}
                className="w-full bg-gray-50 rounded-lg border border-gray-200"
                style={{ height: '400px' }}
              />
              <div className="absolute top-2 right-2 bg-white/90 backdrop-blur rounded-lg p-2 text-xs shadow-sm">
                <div className="flex items-center gap-1 mb-1">
                  <div className="w-2 h-2 bg-red-500 rounded-full" />
                  <span>重病区</span>
                </div>
                <div className="flex items-center gap-1 mb-1">
                  <div className="w-2 h-2 bg-yellow-500 rounded-full" />
                  <span>轻病区</span>
                </div>
                <div className="flex items-center gap-1">
                  <div className="w-2 h-2 bg-green-500 rounded-full" />
                  <span>健康区</span>
                </div>
              </div>
            </div>

            {isMissionActive && (
              <div className="mt-4">
                <div className="flex justify-between text-sm mb-2">
                  <span className="text-gray-600">任务进度</span>
                  <span className="font-medium text-gray-900">{missionProgress.toFixed(0)}%</span>
                </div>
                <Progress percent={missionProgress} status="active" strokeColor="#16a34a" />
                <div className="flex justify-between text-xs text-gray-500 mt-2">
                  <span>已作业面积: {(missionProgress * 0.15).toFixed(1)} 亩</span>
                  <span>已用药量: {(missionProgress * 0.8).toFixed(1)} L</span>
                  <span>预计剩余: {((100 - missionProgress) * 0.5).toFixed(0)} 分钟</span>
                </div>
              </div>
            )}
          </Card>
        </div>
      </div>
    </div>
  )
}
