import { useState } from 'react'
import { Button, Card, Form, Input, Tabs, message } from 'antd'
import { LockOutlined, UserOutlined, MailOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { register } from '../api/endpoints'
import { useAuth } from '../store/auth'

export default function Login() {
  const navigate = useNavigate()
  const { login, loading, error } = useAuth()
  const [tab, setTab] = useState('login')

  const onLogin = async (values: { username: string; password: string }) => {
    try {
      await login(values.username, values.password)
      navigate('/', { replace: true })
    } catch {
      /* 错误已存进 store，由下方提示展示 */
    }
  }

  const onRegister = async (values: {
    username: string
    email: string
    password: string
    full_name?: string
  }) => {
    try {
      await register(values)
      message.success('注册成功，请登录')
      setTab('login')
    } catch (e) {
      const detail =
        (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? '注册失败'
      message.error(detail)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
      <Card className="w-full max-w-md shadow-sm">
        <div className="text-center mb-6">
          <div className="w-12 h-12 bg-primary-600 rounded-xl flex items-center justify-center mx-auto mb-3">
            <span className="text-white font-bold text-lg">智</span>
          </div>
          <h1 className="text-xl font-bold text-gray-900">智农慧眼</h1>
          <p className="text-sm text-gray-500 mt-1">AI 精准植保平台</p>
        </div>

        <Tabs
          activeKey={tab}
          onChange={setTab}
          items={[
            {
              key: 'login',
              label: '登录',
              children: (
                <Form layout="vertical" onFinish={onLogin} requiredMark={false}>
                  <Form.Item name="username" rules={[{ required: true, message: '请输入用户名' }]}>
                    <Input prefix={<UserOutlined />} placeholder="用户名" size="large" />
                  </Form.Item>
                  <Form.Item name="password" rules={[{ required: true, message: '请输入密码' }]}>
                    <Input.Password prefix={<LockOutlined />} placeholder="密码" size="large" />
                  </Form.Item>
                  {error && <p className="text-sm text-red-600 mb-3">{error}</p>}
                  <Button
                    type="primary"
                    htmlType="submit"
                    size="large"
                    block
                    loading={loading}
                    className="bg-green-600 hover:bg-green-700"
                  >
                    登录
                  </Button>
                </Form>
              ),
            },
            {
              key: 'register',
              label: '注册',
              children: (
                <Form layout="vertical" onFinish={onRegister} requiredMark={false}>
                  <Form.Item name="username" rules={[{ required: true, message: '请输入用户名' }]}>
                    <Input prefix={<UserOutlined />} placeholder="用户名" size="large" />
                  </Form.Item>
                  <Form.Item
                    name="email"
                    rules={[{ required: true, type: 'email', message: '请输入有效邮箱' }]}
                  >
                    <Input prefix={<MailOutlined />} placeholder="邮箱" size="large" />
                  </Form.Item>
                  <Form.Item name="full_name">
                    <Input placeholder="姓名（可选）" size="large" />
                  </Form.Item>
                  <Form.Item
                    name="password"
                    rules={[{ required: true, min: 6, message: '密码至少 6 位' }]}
                  >
                    <Input.Password prefix={<LockOutlined />} placeholder="密码" size="large" />
                  </Form.Item>
                  <Button
                    type="primary"
                    htmlType="submit"
                    size="large"
                    block
                    className="bg-green-600 hover:bg-green-700"
                  >
                    注册
                  </Button>
                </Form>
              ),
            },
          ]}
        />
      </Card>
    </div>
  )
}
