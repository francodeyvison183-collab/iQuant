import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import * as authApi from '@/api/auth'

export interface AdminProfile {
  id: number
  username: string
  display_name: string
  must_change_password: boolean
  last_login_at: string | null
}

const ACCESS_KEY = 'admin_access_token'
const REFRESH_KEY = 'admin_refresh_token'

export const useAuthStore = defineStore('auth', () => {
  const accessToken = ref<string | null>(localStorage.getItem(ACCESS_KEY))
  const refreshToken = ref<string | null>(localStorage.getItem(REFRESH_KEY))
  const admin = ref<AdminProfile | null>(null)

  const isLoggedIn = computed(() => Boolean(accessToken.value))

  function persist() {
    if (accessToken.value) {
      localStorage.setItem(ACCESS_KEY, accessToken.value)
    } else {
      localStorage.removeItem(ACCESS_KEY)
    }
    if (refreshToken.value) {
      localStorage.setItem(REFRESH_KEY, refreshToken.value)
    } else {
      localStorage.removeItem(REFRESH_KEY)
    }
  }

  function setSession(data: authApi.LoginResult) {
    accessToken.value = data.access_token
    refreshToken.value = data.refresh_token
    admin.value = data.admin
    persist()
  }

  function clearSession() {
    accessToken.value = null
    refreshToken.value = null
    admin.value = null
    persist()
  }

  async function fetchMe() {
    const resp = await authApi.getMe()
    admin.value = resp.data!
    return admin.value
  }

  async function login(payload: authApi.LoginPayload) {
    const resp = await authApi.login(payload)
    setSession(resp.data!)
    return resp.data!
  }

  async function refresh() {
    if (!refreshToken.value) {
      throw new Error('no refresh token')
    }
    const resp = await authApi.refresh(refreshToken.value)
    setSession(resp.data!)
    return resp.data!
  }

  async function logout() {
    const rt = refreshToken.value
    const at = accessToken.value
    if (rt) {
      try {
        await authApi.logout(rt, at)
      } catch {
        // 忽略退出接口失败
      }
    }
    clearSession()
  }

  return {
    accessToken,
    refreshToken,
    admin,
    isLoggedIn,
    setSession,
    clearSession,
    fetchMe,
    login,
    refresh,
    logout,
  }
})
