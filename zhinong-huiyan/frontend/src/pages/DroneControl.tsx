import { useCallback, useEffect, useState } from 'react'
import { Alert, Badge, Button, Card, Empty, Progress, Spin, Tag, message } from 'antd'
import { PauseCircleOutlined, PlayCircleOutlined, StopOutlined, ReloadOutlined } from '@ant-design/icons'
import { fetchDrones, sendDroneCommand } from '../api/endpoints'
import { describeError } from '../api/client'
import type { DroneInfo } from '../api/types'

const statusMeta: Record<string, { text: string; color: string }> = {
  standby: { text: '待命', color: 'default' },
  flying: { text: '作业中', color: 'processing' },
  returning: { text: '返航中', color: 'warning' },
}

export default function DroneControl() {
  const [drones, setDrones] = useState<DroneInfo[]>([])
  const [loading, setLoading] = useState(false)
  const [busy, setBusy] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      setDrones(await fetchDrones())
    } catch (e) {
      message.error(describeError(e))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const command = async (droneId: string, cmd: 'start' | 'pause' | 'return') => {
    setBusy(droneId)
    try {
      const res = await sendDroneCommand(droneId, cmd)
      message.success(res.message ?? '指令已发送')
      await load()
    } catch (e) {
      message.error(describeError(e))
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">无人机作业</h2>
          <p className="text-gray-500 mt-1">作业调度与状态监控</p>
        </div>
        <Button icon={<ReloadOutlined />} onClick={load} loading={loading}>刷新</Button>
      </div>

      <Alert
        type="info"
        showIcon
        message="模拟控制面"
        description="本系统不连接真实飞控。此处的指令只更新数据库中的作业状态，不会产生任何实际飞行或施药动作。"
      />

      <Spin spinning={loading}>
        {drones.length === 0 ? (
          <Card><Empty description="暂无无人机设备" /></Card>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {drones.map((d) => {
              const meta = statusMeta[d.status] ?? { text: d.status, color: 'default' }
              return (
                <Card
                  key={d.drone_id}
                  title={
                    <div className="flex items-center gap-2">
                      <span>{d.name}</span>
                      <span className="text-xs text-gray-400">{d.drone_id}</span>
                      <Tag color={meta.color}>{meta.text}</Tag>
                    </div>
                  }
                  extra={<Badge status="processing" text={`信号 ${d.signal}%`} />}
                >
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <div className="text-sm text-gray-600 mb-1">电量</div>
                      <Progress
                        percent={Math.round(d.battery)}
                        strokeColor={d.battery < 25 ? '#ef4444' : '#16a34a'}
                        size="small"
                      />
                    </div>
                    <div>
                      <div className="text-sm text-gray-600 mb-1">作业进度</div>
                      <Progress percent={Math.round(d.mission_progress)} size="small" />
                    </div>
                    <div className="text-sm text-gray-600">
                      高度 <span className="text-gray-900 font-medium">{d.altitude} m</span>
                    </div>
                    <div className="text-sm text-gray-600">
                      速度 <span className="text-gray-900 font-medium">{d.speed} m/s</span>
                    </div>
                    <div className="text-sm text-gray-600">
                      喷雾率 <span className="text-gray-900 font-medium">{d.spray_rate} L/min</span>
                    </div>
                    <div className="text-sm text-gray-600">
                      机温 <span className="text-gray-900 font-medium">{d.temperature} °C</span>
                    </div>
                  </div>

                  <div className="flex gap-2 mt-4">
                    <Button
                      type="primary"
                      icon={<PlayCircleOutlined />}
                      loading={busy === d.drone_id}
                      onClick={() => command(d.drone_id, 'start')}
                      disabled={d.status === 'flying'}
                      className="bg-green-600 hover:bg-green-700"
                    >
                      开始作业
                    </Button>
                    <Button
                      icon={<PauseCircleOutlined />}
                      loading={busy === d.drone_id}
                      onClick={() => command(d.drone_id, 'pause')}
                      disabled={d.status !== 'flying'}
                    >
                      暂停
                    </Button>
                    <Button
                      danger
                      icon={<StopOutlined />}
                      loading={busy === d.drone_id}
                      onClick={() => command(d.drone_id, 'return')}
                    >
                      返航
                    </Button>
                  </div>
                </Card>
              )
            })}
          </div>
        )}
      </Spin>
    </div>
  )
}
