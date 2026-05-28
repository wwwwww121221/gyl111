<template>
  <div class="login-page">
    <section class="hero-panel">
      <div class="hero-bg-shapes">
        <div class="shape shape-1"></div>
        <div class="shape shape-2"></div>
        <div class="shape shape-3"></div>
        <div class="shape shape-4"></div>
        <div class="shape shape-5"></div>
      </div>
      <div class="hero-inner">
        <div class="brand-row">
          <div class="brand-mark">SCM</div>
          <div class="brand-name">JULAN</div>
        </div>
        <h1>供应商<br />协同平台</h1>
        <p>统一的供应商登录入口，支持密码登录、短信验证码登录，以及手机号验证码找回密码。</p>
        <div class="hero-features">
          <div class="feature-item">
            <div class="feature-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
            </div>
            <span>安全加密</span>
          </div>
          <div class="feature-item">
            <div class="feature-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>
            </div>
            <span>快速响应</span>
          </div>
          <div class="feature-item">
            <div class="feature-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
            </div>
            <span>协同高效</span>
          </div>
        </div>
      </div>
    </section>

    <section class="auth-panel">
      <div class="auth-card" :class="{ 'card-enter': cardEntered }">
        <div class="auth-header">
          <h2>{{ isInternalMode ? '内部账号登录' : '供应商登录' }}</h2>
          <p>{{ isInternalMode ? '请输入内部账号信息进入系统。' : '请选择密码登录或验证码登录。' }}</p>
        </div>

        <el-alert
          v-if="wechatHint"
          :title="wechatHint"
          type="info"
          :closable="false"
          class="wechat-alert"
        />

        <div v-if="!isInternalMode && showWechatBindEntry" class="wechat-bind-entry">
          <span class="wechat-bind-copy">当前页面未携带微信身份，首次绑定请先完成微信授权。</span>
          <el-button type="success" plain @click="startWechatBind('login')">
            微信授权绑定
          </el-button>
        </div>

        <div v-if="!isInternalMode" class="mode-tabs">
          <div class="mode-tabs-indicator" :class="{ 'indicator-right': activeTab === 'supplier-sms' }"></div>
          <button
            type="button"
            class="mode-tab"
            :class="{ active: activeTab === 'supplier-password' }"
            @click="activeTab = 'supplier-password'"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="tab-icon"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
            密码登录
          </button>
          <button
            type="button"
            class="mode-tab"
            :class="{ active: activeTab === 'supplier-sms' }"
            @click="activeTab = 'supplier-sms'"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="tab-icon"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72c.127.96.361 1.903.7 2.81a2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0 1 22 16.92z"/></svg>
            验证码登录
          </button>
        </div>

        <transition name="form-fade" mode="out-in">
          <el-form
            v-if="activeTab === 'supplier-password'"
            key="supplier-password"
            ref="supplierPasswordRef"
            :model="supplierPasswordForm"
            :rules="supplierPasswordRules"
            label-position="top"
            class="login-form"
          >
            <el-form-item label="手机号" prop="phone">
              <el-input
                v-model="supplierPasswordForm.phone"
                maxlength="11"
                placeholder="请输入手机号"
                autocomplete="tel"
                size="large"
              >
                <template #prefix>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="input-icon"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72c.127.96.361 1.903.7 2.81a2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0 1 22 16.92z"/></svg>
                </template>
              </el-input>
            </el-form-item>

            <el-form-item label="密码" prop="password">
              <el-input
                v-model="supplierPasswordForm.password"
                type="password"
                show-password
                placeholder="请输入密码"
                autocomplete="current-password"
                size="large"
                @keyup.enter="handleSupplierPasswordLogin"
              >
                <template #prefix>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="input-icon"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
                </template>
              </el-input>
            </el-form-item>

            <div class="helper-row">
              <el-button link type="primary" @click="openResetDialog">忘记密码？</el-button>
            </div>

            <el-button type="primary" class="submit-btn" :loading="loading" @click="handleSupplierPasswordLogin">
              登录供应商端
            </el-button>
          </el-form>

          <el-form
            v-else-if="activeTab === 'supplier-sms'"
            key="supplier-sms"
            ref="supplierSmsRef"
            :model="supplierSmsForm"
            :rules="supplierSmsRules"
            label-position="top"
            class="login-form"
          >
            <el-form-item label="手机号" prop="phone">
              <el-input
                v-model="supplierSmsForm.phone"
                maxlength="11"
                placeholder="请输入手机号"
                autocomplete="tel"
                size="large"
              >
                <template #prefix>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="input-icon"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72c.127.96.361 1.903.7 2.81a2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0 1 22 16.92z"/></svg>
                </template>
              </el-input>
            </el-form-item>

            <el-form-item label="验证码" prop="sms_code">
              <div class="sms-input-row">
                <el-input
                  v-model="supplierSmsForm.sms_code"
                  maxlength="6"
                  placeholder="请输入验证码"
                  autocomplete="off"
                  size="large"
                  @keyup.enter="handleSupplierSmsLogin"
                >
                  <template #prefix>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="input-icon"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>
                  </template>
                </el-input>
                <el-button
                  class="sms-btn"
                  :disabled="smsCountdown > 0 || smsSending"
                  @click="sendLoginSmsCode"
                >
                  {{ smsCountdown > 0 ? `${smsCountdown}s` : '获取验证码' }}
                </el-button>
              </div>
            </el-form-item>

            <el-button type="primary" class="submit-btn" :loading="loading" @click="handleSupplierSmsLogin">
              登录供应商端
            </el-button>
          </el-form>

          <el-form
            v-else
            key="internal"
            ref="internalRef"
            :model="internalForm"
            :rules="internalRules"
            label-position="top"
            class="login-form"
          >
            <el-form-item label="登录账号" prop="username">
              <el-input
                v-model="internalForm.username"
                placeholder="请输入登录账号"
                autocomplete="username"
                size="large"
              >
                <template #prefix>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="input-icon"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
                </template>
              </el-input>
            </el-form-item>

            <el-form-item label="密码" prop="password">
              <el-input
                v-model="internalForm.password"
                type="password"
                show-password
                placeholder="请输入密码"
                autocomplete="current-password"
                size="large"
                @keyup.enter="handleInternalLogin"
              >
                <template #prefix>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="input-icon"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
                </template>
              </el-input>
            </el-form-item>

            <el-button type="primary" class="submit-btn" :loading="loading" @click="handleInternalLogin">
              登录后台
            </el-button>
          </el-form>
        </transition>

        <div class="footer-actions">
          <el-button link type="primary" @click="pushWithOpenid('/register')">
            创建新供应商入驻 / 申请加入已有供应商
          </el-button>
          <el-button link @click="togglePortal">
            {{ isInternalMode ? '返回供应商登录' : '内部账号登录' }}
          </el-button>
        </div>
      </div>
    </section>

    <el-dialog v-model="resetDialogVisible" title="找回供应商密码" width="420px" destroy-on-close>
      <el-form ref="resetRef" :model="resetForm" :rules="resetRules" label-position="top">
        <el-form-item label="手机号" prop="phone">
          <el-input v-model="resetForm.phone" maxlength="11" placeholder="请输入手机号" autocomplete="tel">
            <template #append>
              <el-button :disabled="resetCountdown > 0 || resetSmsSending" @click="sendResetSmsCode">
                {{ resetCountdown > 0 ? `${resetCountdown}s` : '获取验证码' }}
              </el-button>
            </template>
          </el-input>
        </el-form-item>

        <el-form-item label="验证码" prop="sms_code">
          <el-input
            v-model="resetForm.sms_code"
            maxlength="6"
            placeholder="请输入验证码"
            autocomplete="off"
          />
        </el-form-item>

        <el-form-item label="新密码" prop="new_password">
          <el-input
            v-model="resetForm.new_password"
            type="password"
            show-password
            placeholder="至少 6 位"
            autocomplete="new-password"
          />
        </el-form-item>

        <el-form-item label="确认新密码" prop="confirm_password">
          <el-input
            v-model="resetForm.confirm_password"
            type="password"
            show-password
            placeholder="请再次输入新密码"
            autocomplete="new-password"
          />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="resetDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="resetSubmitting" @click="submitResetPassword">
          重置密码
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import api, { getApiOrigin } from '../api'

