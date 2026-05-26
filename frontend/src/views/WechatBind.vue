<template>
  <div class="wechat-bind-page">
    <div class="wechat-bind-shell">
      <div class="wechat-bind-badge">WeChat Bind</div>
      <h1>微信绑定中心</h1>
      <p class="wechat-bind-lead">
        {{ leadText }}
      </p>

      <div class="wechat-bind-card">
        <div class="wechat-bind-row">
          <span class="wechat-bind-label">当前 OpenID</span>
          <code class="wechat-bind-code">{{ displayOpenid }}</code>
        </div>
        <p class="wechat-bind-note">
          {{ noteText }}
        </p>

        <button
          v-if="openid"
          class="wechat-bind-primary"
          type="button"
          :disabled="binding"
          @click="bindCurrentAccount"
        >
          {{ binding ? '绑定中...' : '绑定到当前已登录账号' }}
        </button>

        <div class="wechat-bind-actions">
          <button class="wechat-bind-secondary" type="button" @click="goLogin">
            去登录并绑定
          </button>
          <button class="wechat-bind-secondary" type="button" @click="goRegister">
            去入驻并绑定
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '../api'

const route = useRoute()
const router = useRouter()
const binding = ref(false)

const openid = computed(() => String(route.query.openid || '').trim())
const target = computed(() => (String(route.query.target || '').trim().toLowerCase() === 'register' ? 'register' : 'login'))

const displayOpenid = computed(() => openid.value || '未从微信回调中获取到 OpenID')
const leadText = computed(() => {
  if (openid.value) {
    return '你可以直接把当前微信身份绑定到已登录账号，或者先登录/入驻后自动完成绑定。'
  }
  return '当前页面没有携带 OpenID。你仍然可以继续登录或入驻，但若要接收微信推送，请从公众号欢迎消息中的链接进入。'
})
const noteText = computed(() => {
  if (openid.value) {
    return '如果浏览器里已经登录过供应商账号，可以直接点击绑定。否则请先进入登录或入驻页面，系统会带着 OpenID 一起提交。'
  }
  return '没有 OpenID 时无法直接绑定当前微信。建议先关注公众号，并从欢迎消息里的绑定链接再次进入。'
})

const pushWithOpenid = (path) => {
  const query = openid.value ? { openid: openid.value } : {}
  router.push({ path, query })
}

const goLogin = () => {
  pushWithOpenid('/login')
}

const goRegister = () => {
  pushWithOpenid('/register')
}

const bindCurrentAccount = async () => {
  if (!openid.value) {
    ElMessage.warning('当前页面没有 OpenID，无法直接绑定。')
    return
  }

  const token = localStorage.getItem('token')
  if (!token) {
    ElMessage.info('请先登录供应商账号，再回来点击绑定。')
    router.push({ path: target.value === 'register' ? '/register' : '/login', query: { openid: openid.value } })
    return
  }

  binding.value = true
  try {
    const { data } = await api.post('/auth/wechat-bind', { openid: openid.value })
    ElMessage.success(data?.message || '微信绑定成功')
  } catch (error) {
    if (error?.response?.status !== 401) {
      ElMessage.error(error.response?.data?.detail || '微信绑定失败')
    }
  } finally {
    binding.value = false
  }
}
</script>

<style scoped>
.wechat-bind-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background:
    radial-gradient(circle at top left, rgba(34, 197, 94, 0.22), transparent 36%),
    radial-gradient(circle at bottom right, rgba(14, 165, 233, 0.18), transparent 30%),
    linear-gradient(180deg, #f4fbf6 0%, #e7f2ff 100%);
}

.wechat-bind-shell {
  width: min(520px, 100%);
  padding: 36px 30px 32px;
  border-radius: 28px;
  background: rgba(255, 255, 255, 0.92);
  border: 1px solid rgba(15, 23, 42, 0.08);
  box-shadow: 0 20px 48px rgba(15, 23, 42, 0.12);
}

.wechat-bind-badge {
  display: inline-flex;
  padding: 6px 12px;
  border-radius: 999px;
  background: rgba(22, 163, 74, 0.12);
  color: #15803d;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.wechat-bind-shell h1 {
  margin: 18px 0 10px;
  font-size: clamp(30px, 5vw, 42px);
  line-height: 1.1;
  color: #0f172a;
}

.wechat-bind-lead {
  color: #475569;
  line-height: 1.8;
}

.wechat-bind-card {
  margin-top: 24px;
  padding: 22px 20px;
  border-radius: 22px;
  background: rgba(248, 250, 252, 0.92);
  border: 1px solid rgba(148, 163, 184, 0.2);
}

.wechat-bind-row {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.wechat-bind-label {
  color: #64748b;
  font-size: 13px;
  font-weight: 600;
}

.wechat-bind-code {
  display: block;
  padding: 12px 14px;
  border-radius: 14px;
  background: #0f172a;
  color: #e2e8f0;
  font-size: 13px;
  line-height: 1.6;
  word-break: break-all;
}

.wechat-bind-note {
  margin: 16px 0 0;
  color: #475569;
  line-height: 1.7;
}

.wechat-bind-primary,
.wechat-bind-secondary {
  border: none;
  border-radius: 16px;
  padding: 14px 18px;
  font-size: 15px;
  font-weight: 700;
  cursor: pointer;
  transition: transform 0.2s ease, box-shadow 0.2s ease, opacity 0.2s ease;
}

.wechat-bind-primary {
  width: 100%;
  margin-top: 20px;
  background: linear-gradient(135deg, #16a34a 0%, #22c55e 100%);
  color: #fff;
  box-shadow: 0 14px 30px rgba(34, 197, 94, 0.22);
}

.wechat-bind-secondary {
  flex: 1;
  background: #fff;
  color: #0f172a;
  border: 1px solid rgba(148, 163, 184, 0.35);
}

.wechat-bind-primary:hover,
.wechat-bind-secondary:hover {
  transform: translateY(-1px);
}

.wechat-bind-primary:disabled {
  cursor: not-allowed;
  opacity: 0.7;
  transform: none;
}

.wechat-bind-actions {
  margin-top: 14px;
  display: flex;
  gap: 12px;
}

@media (max-width: 640px) {
  .wechat-bind-shell {
    padding: 30px 22px 24px;
    border-radius: 22px;
  }

  .wechat-bind-actions {
    flex-direction: column;
  }
}
</style>
