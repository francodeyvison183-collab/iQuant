import { get, http, patch, post } from './client'
import type { ApiEnvelope } from './client'

const AUTH_TIMEOUT_MS = 8_000

export interface AdminProfile {
  id: number
  username: string
  display_name: string
  must_change_password: boolean
  last_login_at: string | null
}

export interface LoginResult {
  access_token: string
  refresh_token: string
  expires_at: string
  admin: AdminProfile
}

export interface AuthConfig {
  turnstile_site_key: string
  turnstile_required: boolean
}

export interface LoginPayload {
  username: string
  password: string
  captcha_token?: string
}

export const getAuthConfig = () =>
  http
    .get<ApiEnvelope<AuthConfig>>('/admin/auth/config', { timeout: AUTH_TIMEOUT_MS })
    .then((r) => r.data)

export const login = (payload: LoginPayload) =>
  post<LoginResult>('/admin/auth/login', payload)

export const refresh = (refreshToken: string) =>
  post<LoginResult>('/admin/auth/refresh', { refresh_token: refreshToken })

export const logout = (refreshToken: string, accessToken: string | null) =>
  post<{ message: string }>(
    '/admin/auth/logout',
    { refresh_token: refreshToken },
    accessToken ? { Authorization: `Bearer ${accessToken}` } : undefined,
  )

export const getMe = () =>
  http
    .get<ApiEnvelope<AdminProfile>>('/admin/auth/me', { timeout: AUTH_TIMEOUT_MS })
    .then((r) => r.data)

export const changePassword = (oldPassword: string, newPassword: string) =>
  patch<{ message: string }>('/admin/auth/password', {
    old_password: oldPassword,
    new_password: newPassword,
  })
