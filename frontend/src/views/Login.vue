<template>
  <div class="login-page">
    <section class="hero-panel">
      <div class="hero-inner">
        <div class="brand-row">
          <div class="brand-mark">SCM</div>
          <div class="brand-name">JULAN</div>
        </div>
        <h1>供应商协同平台</h1>
        <p>统一的供应商登录入口，支持密码登录、短信验证码登录，以及手机号验证码找回密码。</p>
      </div>
    </section>

    <section class="auth-panel">
      <div class="auth-card">
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

        <div v-if="!isInternalMode" class="mode-links">
          <button
            type="button"
            class="mode-link"
            :class="{ active: activeTab === 'supplier-password' }"
            @click="activeTab = 'supplier-password'"
          >
            密码登录
          </button>
          <span class="mode-divider">|</span>
          <button
            type="button"
            class="mode-link"
            :class="{ active: activeTab === 'supplier-sms' }"
            @click="activeTab = 'supplier-sms'"
          >
            验证码登录
          </button>
        </div>

        <el-form
          v-show="activeTab === 'supplier-password'"
          ref="supplierPasswordRef"
          :model="supplierPasswordForm"
          :rules="supplierPasswordRules"
          label-position="top"
        >
          <el-form-item label="手机号" prop="phone">
            <el-input
              v-model="supplierPasswordForm.phone"
              maxlength="11"
              placeholder="请输入手机号"
              autocomplete="tel"
            />
          </el-form-item>

          <el-form-item label="密码" prop="password">
            <el-input
              v-model="supplierPasswordForm.password"
              type="password"
              show-password
              placeholder="请输入密码"
              autocomplete="current-password"
              @keyup.enter="handleSupplierPasswordLogin"
            />
          </el-form-item>

          <div class="helper-row">
            <el-button link type="primary" @click="openResetDialog">忘记密码？</el-button>
          </div>

          <el-button type="primary" class="submit-btn" :loading="loading" @click="handleSupplierPasswordLogin">
            登录供应商端
          </el-button>
        </el-form>

        <el-form
          v-show="activeTab === 'supplier-sms'"
          ref="supplierSmsRef"
          :model="supplierSmsForm"
          :rules="supplierSmsRules"
          label-position="top"
        >
          <el-form-item label="手机号" prop="phone">
            <el-input
              v-model="supplierSmsForm.phone"
              maxlength="11"
              placeholder="请输入手机号"
              autocomplete="tel"
            >
              <template #append>
                <el-button :disabled="smsCountdown > 0 || smsSending" @click="sendLoginSmsCode">
                  {{ smsCountdown > 0 ? `${smsCountdown}s` : '获取验证码' }}
                </el-button>
              </template>
            </el-input>
          </el-form-item>

          <el-form-item label="验证码" prop="sms_code">
            <el-input
              v-model="supplierSmsForm.sms_code"
              maxlength="6"
              placeholder="请输入验证码"
              autocomplete="off"
              @keyup.enter="handleSupplierSmsLogin"
            />
          </el-form-item>

          <el-button type="primary" class="submit-btn" :loading="loading" @click="handleSupplierSmsLogin">
            登录供应商端
          </el-button>
        </el-form>

        <el-form
          v-show="activeTab === 'internal'"
          ref="internalRef"
          :model="internalForm"
          :rules="internalRules"
          label-position="top"
        >
          <el-form-item label="登录账号" prop="username">
            <el-input
              v-model="internalForm.username"
              placeholder="请输入登录账号"
              autocomplete="username"
            />
          </el-form-item>

          <el-form-item label="密码" prop="password">
            <el-input
              v-model="internalForm.password"
              type="password"
              show-password
              placeholder="请输入密码"
              autocomplete="current-password"
              @keyup.enter="handleInternalLogin"
            />
          </el-form-item>

          <el-button type="primary" class="submit-btn" :loading="loading" @click="handleInternalLogin">
            登录后台
          </el-button>
        </el-form>

        <div class="footer-actions">
          <el-button link type="primary" @click="router.push('/register')">
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
import axios from 'axios'
import api from '../api'

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

const getOpenid = () => String(route.query.openid || '').trim()

const persistLogin = (payload, fallbackUsername = '') => {
  localStorage.setItem('token', payload.access_token || '')
  localStorage.setItem('role', payload.role || '')
  localStorage.setItem('department', payload.department || '')
  localStorage.setItem('username', payload.username || fallbackUsername)
  localStorage.setItem('supplier_id', payload.supplier_id ? String(payload.supplier_id) : '')
  localStorage.setItem('supplier_name', payload.supplier_name || '')
}

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

const sendSceneCode = async (phone, scene) => {
  await api.post('/auth/supplier/send-sms-code', { phone, scene })
}

