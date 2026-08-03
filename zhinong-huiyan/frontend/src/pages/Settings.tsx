import { Card, Form, Switch, Button, Select, Slider, message } from 'antd'
import { SaveOutlined, ReloadOutlined, CloudUploadOutlined } from '@ant-design/icons'

export default function Settings() {
  const [form] = Form.useForm()

  const handleSave = () => {
    message.success('设置已保存')
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-900">系统设置</h2>
        <p className="text-gray-500 mt-1">配置模型参数、通知偏好与系统集成选项</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* AI模型设置 */}
        <Card title="AI模型参数" className="shadow-sm">
          <Form layout="vertical" form={form} initialValues={{
            confidence: 85,
            nms: 0.5,
            maxDetections: 50,
            inputSize: 640,
            device: 'auto',
          }}>
            <Form.Item label="置信度阈值" name="confidence">
              <Slider min={50} max={99} marks={{ 50: '50%', 75: '75%', 99: '99%' }} />
            </Form.Item>

            <Form.Item label="NMS阈值" name="nms">
              <Slider min={0.1} max={0.9} step={0.1} marks={{ 0.1: '0.1', 0.5: '0.5', 0.9: '0.9' }} />
            </Form.Item>

            <Form.Item label="最大检测数量" name="maxDetections">
              <Slider min={10} max={200} step={10} />
            </Form.Item>

            <Form.Item label="输入图像尺寸" name="inputSize">
              <Select>
                <Select.Option value={320}>320 × 320（最快）</Select.Option>
                <Select.Option value={416}>416 × 416（平衡）</Select.Option>
                <Select.Option value={640}>640 × 640（推荐）</Select.Option>
                <Select.Option value={1280}>1280 × 1280（最精确）</Select.Option>
              </Select>
            </Form.Item>

            <Form.Item label="推理设备" name="device">
              <Select>
                <Select.Option value="auto">自动选择</Select.Option>
                <Select.Option value="cuda">GPU (CUDA)</Select.Option>
                <Select.Option value="cpu">CPU</Select.Option>
              </Select>
            </Form.Item>
          </Form>
        </Card>

        {/* 通知设置 */}
        <Card title="通知与预警" className="shadow-sm">
          <div className="space-y-4">
            {[
              { label: '病虫害预警通知', desc: '发现病虫害时立即推送', default: true },
              { label: '施药完成通知', desc: '无人机作业完成后推送', default: true },
              { label: '设备离线告警', desc: '边缘设备或无人机离线时推送', default: true },
              { label: '周报汇总', desc: '每周生成防治效果报告', default: false },
              { label: '低电量预警', desc: '无人机电量低于20%时推送', default: true },
            ].map((item) => (
              <div key={item.label} className="flex items-center justify-between py-2 border-b border-gray-100 last:border-0">
                <div>
                  <p className="text-sm font-medium text-gray-900">{item.label}</p>
                  <p className="text-xs text-gray-500">{item.desc}</p>
                </div>
                <Switch defaultChecked={item.default} />
              </div>
            ))}
          </div>
        </Card>

        {/* 无人机设置 */}
        <Card title="无人机参数" className="shadow-sm">
          <Form layout="vertical">
            <Form.Item label="默认飞行高度" name="altitude" initialValue={12}>
              <Slider min={5} max={30} marks={{ 5: '5m', 15: '15m', 30: '30m' }} />
            </Form.Item>

            <Form.Item label="默认飞行速度" name="speed" initialValue={5}>
              <Slider min={2} max={10} marks={{ 2: '2m/s', 5: '5m/s', 10: '10m/s' }} />
            </Form.Item>

            <Form.Item label="最低返航电量" name="returnBattery" initialValue={20}>
              <Slider min={10} max={50} marks={{ 10: '10%', 30: '30%', 50: '50%' }} />
            </Form.Item>

            <Form.Item label="变量施药模式" name="variableSpray" initialValue={true}>
              <Switch defaultChecked />
            </Form.Item>
          </Form>
        </Card>

        {/* 数据同步 */}
        <Card title="数据同步" className="shadow-sm">
          <div className="space-y-4">
            <div className="flex items-center justify-between py-2">
              <div>
                <p className="text-sm font-medium text-gray-900">云端自动同步</p>
                <p className="text-xs text-gray-500">边缘设备数据自动上传云端</p>
              </div>
              <Switch defaultChecked />
            </div>
            <div className="flex items-center justify-between py-2">
              <div>
                <p className="text-sm font-medium text-gray-900">离线缓存</p>
                <p className="text-xs text-gray-500">网络中断时本地缓存数据</p>
              </div>
              <Switch defaultChecked />
            </div>
            <div className="bg-gray-50 rounded-lg p-3">
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-600">上次同步时间</span>
                <span className="text-sm text-gray-900">2024-06-01 10:30:25</span>
              </div>
              <div className="flex items-center justify-between mt-2">
                <span className="text-sm text-gray-600">同步数据量</span>
                <span className="text-sm text-gray-900">2.3 GB</span>
              </div>
            </div>
            <Button icon={<CloudUploadOutlined />} block>
              立即同步
            </Button>
          </div>
        </Card>
      </div>

      <div className="flex justify-end gap-4">
        <Button icon={<ReloadOutlined />}>恢复默认</Button>
        <Button type="primary" icon={<SaveOutlined />} onClick={handleSave} className="bg-green-600 hover:bg-green-700">
          保存设置
        </Button>
      </div>
    </div>
  )
}
