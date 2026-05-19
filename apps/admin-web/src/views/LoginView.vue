<script setup lang="ts">
import { nextTick, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getAuthConfig } from '@/api/auth'
import { extractApiError } from '@/api/errors'
import { useAuthStore } from '@/stores/auth'

declare global {
  interface Window {
    turnstile?: {
      render: (el: HTMLElement, opts: Record<string, unknown>) => string
      getResponse: (widgetId: string) => string
      reset: (widgetId: string) => void
    }
  }
}

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

const username = ref('')
const password = ref('')
const loading = ref(false)
const turnstileSiteKey = ref('')
const turnstileRequired = ref(false)
const turnstileEl = ref<HTMLElement | null>(null)
const loginError = ref('')
let turnstileWidgetId = ''

async function renderTurnstile() {
  if (!turnstileSiteKey.value) return
  await loadTurnstileScript()
  await nextTick()
  if (turnstileEl.value && window.turnstile) {
    turnstileWidgetId = window.turnstile.render(turnstileEl.value, {
      sitekey: turnstileSiteKey.value,
      theme: 'light',
    })
  }
}

onMounted(async () => {
  try {
    const cfg = await getAuthConfig()
    turnstileSiteKey.value = cfg.data?.turnstile_site_key || ''
    turnstileRequired.value = Boolean(cfg.data?.turnstile_required)
    await renderTurnstile()
  } catch {
    // 开发环境无 Turnstile 时可继续登录
  }
})

function loadTurnstileScript(): Promise<void> {
  return new Promise((resolve, reject) => {
    if (document.querySelector('script[data-turnstile]')) {
      resolve()
      return
    }
    const s = document.createElement('script')
    s.src = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit'
    s.async = true
    s.defer = true
    s.dataset.turnstile = '1'
    s.onload = () => resolve()
    s.onerror = () => reject(new Error('Turnstile 脚本加载失败'))
    document.head.appendChild(s)
  })
}

function captchaToken(): string {
  if (!turnstileSiteKey.value || !window.turnstile || !turnstileWidgetId) {
    return ''
  }
  return window.turnstile.getResponse(turnstileWidgetId) || ''
}

async function onSubmit() {
  if (!username.value || !password.value) {
    ElMessage.warning('请输入用户名和密码')
    return
  }
  if (turnstileRequired.value && !captchaToken()) {
    ElMessage.warning('请完成人机验证')
    return
  }
  loginError.value = ''
  loading.value = true
  try {
    await auth.login({
      username: username.value.trim(),
      password: password.value,
      captcha_token: captchaToken(),
    })
    const redirect = (route.query.redirect as string) || '/market/hosts'
    await router.replace(redirect)
  } catch (err) {
    loginError.value = extractApiError(err)
    ElMessage.error(loginError.value)
    if (turnstileWidgetId && window.turnstile) {
      window.turnstile.reset(turnstileWidgetId)
    }
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-page">
    <el-card class="login-card" shadow="hover">
      <template #header>
        <div class="login-title">iQuant 管理后台</div>
      </template>
      <el-form label-position="top" @submit.prevent="onSubmit">
        <el-form-item label="用户名">
          <el-input v-model="username" autocomplete="username" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input
            v-model="password"
            type="password"
            show-password
            autocomplete="current-password"
            @keyup.enter="onSubmit"
          />
        </el-form-item>
        <div v-if="turnstileSiteKey" ref="turnstileEl" class="turnstile" />
        <el-alert
          v-if="loginError"
          :title="loginError"
          type="error"
          show-icon
          :closable="false"
          class="login-error"
        />
        <el-button type="primary" class="submit" :loading="loading" @click="onSubmit">
          登录
        </el-button>
        <p class="login-dev-hint">
          本地开发默认账号见项目根目录 <code>.env</code> 中
          <code>IQUANT_ADMIN_BOOTSTRAP_USERNAME</code> /
          <code>IQUANT_ADMIN_BOOTSTRAP_PASSWORD</code>（需先执行
          <code>.\make.ps1 admin-bootstrap</code>）。
        </p>
      </el-form>
    </el-card>
  </div>
</template>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #1e3a5f 0%, #111827 100%);
  padding: 24px;
}
.login-card {
  width: 100%;
  max-width: 400px;
}
.login-title {
  font-size: 18px;
  font-weight: 600;
  text-align: center;
}
.turnstile {
  margin-bottom: 16px;
  display: flex;
  justify-content: center;
}
.submit {
  width: 100%;
}
.login-error {
  margin-bottom: 12px;
}
.login-dev-hint {
  margin: 14px 0 0;
  font-size: 12px;
  line-height: 1.45;
  color: #6b7280;
  text-align: center;
}
.login-dev-hint code {
  font-size: 11px;
}
</style>