const sendLoginSmsCode = async () => {
  const valid = await supplierSmsRef.value?.validateField('phone').then(() => true).catch(() => false)
  if (!valid) return

  smsSending.value = true
  try {
    await sendSceneCode(supplierSmsForm.phone, 'login')
    ElMessage.success('验证码已发送')
    startCountdown(smsCountdown)
  } finally {
    smsSending.value = false
  }
}

const sendResetSmsCode = async () => {
  const valid = await resetRef.value?.validateField('phone').then(() => true).catch(() => false)
  if (!valid) return

  resetSmsSending.value = true
  try {
    await sendSceneCode(resetForm.phone, 'reset_password')
    ElMessage.success('验证码已发送')
    startCountdown(resetCountdown)
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
    router.push('/supplier/inquiries')
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
    router.push('/supplier/inquiries')
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

    const { data } = await axios.post('/api/auth/login', formData, {
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
    })

    persistLogin(data, internalForm.username)
    ElMessage.success('登录成功')
    router.push(data.role === 'supplier' ? '/supplier/inquiries' : '/dashboard')
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
    const { data } = await api.post('/auth/supplier/wechat-login', { openid })
    if (data?.bound && data?.access_token) {
      persistLogin(data)
      ElMessage.success('微信登录成功')
      router.push('/supplier/inquiries')
      return
    }

    wechatHint.value = data?.message || '请先绑定手机号后再使用微信登录。'
    activeTab.value = 'supplier-password'
  } catch (error) {
    wechatHint.value = error.response?.data?.detail || '微信登录校验失败，请改用手机号登录。'
    activeTab.value = 'supplier-password'
  }
}

onMounted(() => {
  tryWechatDirectLogin()
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
  grid-template-columns: minmax(0, 1.5fr) minmax(420px, 0.85fr);
  background:
    linear-gradient(90deg, #2f5cff 0%, #2f5cff 58%, #f5f7fb 58%, #f5f7fb 100%);
}

.hero-panel {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 48px;
}

.hero-inner {
  width: min(560px, 100%);
  color: #ffffff;
}

.brand-row {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 40px;
}

.brand-mark {
  width: 58px;
  height: 58px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.12);
  border: 1px solid rgba(255, 255, 255, 0.18);
  font-size: 18px;
  font-weight: 800;
  letter-spacing: 1px;
}

.brand-name {
  font-size: 28px;
  font-weight: 700;
  letter-spacing: 6px;
}

.hero-inner h1 {
  margin: 0 0 18px;
  font-size: clamp(42px, 5vw, 72px);
  line-height: 1.08;
  font-weight: 800;
}

.hero-inner p {
  margin: 0;
  max-width: 440px;
  font-size: 19px;
  line-height: 1.8;
  color: rgba(255, 255, 255, 0.92);
}

.auth-panel {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 48px 28px;
}

.auth-card {
  width: min(520px, 100%);
  background: #ffffff;
  border-radius: 24px;
  padding: 40px;
  border: 1px solid rgba(15, 23, 42, 0.06);
  box-shadow: 0 20px 48px rgba(46, 78, 170, 0.12);
}

.auth-header h2 {
  margin: 0;
  color: #16213a;
  font-size: 28px;
  font-weight: 800;
}

.auth-header p {
  margin: 10px 0 0;
  color: #64748b;
  font-size: 16px;
  line-height: 1.6;
}

.wechat-alert {
  margin-top: 18px;
}

.mode-links {
  margin: 22px 0 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #94a3b8;
}

.mode-link {
  border: none;
  background: transparent;
  color: #64748b;
  font-size: 15px;
  cursor: pointer;
  padding: 0;
}

.mode-link.active {
  color: #2f5cff;
  font-weight: 700;
}

.mode-divider {
  margin: 0 10px;
}

.helper-row {
  display: flex;
  justify-content: flex-end;
  margin-top: -10px;
  margin-bottom: 14px;
}

.submit-btn {
  width: 100%;
  height: 54px;
  margin-top: 8px;
  border-radius: 14px;
  font-size: 18px;
  font-weight: 700;
  box-shadow: 0 12px 24px rgba(47, 92, 255, 0.18);
}

.footer-actions {
  margin-top: 20px;
  display: flex;
  justify-content: center;
  gap: 14px;
  flex-wrap: wrap;
}

@media (max-width: 980px) {
  .login-page {
    grid-template-columns: 1fr;
    background: linear-gradient(180deg, #2f5cff 0%, #2f5cff 34%, #f5f7fb 34%, #f5f7fb 100%);
  }

  .hero-panel {
    justify-content: flex-start;
    padding: 40px 24px 16px;
  }

  .brand-row {
    margin-bottom: 24px;
  }

  .hero-inner h1 {
    font-size: 38px;
  }

  .hero-inner p {
    max-width: none;
    font-size: 16px;
  }

  .auth-panel {
    padding: 12px 18px 28px;
  }

  .auth-card {
    padding: 28px 22px 24px;
    border-radius: 20px;
  }
}
</style>
