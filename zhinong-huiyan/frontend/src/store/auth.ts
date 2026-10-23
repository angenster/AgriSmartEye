import { create } from 'zustand'
import { TOKEN_KEY } from '../api/client'
import { fetchMe, login as loginRequest } from '../api/endpoints'
import type { UserInfo } from '../api/types'

interface AuthState {
  token: string | null
  user: UserInfo | null
  loading: boolean
  error: string | null
  login: (username: string, password: string) => Promise<void>
  logout: () => void
  /** 用已存的 token 拉一次用户信息，用于刷新页面后恢复登录态 */
  restore: () => Promise<void>
}

export const useAuth = create<AuthState>((set, get) => ({
  token: localStorage.getItem(TOKEN_KEY),
  user: null,
  loading: false,
  error: null,

  login: async (username, password) => {
    set({ loading: true, error: null })
    try {
      const token = await loginRequest(username, password)
      localStorage.setItem(TOKEN_KEY, token)
      set({ token })
      const user = await fetchMe()
      set({ user, loading: false })
    } catch (e) {
      const message =
        (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        '登录失败，请检查用户名与密码'
      set({ error: message, loading: false, token: null })
      localStorage.removeItem(TOKEN_KEY)
      throw e
    }
  },

  logout: () => {
    localStorage.removeItem(TOKEN_KEY)
    set({ token: null, user: null, error: null })
  },

  restore: async () => {
    if (!get().token || get().user) return
    set({ loading: true })
    try {
      const user = await fetchMe()
      set({ user, loading: false })
    } catch {
      localStorage.removeItem(TOKEN_KEY)
      set({ token: null, user: null, loading: false })
    }
  },
}))
