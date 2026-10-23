import { useCallback, useEffect, useState } from 'react'
import {
  Button, Card, Empty, Form, Input, InputNumber, Modal, Spin, Table, Tag, message,
} from 'antd'
import { PlusOutlined, ReloadOutlined } from '@ant-design/icons'
import { createField, fetchFields } from '../api/endpoints'
import { describeError } from '../api/client'
import type { FieldInfo } from '../api/types'

const statusMeta: Record<string, { text: string; color: string }> = {
  healthy: { text: '健康', color: 'green' },
  mild: { text: '轻度', color: 'lime' },
  moderate: { text: '中度', color: 'orange' },
  severe: { text: '重度', color: 'red' },
}

export default function FieldManagement() {
  const [fields, setFields] = useState<FieldInfo[]>([])
  const [loading, setLoading] = useState(false)
  const [open, setOpen] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [form] = Form.useForm()

  const load = useCallback(async () => {
    setLoading(true)
    try {
      setFields(await fetchFields())
    } catch (e) {
      message.error(describeError(e))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const submit = async () => {
    try {
      const values = await form.validateFields()
      setSubmitting(true)
      await createField(values)
      message.success('田块已创建')
      setOpen(false)
      form.resetFields()
      await load()
    } catch (e) {
      if ((e as { errorFields?: unknown })?.errorFields) return // 表单校验失败，不弹错误
      message.error(describeError(e))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">农事管理</h2>
          <p className="text-gray-500 mt-1">管理田块与作物信息，诊断时可绑定田块获取上下文</p>
        </div>
        <div className="flex gap-2">
          <Button icon={<ReloadOutlined />} onClick={load} loading={loading}>刷新</Button>
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => setOpen(true)}
            className="bg-green-600 hover:bg-green-700"
          >
            新建田块
          </Button>
        </div>
      </div>

      <Card>
        <Spin spinning={loading}>
          <Table
            rowKey="id"
            dataSource={fields}
            locale={{ emptyText: <Empty description="还没有田块，先新建一个" /> }}
            pagination={{ pageSize: 10 }}
            scroll={{ x: 760 }}
            columns={[
              { title: 'ID', dataIndex: 'id', width: 70 },
              { title: '田块名称', dataIndex: 'name' },
              { title: '作物', dataIndex: 'crop_type' },
              { title: '面积(亩)', dataIndex: 'area', render: (v: number) => v?.toFixed(2) },
              { title: '位置', dataIndex: 'location', render: (v) => v || '—' },
              {
                title: '状态',
                dataIndex: 'status',
                render: (v: string) => {
                  const meta = statusMeta[v] ?? { text: v, color: 'default' }
                  return <Tag color={meta.color}>{meta.text}</Tag>
                },
              },
              {
                title: '创建时间',
                dataIndex: 'created_at',
                render: (v: string) => new Date(v).toLocaleString('zh-CN'),
              },
            ]}
          />
        </Spin>
      </Card>

      <Modal
        title="新建田块"
        open={open}
        onCancel={() => setOpen(false)}
        onOk={submit}
        confirmLoading={submitting}
        okText="创建"
        cancelText="取消"
      >
        <Form form={form} layout="vertical" requiredMark={false}>
          <Form.Item name="name" label="田块名称" rules={[{ required: true, message: '请输入名称' }]}>
            <Input placeholder="例如 A-03 号田" />
          </Form.Item>
          <Form.Item name="crop_type" label="作物" rules={[{ required: true, message: '请输入作物' }]}>
            <Input placeholder="例如 芒果" />
          </Form.Item>
          <Form.Item name="area" label="面积(亩)" rules={[{ required: true, message: '请输入面积' }]}>
            <InputNumber min={0.1} step={0.1} className="w-full" />
          </Form.Item>
          <Form.Item name="location" label="位置">
            <Input placeholder="例如 海南省儋州市" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
