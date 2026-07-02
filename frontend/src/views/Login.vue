<template>
  <div class="login-page">
    <div class="left-panel">
      <div class="brand-area">
        <div class="brand-tag">SCM</div>
        <h1 class="brand-title">供应链<br>协同平台</h1>
        <p class="brand-desc">统一的供应商登录入口，支持密码登录、短信验证码登录，以及手机号验证找回密码。</p>
      </div>
    </div>

    <div class="right-panel">
      <div class="login-card">
        <h2 class="card-title">{{ loginMode === 'supplier' ? '供应商登录' : '内部人员登录' }}</h2>
        <p class="card-subtitle">{{ loginMode === 'supplier' ? '请选择密码登录或验证码登录' : '请选择密码登录或验证码登录' }}</p>

        <div class="mode-switch">
          <button
            type="button"
            class="mode-btn"
            :class="{ active: loginMode === 'supplier' }"
            @click="loginMode = 'supplier'"
          >供应商登录</button>
          <button
            type="button"
            class="mode-btn"
            :class="{ active: loginMode === 'internal' }"
            @click="loginMode = 'internal'"
          >内部人员登录</button>
        </div>

        <transition name="fade" mode="out-in">
          <div v-if="loginMode === 'supplier'" key="supplier" class="form-area">
            <div class="sub-tabs">
              <button
                type="button"
                class="sub-tab"
                :class="{ active: activeTab === 'password' }"
                @click="activeTab = 'password'"
              >密码登录</button>
              <button
                type="button"
                class="sub-tab"
                :class="{ active: activeTab === 'sms' }"
                @click="activeTab = 'sms'"
              >验证码登录</button>
            </div>

            <el-form
              v-if="activeTab === 'password'"
              key="sp"
              ref="supplierPasswordRef"
              :model="supplierForm"
              :rules="supplierRules"
              label-position="top"
              size="large"
            >
              <el-form-item label="手机号" prop="phone">
                <el-input v-model="supplierForm.phone" maxlength="11" placeholder="请输入手机号" autocomplete="tel" />
              </el-form-item>
              <el-form-item label="密码" prop="password">
                <el-input v-model="supplierForm.password" type="password" show-password placeholder="请输入密码" autocomplete="current-password" @keyup.enter="handleSupplierLogin('password')" />
              </el-form-item>
              <div class="form-extra">
                <el-button link type="primary" @click="openResetDialog">忘记密码？</el-button>
              </div>
              <el-button type="primary" class="submit-btn" :loading="loading" @click="handleSupplierLogin('password')">登 录</el-button>
            </el-form>

            <el-form
              v-else
              key="ss"
              ref="supplierSmsRef"
              :model="smsForm"
              :rules="smsRules"
              label-position="top"
              size="large"
            >
              <el-form-item label="手机号" prop="phone">
                <el-input v-model="smsForm.phone" maxlength="11" placeholder="请输入手机号" autocomplete="tel" />
              </el-form-item>
              <el-form-item label="验证码" prop="sms_code">
                <div class="sms-row">
                  <el-input v-model="smsForm.sms_code" maxlength="6" placeholder="请输入验证码" @keyup.enter="handleSupplierLogin('sms')" />
                  <el-button class="sms-send-btn" :disabled="smsCountdown > 0 || smsSending" @click="sendLoginSms">
                    {{ smsCountdown > 0 ? `${smsCountdown}s` : '获取验证码' }}
                  </el-button>
                </div>
              </el-form-item>
              <el-button type="primary" class="submit-btn" :loading="loading" @click="handleSupplierLogin('sms')">登 录</el-button>
            </el-form>
          </div>

          <div v-else key="internal" class="form-area">
            <div class="sub-tabs">
              <button
                type="button"
                class="sub-tab"
                :class="{ active: internalTab === 'password' }"
                @click="internalTab = 'password'"
              >密码登录</button>
              <button
                type="button"
                class="sub-tab"
                :class="{ active: internalTab === 'sms' }"
                @click="internalTab = 'sms'"
              >验证码登录</button>
            </div>

            <el-form
              v-if="internalTab === 'password'"
              key="ip"
              ref="internalRef"
              :model="internalForm"
              :rules="internalRules"
              label-position="top"
              size="large"
            >
              <el-form-item label="账号" prop="username">
                <el-input v-model="internalForm.username" placeholder="请输入登录账号" autocomplete="username" />
              </el-form-item>
              <el-form-item label="密码" prop="password">
                <el-input v-model="internalForm.password" type="password" show-password placeholder="请输入密码" autocomplete="current-password" @keyup.enter="handleInternalLogin" />
              </el-form-item>
              <div class="form-extra">
                <el-button link type="primary" @click="openInternalResetDialog">忘记密码？</el-button>
              </div>
              <el-button type="primary" class="submit-btn" :loading="loading" @click="handleInternalLogin">登 录</el-button>
            </el-form>

            <el-form
              v-else
              key="is"
              ref="internalSmsRef"
              :model="internalSmsForm"
              :rules="internalSmsRules"
              label-position="top"
              size="large"
            >
              <el-form-item label="手机号" prop="phone">
                <el-input v-model="internalSmsForm.phone" maxlength="11" placeholder="请输入手机号" autocomplete="tel" />
              </el-form-item>
              <el-form-item label="验证码" prop="sms_code">
                <div class="sms-row">
                  <el-input v-model="internalSmsForm.sms_code" maxlength="6" placeholder="请输入验证码" @keyup.enter="handleInternalSmsLogin" />
                  <el-button class="sms-send-btn" :disabled="internalSmsCountdown > 0 || internalSmsSending" @click="sendInternalSms">
                    {{ internalSmsCountdown > 0 ? `${internalSmsCountdown}s` : '获取验证码' }}
                  </el-button>
                </div>
              </el-form-item>
              <el-button type="primary" class="submit-btn" :loading="loading" @click="handleInternalSmsLogin">登 录</el-button>
            </el-form>
          </div>
        </transition>

        <div v-if="loginMode === 'supplier'" class="card-footer">
          <span class="footer-text">还没有账号？</span>
          <el-button link type="primary" @click="goRegister">注册新账号</el-button>
        </div>
      </div>
    </div>

    <el-dialog v-model="resetDialogVisible" :title="resetMode === 'internal' ? '内部人员找回密码' : '找回密码'" width="400px" destroy-on-close>
      <el-form ref="resetRef" :model="resetForm" :rules="resetRules" label-position="top" size="large">
        <el-form-item label="手机号" prop="phone">
          <el-input v-model="resetForm.phone" maxlength="11" placeholder="请输入手机号">
            <template #append>
              <el-button :disabled="resetCountdown > 0 || resetSmsSending" @click="sendResetSms">
                {{ resetCountdown > 0 ? `${resetCountdown}s` : '获取验证码' }}
              </el-button>
            </template>
          </el-input>
        </el-form-item>
        <el-form-item label="验证码" prop="sms_code">
          <el-input v-model="resetForm.sms_code" maxlength="6" placeholder="请输入验证码" />
        </el-form-item>
        <el-form-item label="新密码" prop="new_password">
          <el-input v-model="resetForm.new_password" type="password" show-password placeholder="至少 6 位" />
        </el-form-item>
        <el-form-item label="确认密码" prop="confirm_password">
          <el-input v-model="resetForm.confirm_password" type="password" show-password placeholder="请再次输入新密码" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="resetDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="resetSubmitting" @click="submitReset">确认重置</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '../api'

