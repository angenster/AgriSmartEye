import axios from 'axios'

export const TOKEN_KEY = 'zhinong_token'

/** 诊断链路会跑 Agent + RAG，耗时以秒计；门禁要加载两个权重，故单独给更长的超时 */
export const LONG_TIMEOUT = 120_000
export const GATE_TIMEOUT = 15 * 60 * 1000

const client = axios.create({
  // vite.config.ts 里 /api 已代理到后端
  baseURL: '/api/v1',
  timeout: LONG_TIMEOUT,
})

client.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY)
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

client.interceptors.response.use(
  (response) => response,
  (error) => {
    // 凭证失效就清掉并回登录页，避免每个页面各自处理
    if (error.response?.status === 401) {
      localStorage.removeItem(TOKEN_KEY)
      if (!window.location.pathname.startsWith('/login')) {
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  },
)

/** 把后端的 detail 抽成可直接展示的文案 */
export function describeError(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail
    if (typeof detail === 'string') return detail
    if (detail) return JSON.stringify(detail)
    return error.message
  }
  return String(error)
}

export default client