const router = useRouter()
const route = useRoute()

const activeTab = ref('supplier-password')
const loading = ref(false)
const smsSending = ref(false)
const resetSmsSending = ref(false)
const smsCountdown = ref(0)
const resetCountdown = ref(0)
const resetDialogVisible = ref(false)
const resetSubmitting = ref(false)
const wechatHint = ref('')
const cardEntered = ref(false)

let smsTimer = null
let resetTimer = null

const supplierPasswordRef = ref(null)
const supplierSmsRef = ref(null)
const internalRef = ref(null)
const resetRef = ref(null)

const supplierPasswordForm = reactive({
  phone: '',
  password: '',
})

const supplierSmsForm = reactive({
  phone: '',
  sms_code: '',
})

const internalForm = reactive({
  username: '',
  password: '',
})

const resetForm = reactive({
  phone: '',
  sms_code: '',
  new_password: '',
  confirm_password: '',
})

const isInternalMode = computed(() => activeTab.value === 'internal')
const getOpenid = () => String(route.query.openid || '').trim()
const hasOpenid = computed(() => Boolean(getOpenid()))
const isWechatBrowser = computed(() => /micromessenger/i.test(window.navigator.userAgent || ''))
const showWechatBindEntry = computed(() => isWechatBrowser.value && !hasOpenid.value)