const router = useRouter()
const route = useRoute()
const getRedirectPath = () => String(route.query.redirect || '').trim()

const loginMode = ref('supplier')
const activeTab = ref('password')
const internalTab = ref('password')
const loading = ref(false)
const smsSending = ref(false)
const resetSmsSending = ref(false)
const internalSmsSending = ref(false)
const smsCountdown = ref(0)
const resetCountdown = ref(0)
const internalSmsCountdown = ref(0)
const resetDialogVisible = ref(false)
const resetSubmitting = ref(false)
const resetMode = ref('supplier')

const supplierPasswordRef = ref(null)
const supplierSmsRef = ref(null)
const internalRef = ref(null)
const internalSmsRef = ref(null)
const resetRef = ref(null)

let smsTimer = null
let resetTimer = null
let internalSmsTimer = null

const supplierForm = reactive({ phone: '', password: '' })
const smsForm = reactive({ phone: '', sms_code: '' })
const internalForm = reactive({ username: '', password: '' })
const internalSmsForm = reactive({ phone: '', sms_code: '' })
const resetForm = reactive({ phone: '', sms_code: '', new_password: '', confirm_password: '' })

const getOpenid = () => String(route.query.openid || '').trim()

const resolvePostLoginRoute = () => {
  const redirect = getRedirectPath()
  return redirect || '/'
}

