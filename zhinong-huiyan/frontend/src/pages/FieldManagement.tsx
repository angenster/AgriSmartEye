import { useState } from 'react'
import { Card, Button, Tag, Timeline, Badge, Modal, Form, Input, Select, DatePicker } from 'antd'
import { PlusOutlined, EnvironmentOutlined } from '@ant-design/icons'
import type { Dayjs } from 'dayjs'

interface Field {
  id: string
  name: string
  crop: string
  area: number
  location: string
  status: '健康' | '轻度异常' | '中度异常' | '重度异常'
  lastCheck: string
  nextSpray: string
  history: OperationRecord[]
}

interface OperationRecord {
  time: string
  type: string
  content: string
  operator: string
}

const fields: Field[] = [
  {
    id: 'A-03',
    name: 'A区03号田',
    crop: '芒果',
    area: 15.6,
    location: '儋州市那大镇',
    status: '中度异常',
    lastCheck: '2024-06-01',
    nextSpray: '2024-06-03',
    history: [
      { time: '2024-06-01 09:30', type: 'AI巡检', content: '发现炭疽病中度感染', operator: '系统' },
      { time: '2024-05-28 14:00', type: '无人机施药', content: '喷洒杀菌剂，面积15.6亩', operator: '张师傅' },
      { time: '2024-05-25 08:00', type: '人工巡查', content: '叶片健康，无异常', operator: '李师傅' },
    ],
  },
  {
    id: 'B-07',
    name: 'B区07号田',
    crop: '荔枝',
    area: 12.3,
    location: '乐东县佛罗镇',
    status: '轻度异常',
    lastCheck: '2024-06-01',
    nextSpray: '2024-06-05',
    history: [
      { time: '2024-06-01 10:15', type: 'AI巡检', content: '发现霜疫霉病轻度感染', operator: '系统' },
      { time: '2024-05-30 09:00', type: '无人机施药', content: '喷洒保护性杀菌剂', operator: '王师傅' },
    ],
  },
  {
    id: 'C-12',
    name: 'C区12号田',
    crop: '槟榔',
    area: 28.5,
    location: '三亚市崖州区',
    status: '健康',
    lastCheck: '2024-05-31',
    nextSpray: '2024-06-10',
    history: [
      { time: '2024-05-31 16:00', type: 'AI巡检', content: '植株健康，无病虫害', operator: '系统' },
      { time: '2024-05-20 08:30', type: '无人机施药', content: '预防性喷洒', operator: '张师傅' },
    ],
  },
  {
    id: 'A-05',
    name: 'A区05号田',
    crop: '香蕉',
    area: 20.0,
    location: '儋州市那大镇',
    status: '重度异常',
    lastCheck: '2024-05-31',
    nextSpray: '2024-06-02',
    history: [
      { time: '2024-05-31 14:20', type: 'AI巡检', content: '发现枯萎病重度感染，需紧急处理', operator: '系统' },
      { time: '2024-05-25 10:00', type: '人工巡查', content: '部分叶片发黄', operator: '李师傅' },
    ],
  },
]

const statusColors = {
  '健康': 'green',
  '轻度异常': 'orange',
  '中度异常': 'red',
  '重度异常': 'red',
}

export default function FieldManagement() {
  const [selectedField, setSelectedField] = useState<Field | null>(null)
  const [modalVisible, setModalVisible] = useState(false)
  const [form] = Form.useForm()

  const handleAddOperation = (values: { type: string; content: string; date: Dayjs }) => {
    console.log('新增记录:', values)
    setModalVisible(false)
    form.resetFields()
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">农事管理</h2>
          <p className="text-gray-500 mt-1">数字化管理田块信息、作业记录与防治计划</p>
        </div>
        <Button type="primary" icon={<PlusOutlined />} className="bg-green-600 hover:bg-green-700">
          新增田块
        </Button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {fields.map((field) => (
          <Card
            key={field.id}
            className={`shadow-sm cursor-pointer transition-all hover:shadow-md ${selectedField?.id === field.id ? 'ring-2 ring-green-500' : ''}`}
            onClick={() => setSelectedField(field)}
          >
            <div className="flex items-start justify-between">
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <h3 className="text-lg font-semibold text-gray-900">{field.name}</h3>
                  <Tag color={statusColors[field.status]}>{field.status}</Tag>
                </div>
                <div className="flex items-center gap-4 text-sm text-gray-600">
                  <span className="flex items-center gap-1">
                    <EnvironmentOutlined />
                    {field.location}
                  </span>
                  <span>{field.area} 亩</span>
                  <Tag color="blue">{field.crop}</Tag>
                </div>
              </div>
              <Badge
                count={field.status === '重度异常' ? '紧急' : field.status === '中度异常' ? '注意' : undefined}
                style={{ backgroundColor: field.status === '重度异常' ? '#ef4444' : '#f59e0b' }}
              />
            </div>

            <div className="grid grid-cols-2 gap-4 mt-4 pt-4 border-t border-gray-100">
              <div>
                <p className="text-xs text-gray-500">最近检查</p>
                <p className="text-sm font-medium text-gray-900">{field.lastCheck}</p>
              </div>
              <div>
                <p className="text-xs text-gray-500">下次施药</p>
                <p className="text-sm font-medium text-gray-900">{field.nextSpray}</p>
              </div>
            </div>
          </Card>
        ))}
      </div>

      {selectedField && (
        <Card
          title={
            <div className="flex items-center justify-between">
              <span>{selectedField.name} - 作业记录</span>
              <Button type="primary" size="small" icon={<PlusOutlined />} onClick={() => setModalVisible(true)} className="bg-green-600 hover:bg-green-700">
                新增记录
              </Button>
            </div>
          }
          className="shadow-sm"
        >
          <Timeline
            items={selectedField.history.map((record) => ({
              color: record.type === 'AI巡检' ? 'green' : record.type === '无人机施药' ? 'blue' : 'gray',
              children: (
                <div className="ml-2">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-gray-900">{record.type}</span>
                    <span className="text-xs text-gray-500">{record.time}</span>
                  </div>
                  <p className="text-sm text-gray-600 mt-1">{record.content}</p>
                  <p className="text-xs text-gray-400 mt-1">操作人: {record.operator}</p>
                </div>
              ),
            }))}
          />
        </Card>
      )}

      <Modal
        title="新增农事记录"
        open={modalVisible}
        onOk={() => form.submit()}
        onCancel={() => setModalVisible(false)}
        okText="保存"
        cancelText="取消"
        okButtonProps={{ className: 'bg-green-600 hover:bg-green-700' }}
      >
        <Form form={form} layout="vertical" onFinish={handleAddOperation}>
          <Form.Item name="type" label="记录类型" rules={[{ required: true }]}>
            <Select placeholder="选择记录类型">
              <Select.Option value="AI巡检">AI巡检</Select.Option>
              <Select.Option value="无人机施药">无人机施药</Select.Option>
              <Select.Option value="人工巡查">人工巡查</Select.Option>
              <Select.Option value="施肥">施肥</Select.Option>
              <Select.Option value="灌溉">灌溉</Select.Option>
            </Select>
          </Form.Item>
          <Form.Item name="date" label="日期时间" rules={[{ required: true }]}>
            <DatePicker showTime className="w-full" />
          </Form.Item>
          <Form.Item name="content" label="记录内容" rules={[{ required: true }]}>
            <Input.TextArea rows={3} placeholder="请输入记录内容" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