const phoneValidator = (_, value, callback) => {
  if (!/^1[3-9]\d{9}$/.test(String(value || '').trim())) {
    callback(new Error('请输入有效的 11 位手机号'))
    return
  }
  callback()
}

const confirmPasswordValidator = (_, value, callback) => {
  if (!value) {
    callback(new Error('请再次输入新密码'))
    return
  }
  if (value !== resetForm.new_password) {
    callback(new Error('两次输入的密码不一致'))
    return
  }
  callback()
}

const supplierPasswordRules = {
  phone: [{ required: true, validator: phoneValidator, trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

const supplierSmsRules = {
  phone: [{ required: true, validator: phoneValidator, trigger: 'blur' }],
  sms_code: [{ required: true, message: '请输入验证码', trigger: 'blur' }],
}

const internalRules = {
  username: [{ required: true, message: '请输入登录账号', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

const resetRules = {
  phone: [{ required: true, validator: phoneValidator, trigger: 'blur' }],
  sms_code: [{ required: true, message: '请输入验证码', trigger: 'blur' }],
  new_password: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 6, message: '密码至少 6 位', trigger: 'blur' },
  ],
  confirm_password: [{ required: true, validator: confirmPasswordValidator, trigger: 'blur' }],
}

const pushWithOpenid = (path) => {
  const openid = getOpenid()
  router.push(openid ? { path, query: { openid } } : { path })
}

const startWechatBind = (target = 'login') => {
  const normalizedTarget = target === 'register' ? 'register' : 'login'
  window.location.href = `${getApiOrigin()}/wechat/oauth/start?target=${normalizedTarget}`
}

const persistLogin = (payload, fallbackUsername = '') => {
  localStorage.setItem('token', payload.access_token || '')
  localStorage.setItem('role', payload.role || '')
  localStorage.setItem('department', payload.department || '')
  localStorage.setItem('username', payload.username || fallbackUsername)
  localStorage.setItem('supplier_id', payload.supplier_id ? String(payload.supplier_id) : '')
  localStorage.setItem('supplier_name', payload.supplier_name || '')
  localStorage.setItem('supplier_status', payload.supplier_status || '')
  localStorage.setItem('member_status', payload.member_status || '')
}

const getSupplierHomePath = (payload) => (payload?.supplier_status === 'approved' ? '/supplier/inquiries' : '/supplier/company-info')

const startCountdown = (target) => {
  target.value = 60
  const timer = setInterval(() => {
    target.value -= 1
    if (target.value <= 0) {
      clearInterval(timer)
      if (target === smsCountdown) {
        smsTimer = null
      } else {
        resetTimer = null
      }
    }
  }, 1000)

  if (target === smsCountdown) {
    if (smsTimer) clearInterval(smsTimer)
    smsTimer = timer
  } else {
    if (resetTimer) clearInterval(resetTimer)
    resetTimer = timer
  }
}

const showSmsDebugIfNeeded = (data) => {
  if (data?.debug_code) {
    ElMessage.info(`调试验证码：${data.debug_code}`)
  }
}

const sendSceneCode = async (phone, scene) => {
  const { data } = await api.post('/auth/supplier/send-sms-code', { phone, scene })
  showSmsDebugIfNeeded(data)
  return data
}

const sendLoginSmsCode = async () => {
  const valid = await supplierSmsRef.value?.validateField('phone').then(() => true).catch(() => false)
  if (!valid) return

  smsSending.value = true
  try {
    const data = await sendSceneCode(supplierSmsForm.phone, 'login')
    ElMessage.success(data?.message || '验证码已发送')
    startCountdown(smsCountdown)
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '验证码发送失败')
  } finally {
    smsSending.value = false
  }
}

const sendResetSmsCode = async () => {
  const valid = await resetRef.value?.validateField('phone').then(() => true).catch(() => false)
  if (!valid) return

  resetSmsSending.value = true
  try {
    const data = await sendSceneCode(resetForm.phone, 'reset_password')
    ElMessage.success(data?.message || '验证码已发送')
    startCountdown(resetCountdown)
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '验证码发送失败')
  } finally {
    resetSmsSending.value = false
  }
}

const handleSupplierPasswordLogin = async () => {
  const valid = await supplierPasswordRef.value?.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  try {
    const { data } = await api.post('/auth/supplier/password-login', {
      phone: supplierPasswordForm.phone,
      password: supplierPasswordForm.password,
      openid: getOpenid() || undefined,
    })
    persistLogin(data, supplierPasswordForm.phone)
    ElMessage.success('登录成功')
    router.push(getSupplierHomePath(data))
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '登录失败')
  } finally {
    loading.value = false
  }
}

const handleSupplierSmsLogin = async () => {
  const valid = await supplierSmsRef.value?.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  try {
    const { data } = await api.post('/auth/supplier/sms-login', {
      phone: supplierSmsForm.phone,
      sms_code: supplierSmsForm.sms_code,
      openid: getOpenid() || undefined,
    })
    persistLogin(data, supplierSmsForm.phone)
    ElMessage.success('登录成功')
    router.push(getSupplierHomePath(data))
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '登录失败')
  } finally {
    loading.value = false
  }
}