const goRegister = () => {
  const openid = getOpenid()
  router.push(openid ? { path: '/register', query: { openid } } : { path: '/register' })
}

const phoneValidator = (_, value, callback) => {
  if (!/^1[3-9]\d{9}$/.test(String(value || '').trim())) callback(new Error('请输入有效的手机号'))
  else callback()
}

const confirmPasswordValidator = (_, value, callback) => {
  if (!value) callback(new Error('请再次输入新密码'))
  else if (value !== resetForm.new_password) callback(new Error('两次密码不一致'))
  else callback()
}

const supplierRules = {
  phone: [{ required: true, validator: phoneValidator, trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}
const smsRules = {
  phone: [{ required: true, validator: phoneValidator, trigger: 'blur' }],
  sms_code: [{ required: true, message: '请输入验证码', trigger: 'blur' }],
}
const internalRules = {
  username: [{ required: true, message: '请输入账号', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}
const internalSmsRules = {
  phone: [{ required: true, validator: phoneValidator, trigger: 'blur' }],
  sms_code: [{ required: true, message: '请输入验证码', trigger: 'blur' }],
}
const resetRules = {
  phone: [{ required: true, validator: phoneValidator, trigger: 'blur' }],
  sms_code: [{ required: true, message: '请输入验证码', trigger: 'blur' }],
  new_password: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 6, message: '至少 6 位', trigger: 'blur' },
  ],
  confirm_password: [{ required: true, validator: confirmPasswordValidator, trigger: 'blur' }],
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
  if (payload.bound_status) localStorage.setItem('bound_status', payload.bound_status)
  else localStorage.removeItem('bound_status')
  window.dispatchEvent(new Event('auth-changed'))
}

const startCountdown = (target) => {
  target.value = 60
  const timer = setInterval(() => {
    target.value -= 1
    if (target.value <= 0) {
      clearInterval(timer)
      if (target === smsCountdown) smsTimer = null
      else if (target === resetCountdown) resetTimer = null
      else if (target === internalSmsCountdown) internalSmsTimer = null
    }
  }, 1000)
  if (target === smsCountdown) { if (smsTimer) clearInterval(smsTimer); smsTimer = timer }
  else if (target === resetCountdown) { if (resetTimer) clearInterval(resetTimer); resetTimer = timer }
  else if (target === internalSmsCountdown) { if (internalSmsTimer) clearInterval(internalSmsTimer); internalSmsTimer = timer }
}

const sendSceneCode = async (phone, scene) => {
  const { data } = await api.post('/auth/supplier/send-sms-code', { phone, scene })
  if (data?.debug_code) ElMessage.info(`调试验证码：${data.debug_code}`)
  return data
}

const sendLoginSms = async () => {
  const valid = await supplierSmsRef.value?.validateField('phone').then(() => true).catch(() => false)
  if (!valid) return
  smsSending.value = true
  try {
    const data = await sendSceneCode(smsForm.phone, 'login')
    ElMessage.success(data?.message || '验证码已发送')
    startCountdown(smsCountdown)
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '发送失败')
  } finally {
    smsSending.value = false
  }
}

const sendResetSms = async () => {
  const valid = await resetRef.value?.validateField('phone').then(() => true).catch(() => false)
  if (!valid) return
  resetSmsSending.value = true
  try {
    const scene = resetMode.value === 'internal' ? 'internal_reset_password' : 'reset_password'
    const data = await sendSceneCode(resetForm.phone, scene)
    ElMessage.success(data?.message || '验证码已发送')
    startCountdown(resetCountdown)
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '发送失败')
  } finally {
    resetSmsSending.value = false
  }
}

