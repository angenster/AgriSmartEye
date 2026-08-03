import { useState } from 'react'
import { Card, Avatar, Button, Form, Input, Tag, Descriptions } from 'antd'
import { UserOutlined, EditOutlined, SaveOutlined, CameraOutlined } from '@ant-design/icons'

export default function Profile() {
  const [editing, setEditing] = useState(false)
  const [form] = Form.useForm()

  const userInfo = {
    name: '管理员',
    username: 'admin',
    email: 'admin@zhinong.com',
    phone: '13800138000',
    organization: '海南智农慧眼科技有限公司',
    role: '系统管理员',
    joinDate: '2024-01-15',
    avatar: null,
  }

  const stats = [
    { title: '累计识别', value: 1284, suffix: '次' },
    { title: '管理田块', value: 8, suffix: '块' },
    { title: '施药作业', value: 156, suffix: '次' },
    { title: '节约农药', value: 486, suffix: 'L' },
  ]

  const handleSave = (values: any) => {
    console.log('保存用户信息:', values)
    setEditing(false)
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-900">个人中心</h2>
        <p className="text-gray-500 mt-1">管理您的账户信息和使用数据</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* 左侧：用户头像和基本信息 */}
        <div className="space-y-4">
          <Card className="shadow-sm text-center">
            <div className="relative inline-block">
              <Avatar
                size={96}
                icon={<UserOutlined />}
                className="bg-primary-600 text-4xl"
              />
              <div className="absolute bottom-0 right-0 w-8 h-8 bg-white rounded-full flex items-center justify-center shadow cursor-pointer hover:bg-gray-50">
                <CameraOutlined className="text-gray-600 text-sm" />
              </div>
            </div>
            <h3 className="text-xl font-semibold mt-4 text-gray-900">{userInfo.name}</h3>
            <Tag color="green" className="mt-2">{userInfo.role}</Tag>
            <p className="text-sm text-gray-500 mt-2">{userInfo.organization}</p>
            <p className="text-xs text-gray-400 mt-1">加入时间: {userInfo.joinDate}</p>
          </Card>

          <Card className="shadow-sm" title="使用统计">
            <div className="grid grid-cols-2 gap-4">
              {stats.map((stat) => (
                <div key={stat.title} className="text-center">
                  <p className="text-2xl font-bold text-primary-600">
                    {stat.value}
                    <span className="text-sm font-normal text-gray-500 ml-1">{stat.suffix}</span>
                  </p>
                  <p className="text-xs text-gray-500 mt-1">{stat.title}</p>
                </div>
              ))}
            </div>
          </Card>
        </div>

        {/* 右侧：详细信息 */}
        <div className="lg:col-span-2 space-y-4">
          <Card
            className="shadow-sm"
            title="账户信息"
            extra={
              <Button
                type="primary"
                icon={editing ? <SaveOutlined /> : <EditOutlined />}
                onClick={() => editing ? form.submit() : setEditing(true)}
                className="bg-green-600 hover:bg-green-700"
              >
                {editing ? '保存' : '编辑'}
              </Button>
            }
          >
            {editing ? (
              <Form
                form={form}
                layout="vertical"
                initialValues={userInfo}
                onFinish={handleSave}
              >
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <Form.Item name="name" label="姓名" rules={[{ required: true }]}>
                    <Input />
                  </Form.Item>
                  <Form.Item name="username" label="用户名" rules={[{ required: true }]}>
                    <Input disabled />
                  </Form.Item>
                  <Form.Item name="email" label="邮箱" rules={[{ required: true, type: 'email' }]}>
                    <Input />
                  </Form.Item>
                  <Form.Item name="phone" label="手机号" rules={[{ required: true }]}>
                    <Input />
                  </Form.Item>
                  <Form.Item name="organization" label="所属组织" className="md:col-span-2">
                    <Input />
                  </Form.Item>
                </div>
              </Form>
            ) : (
              <Descriptions column={2} bordered>
                <Descriptions.Item label="姓名">{userInfo.name}</Descriptions.Item>
                <Descriptions.Item label="用户名">{userInfo.username}</Descriptions.Item>
                <Descriptions.Item label="邮箱">{userInfo.email}</Descriptions.Item>
                <Descriptions.Item label="手机号">{userInfo.phone}</Descriptions.Item>
                <Descriptions.Item label="所属组织" span={2}>{userInfo.organization}</Descriptions.Item>
                <Descriptions.Item label="角色">{userInfo.role}</Descriptions.Item>
                <Descriptions.Item label="加入时间">{userInfo.joinDate}</Descriptions.Item>
              </Descriptions>
            )}
          </Card>

          <Card className="shadow-sm" title="最近活动">
            <div className="space-y-3">
              {[
                { action: '登录系统', time: '2024-06-01 09:30', ip: '192.168.1.100' },
                { action: '上传图像识别', time: '2024-06-01 09:23', ip: '192.168.1.100' },
                { action: '修改系统设置', time: '2024-05-31 16:45', ip: '192.168.1.100' },
                { action: '导出数据报表', time: '2024-05-31 14:20', ip: '192.168.1.100' },
                { action: '登录系统', time: '2024-05-30 08:15', ip: '192.168.1.105' },
              ].map((item, i) => (
                <div key={i} className="flex items-center justify-between py-2 border-b border-gray-100 last:border-0">
                  <div>
                    <p className="text-sm text-gray-900">{item.action}</p>
                    <p className="text-xs text-gray-400">IP: {item.ip}</p>
                  </div>
                  <span className="text-xs text-gray-500">{item.time}</span>
                </div>
              ))}
            </div>
          </Card>
        </div>
      </div>
    </div>
  )
}