const handleInternalLogin = async () => {
  const valid = await internalRef.value?.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  try {
    const formData = new URLSearchParams()
    formData.append('username', internalForm.username)
    formData.append('password', internalForm.password)

    const { data } = await api.post('/auth/login', formData, {
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
    })

    persistLogin(data, internalForm.username)
    ElMessage.success('登录成功')
    router.push(data.role === 'supplier' ? getSupplierHomePath(data) : '/dashboard')
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '登录失败')
  } finally {
    loading.value = false
  }
}

const openResetDialog = () => {
  resetForm.phone = supplierPasswordForm.phone || supplierSmsForm.phone || ''
  resetForm.sms_code = ''
  resetForm.new_password = ''
  resetForm.confirm_password = ''
  resetDialogVisible.value = true
}

const submitResetPassword = async () => {
  const valid = await resetRef.value?.validate().catch(() => false)
  if (!valid) return

  resetSubmitting.value = true
  try {
    await api.post('/auth/supplier/reset-password', {
      phone: resetForm.phone,
      sms_code: resetForm.sms_code,
      new_password: resetForm.new_password,
    })
    ElMessage.success('密码已重置，请使用新密码登录')
    supplierPasswordForm.phone = resetForm.phone
    supplierPasswordForm.password = ''
    resetDialogVisible.value = false
    activeTab.value = 'supplier-password'
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '重置失败')
  } finally {
    resetSubmitting.value = false
  }
}