const handleSupplierLogin = async (type) => {
  const formRef = type === 'password' ? supplierPasswordRef.value : supplierSmsRef.value
  const form = type === 'password' ? supplierForm : smsForm
  const valid = await formRef?.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  try {
    let res
    if (type === 'password') {
      res = await api.post('/auth/supplier/password-login', {
        phone: form.phone,
        password: form.password,
        openid: getOpenid() || undefined,
      })
    } else {
      res = await api.post('/auth/supplier/sms-login', {
        phone: form.phone,
        sms_code: form.sms_code,
        openid: getOpenid() || undefined,
      })
    }
    persistLogin(res.data, form.phone)
    ElMessage.success('登录成功')
    router.push(resolvePostLoginRoute())
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '登录失败')
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
    const openid = getOpenid()
    if (openid) formData.append('openid', openid)
    const { data } = await api.post('/auth/login', formData, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    })
    persistLogin(data, internalForm.username)
    ElMessage.success('登录成功')
    router.push(resolvePostLoginRoute())
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '登录失败')
  } finally {
    loading.value = false
  }
}

const sendInternalSms = async () => {
  const valid = await internalSmsRef.value?.validateField('phone').then(() => true).catch(() => false)
  if (!valid) return
  internalSmsSending.value = true
  try {
    const data = await sendSceneCode(internalSmsForm.phone, 'internal_login')
    ElMessage.success(data?.message || '验证码已发送')
    startCountdown(internalSmsCountdown)
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '发送失败')
  } finally {
    internalSmsSending.value = false
  }
}

const handleInternalSmsLogin = async () => {
  const valid = await internalSmsRef.value?.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  try {
    const { data } = await api.post('/auth/internal/sms-login', {
      phone: internalSmsForm.phone,
      sms_code: internalSmsForm.sms_code,
      openid: getOpenid() || undefined,
    })
    persistLogin(data, internalSmsForm.phone)
    ElMessage.success('登录成功')
    router.push(resolvePostLoginRoute())
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '登录失败')
  } finally {
    loading.value = false
  }
}

const openResetDialog = () => {
  resetMode.value = 'supplier'
  resetForm.phone = supplierForm.phone || smsForm.phone || ''
  resetForm.sms_code = ''
  resetForm.new_password = ''
  resetForm.confirm_password = ''
  resetDialogVisible.value = true
}

const openInternalResetDialog = () => {
  resetMode.value = 'internal'
  resetForm.phone = internalSmsForm.phone || ''
  resetForm.sms_code = ''
  resetForm.new_password = ''
  resetForm.confirm_password = ''
  resetDialogVisible.value = true
}

const submitReset = async () => {
  const valid = await resetRef.value?.validate().catch(() => false)
  if (!valid) return
  resetSubmitting.value = true
  try {
    const endpoint = resetMode.value === 'internal'
      ? '/auth/internal/reset-password'
      : '/auth/supplier/reset-password'
    await api.post(endpoint, {
      phone: resetForm.phone,
      sms_code: resetForm.sms_code,
      new_password: resetForm.new_password,
    })
    ElMessage.success('密码已重置，请使用新密码登录')
    if (resetMode.value === 'internal') {
      internalSmsForm.phone = resetForm.phone
    } else {
      supplierForm.phone = resetForm.phone
      supplierForm.password = ''
      activeTab.value = 'password'
    }
    resetDialogVisible.value = false
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '重置失败')
  } finally {
    resetSubmitting.value = false
  }
}

onBeforeUnmount(() => {
  if (smsTimer) clearInterval(smsTimer)
  if (resetTimer) clearInterval(resetTimer)
  if (internalSmsTimer) clearInterval(internalSmsTimer)
})
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
}