const togglePortal = () => {
  activeTab.value = isInternalMode.value ? 'supplier-password' : 'internal'
}

const tryWechatDirectLogin = async () => {
  const openid = getOpenid()
  if (!openid) return

  try {
    const { data } = await api.post('/auth/supplier/wechat-login', { openid }, { silentError: true })
    if (data?.bound && data?.access_token) {
      persistLogin(data)
      ElMessage.success('微信登录成功')
      router.push(getSupplierHomePath(data))
      return
    }

    wechatHint.value = '当前微信账号尚未绑定手机号，请先完成手机号登录或绑定。'
    activeTab.value = 'supplier-password'
  } catch (error) {
    wechatHint.value = '微信登录校验失败，请改用手机号登录。'
    activeTab.value = 'supplier-password'
  }
}

onMounted(() => {
  const wechatError = String(route.query.wechat_error || '').trim()
  if (wechatError) {
    wechatHint.value = wechatError
  }
  tryWechatDirectLogin()
  requestAnimationFrame(() => {
    cardEntered.value = true
  })
})

onBeforeUnmount(() => {
  if (smsTimer) clearInterval(smsTimer)
  if (resetTimer) clearInterval(resetTimer)
})
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(420px, 1.15fr);
  background: linear-gradient(135deg, #0f172a 0%, #1e3a5f 40%, #1a56db 100%);
  overflow: hidden;
}

.hero-panel {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 48px;
  overflow: hidden;
}

.hero-bg-shapes {
  position: absolute;
  inset: 0;
  pointer-events: none;
  overflow: hidden;
}

.shape {
  position: absolute;
  border-radius: 50%;
  opacity: 0.08;
  background: #ffffff;
}

.shape-1 {
  width: 600px;
  height: 600px;
  top: -200px;
  left: -100px;
  animation: float-slow 20s ease-in-out infinite;
}

.shape-2 {
  width: 400px;
  height: 400px;
  bottom: -120px;
  right: -80px;
  animation: float-slow 15s ease-in-out infinite reverse;
}

.shape-3 {
  width: 200px;
  height: 200px;
  top: 40%;
  right: 15%;
  opacity: 0.05;
  animation: float-slow 12s ease-in-out infinite;
}

.shape-4 {
  width: 120px;
  height: 120px;
  top: 20%;
  left: 60%;
  opacity: 0.06;
  animation: float-slow 18s ease-in-out infinite reverse;
}

.shape-5 {
  width: 80px;
  height: 80px;
  bottom: 25%;
  left: 20%;
  opacity: 0.04;
  animation: float-slow 10s ease-in-out infinite;
}

@keyframes float-slow {
  0%, 100% { transform: translate(0, 0) scale(1); }
  33% { transform: translate(30px, -20px) scale(1.05); }
  66% { transform: translate(-20px, 15px) scale(0.95); }
}

.hero-inner {
  position: relative;
  z-index: 1;
  max-width: 480px;
  color: #fff;
}

.brand-row {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 28px;
}

.brand-mark {
  width: 56px;
  height: 56px;
  border-radius: 18px;
  display: grid;
  place-items: center;
  background: rgba(255, 255, 255, 0.14);
  border: 1px solid rgba(255, 255, 255, 0.25);
  font-size: 18px;
  font-weight: 800;
  letter-spacing: 0.06em;
}

.brand-name {
  font-size: 20px;
  font-weight: 700;
  letter-spacing: 0.12em;
}

.hero-inner h1 {
  margin: 0;
  font-size: clamp(42px, 6vw, 68px);
  line-height: 0.96;
  letter-spacing: -0.04em;
}

.hero-inner p {
  margin: 24px 0 0;
  color: rgba(226, 232, 240, 0.92);
  font-size: 16px;
  line-height: 1.8;
}

.hero-features {
  display: grid;
  gap: 14px;
  margin-top: 36px;
}

.feature-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 16px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.12);
}

.feature-icon {
  width: 38px;
  height: 38px;
  display: grid;
  place-items: center;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.12);
}

.feature-icon svg {
  width: 18px;
  height: 18px;
}

.auth-panel {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 28px;
  background: rgba(248, 250, 252, 0.92);
  backdrop-filter: blur(10px);
}

.auth-card {
  width: min(520px, 100%);
  padding: 34px 32px 28px;
  border-radius: 30px;
  background: rgba(255, 255, 255, 0.98);
  box-shadow:
    0 4px 6px -1px rgba(0, 0, 0, 0.05),
    0 20px 50px -12px rgba(30, 58, 138, 0.15);
  opacity: 0;
  transform: translateY(24px);
  transition: all 0.6s cubic-bezier(0.16, 1, 0.3, 1);
}

.auth-card.card-enter {
  opacity: 1;
  transform: translateY(0);
}

.auth-header h2 {
  margin: 0;
  color: #0f172a;
  font-size: 26px;
  font-weight: 800;
  letter-spacing: -0.5px;
}

.auth-header p {
  margin: 8px 0 0;
  color: #64748b;
  font-size: 15px;
  line-height: 1.6;
}

.wechat-alert {
  margin-top: 18px;
}

.wechat-bind-entry {
  margin-top: 18px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 14px 16px;
  border-radius: 14px;
  background: #f0fdf4;
  border: 1px solid #bbf7d0;
}

.wechat-bind-copy {
  color: #166534;
  line-height: 1.6;
}

.mode-tabs {
  position: relative;
  margin: 24px 0 28px;
  display: flex;
  background: #f1f5f9;
  border-radius: 14px;
  padding: 4px;
  gap: 4px;
}

.mode-tabs-indicator {
  position: absolute;
  top: 4px;
  bottom: 4px;
  left: 4px;
  width: calc(50% - 6px);
  border-radius: 10px;
  background: #ffffff;
  box-shadow: 0 10px 20px rgba(15, 23, 42, 0.08);
  transition: transform 0.25s ease;
}

.mode-tabs-indicator.indicator-right {
  transform: translateX(calc(100% + 4px));
}

.mode-tab {
  position: relative;
  z-index: 1;
  flex: 1;
  border: none;
  background: transparent;
  padding: 12px 10px;
  border-radius: 10px;
  color: #64748b;
  font-size: 15px;
  font-weight: 700;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  cursor: pointer;
}

.mode-tab.active {
  color: #0f172a;
}

.tab-icon {
  width: 16px;
  height: 16px;
}

.login-form {
  margin-top: 8px;
}

.login-form :deep(.el-form-item__label) {
  color: #334155;
  font-weight: 700;
}

.input-icon {
  width: 17px;
  height: 17px;
}

.sms-input-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 10px;
}

.sms-btn {
  min-width: 120px;
}

.helper-row {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 14px;
}

.submit-btn {
  width: 100%;
  height: 46px;
  border-radius: 14px;
  font-weight: 700;
}

.footer-actions {
  margin-top: 20px;
  display: flex;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.form-fade-enter-active,
.form-fade-leave-active {
  transition: opacity 0.22s ease, transform 0.22s ease;
}

.form-fade-enter-from,
.form-fade-leave-to {
  opacity: 0;
  transform: translateY(8px);
}

@media (max-width: 980px) {
  .login-page {
    grid-template-columns: 1fr;
  }

  .hero-panel {
    min-height: 260px;
    padding: 36px 24px 12px;
  }

  .auth-panel {
    padding: 20px 16px 28px;
  }
}

@media (max-width: 640px) {
  .auth-card {
    padding: 24px 18px 20px;
    border-radius: 22px;
  }

  .wechat-bind-entry,
  .footer-actions {
    flex-direction: column;
    align-items: stretch;
  }

  .sms-input-row {
    grid-template-columns: 1fr;
  }
}
</style>