.left-panel {
  width: 45%;
  min-width: 320px;
  background: linear-gradient(135deg, #1a2a4a 0%, #2c4a7c 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 60px 48px;
  position: relative;
  overflow: hidden;
}

.left-panel::before {
  content: '';
  position: absolute;
  width: 400px;
  height: 400px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.04);
  top: -80px;
  right: -100px;
}

.left-panel::after {
  content: '';
  position: absolute;
  width: 300px;
  height: 300px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.03);
  bottom: -60px;
  left: -60px;
}

.brand-area {
  position: relative;
  z-index: 1;
}

.brand-tag {
  display: inline-block;
  padding: 8px 18px;
  border: 2px solid rgba(255, 255, 255, 0.35);
  border-radius: 10px;
  color: rgba(255, 255, 255, 0.85);
  font-size: 15px;
  font-weight: 700;
  letter-spacing: 3px;
  margin-bottom: 36px;
}

.brand-title {
  margin: 0;
  font-size: 44px;
  font-weight: 800;
  color: #fff;
  line-height: 1.25;
  letter-spacing: 2px;
}

.brand-desc {
  margin-top: 28px;
  font-size: 14px;
  line-height: 1.9;
  color: rgba(255, 255, 255, 0.55);
  max-width: 340px;
}

.right-panel {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px;
  background: #f5f7fa;
}

.login-card {
  width: min(420px, 100%);
  background: #fff;
  border-radius: 16px;
  padding: 40px 36px 32px;
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.06);
}

.card-title {
  margin: 0 0 6px;
  font-size: 22px;
  font-weight: 700;
  color: #1a1a2e;
}

.card-subtitle {
  margin: 0 0 24px;
  font-size: 13px;
  color: #999;
}

.mode-switch {
  display: flex;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  overflow: hidden;
  margin-bottom: 22px;
}

.mode-btn {
  flex: 1;
  border: none;
  background: transparent;
  padding: 10px 0;
  font-size: 14px;
  font-weight: 500;
  color: #666;
  cursor: pointer;
  transition: all 0.2s;
}

.mode-btn.active {
  background: #1890ff;
  color: #fff;
}

.mode-btn:not(.active):hover {
  color: #1890ff;
  background: #f0f7ff;
}

.sub-tabs {
  display: flex;
  gap: 0;
  margin-bottom: 20px;
  border-bottom: 1px solid #eee;
}

.sub-tab {
  border: none;
  background: none;
  padding: 8px 16px;
  font-size: 13px;
  color: #999;
  cursor: pointer;
  position: relative;
  transition: color 0.2s;
}

.sub-tab.active {
  color: #1890ff;
  font-weight: 600;
}

.sub-tab.active::after {
  content: '';
  position: absolute;
  bottom: -1px;
  left: 16px;
  right: 16px;
  height: 2px;
  background: #1890ff;
  border-radius: 1px;
}

.form-area {
  min-height: 200px;
}

.form-area :deep(.el-form-item__label) {
  font-size: 13px;
  font-weight: 500;
  color: #333;
}

.form-extra {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 16px;
}

.submit-btn {
  width: 100%;
  height: 42px;
  border-radius: 8px;
  font-size: 15px;
  font-weight: 600;
}

.sms-row {
  display: flex;
  gap: 10px;
}

.sms-row .el-input { flex: 1; }

.sms-send-btn {
  min-width: 110px;
  flex-shrink: 0;
}

.card-footer {
  text-align: center;
  margin-top: 20px;
  padding-top: 18px;
  border-top: 1px solid #f0f0f0;
}

.footer-text {
  font-size: 13px;
  color: #999;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

@media (max-width: 900px) {
  .left-panel {
    display: none;
  }

  .right-panel {
    padding: 20px;
  }

  .login-card {
    padding: 32px 24px 24px;
  }

  .sms-row {
    flex-direction: column;
  }

  .sms-send-btn {
    min-width: unset;
    width: 100%;
  }
}
</style>
