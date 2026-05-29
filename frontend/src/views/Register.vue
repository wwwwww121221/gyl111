<template>
  <div class="register-page">
    <div class="register-card">
      <div class="header">
        <h2>注册账号</h2>
        <p>注册成功后即可登录系统，在系统内完成供应商绑定或入驻。</p>
      </div>

      <div v-if="showWechatBindEntry" class="wechat-bind-entry">
        <span class="wechat-bind-copy">当前页面未带微信身份，请从公众号底部菜单重新获取注册或登录链接。</span>
        <div class="wechat-bind-actions">
          <el-button type="success" plain @click="startWechatBind">查看操作提示</el-button>
        </div>
      </div>

      <el-alert
        v-if="wechatHint"
        :title="wechatHint"
        type="warning"
        :closable="false"
        show-icon
        class="form-alert"
      />

      <el-form ref="formRef" :model="form" :rules="rules" label-position="top" size="large">
        <el-form-item label="手机号" prop="phone">
          <el-input v-model="form.phone" maxlength="11" placeholder="请输入手机号" autocomplete="tel">
            <template #append>
              <el-button :disabled="countdown > 0 || smsSending" @click="sendCode">
                {{ countdown > 0 ? `${countdown}s` : '获取验证码' }}
              </el-button>
            </template>
          </el-input>
        </el-form-item>

        <el-form-item label="验证码" prop="sms_code">
          <el-input v-model="form.sms_code" maxlength="6" placeholder="请输入验证码" autocomplete="off" />
        </el-form-item>

        <el-form-item label="登录密码" prop="password">
          <el-input
            v-model="form.password"
            type="password"
            show-password
            placeholder="至少 6 位"
            autocomplete="new-password"
          />
        </el-form-item>

        <el-form-item label="确认密码" prop="confirm_password">
          <el-input
            v-model="form.confirm_password"
            type="password"
            show-password
            placeholder="请再次输入密码"
            autocomplete="new-password"
          />
        </el-form-item>

        <el-button type="primary" class="submit-btn" :loading="submitting" @click="submitRegister">
          注 册
        </el-button>
      </el-form>

      <div class="bottom-link">
        <span class="footer-text">已有账号？</span>
        <el-button link type="primary" @click="pushWithOpenid('/login')">返回登录</el-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '../api'

const router = useRouter()
const route = useRoute()

const getOpenid = () => String(route.query.openid || '').trim()
const pushWithOpenid = (path) => {
  const openid = getOpenid()
  router.push(openid ? { path, query: { openid } } : { path })
}

const hasOpenid = () => Boolean(getOpenid())
const isWechatBrowser = computed(() => /micromessenger/i.test(window.navigator.userAgent || ''))
const showWechatBindEntry = computed(() => isWechatBrowser.value && !hasOpenid())
const wechatHint = ref('')

const startWechatBind = () => {
  ElMessage.warning('请回到公众号聊天页，点击底部菜单获取带微信身份的登录/注册链接。')
}

const formRef = ref(null)
const smsSending = ref(false)
const submitting = ref(false)
const countdown = ref(0)
let timer = null

const form = reactive({
  phone: '',
  sms_code: '',
  password: '',
  confirm_password: '',
})

const phoneValidator = (_, value, callback) => {
  if (!/^1[3-9]\d{9}$/.test(String(value || '').trim())) {
    callback(new Error('请输入有效的 11 位手机号'))
    return
  }
  callback()
}

const confirmPasswordValidator = (_, value, callback) => {
  if (!value) callback(new Error('请再次输入密码'))
  else if (value !== form.password) callback(new Error('两次密码不一致'))
  else callback()
}

const rules = {
  phone: [{ required: true, validator: phoneValidator, trigger: 'blur' }],
  sms_code: [{ required: true, message: '请输入验证码', trigger: 'blur' }],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '至少 6 位', trigger: 'blur' },
  ],
  confirm_password: [{ required: true, validator: confirmPasswordValidator, trigger: 'blur' }],
}

const startCountdown = () => {
  countdown.value = 60
  timer = setInterval(() => {
    countdown.value -= 1
    if (countdown.value <= 0) {
      clearInterval(timer)
      timer = null
    }
  }, 1000)
}

const sendCode = async () => {
  const valid = await formRef.value?.validateField('phone').then(() => true).catch(() => false)
  if (!valid) return

  smsSending.value = true
  try {
    const res = await api.post(
      '/auth/supplier/send-sms-code',
      { phone: form.phone, scene: 'register' },
      { silentError: true },
    )
    if (res.data?.debug_code) ElMessage.info(`调试验证码：${res.data.debug_code}`)
    ElMessage.success(res.data.message || '验证码已发送')
    startCountdown()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '发送失败')
  } finally {
    smsSending.value = false
  }
}

const submitRegister = async () => {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    await api.post(
      '/auth/supplier/register',
      {
        phone: form.phone,
        sms_code: form.sms_code,
        password: form.password,
        openid: getOpenid() || undefined,
      },
      { silentError: true },
    )
    ElMessage.success('注册成功，请登录')
    pushWithOpenid('/login')
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '注册失败')
  } finally {
    submitting.value = false
  }
}

onBeforeUnmount(() => {
  if (timer) clearInterval(timer)
})

onMounted(() => {
  const wechatError = String(route.query.wechat_error || '').trim()
  if (wechatError) wechatHint.value = wechatError
})
</script>

<style scoped>
.register-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f0f2f5;
  padding: 20px;
}

.register-card {
  width: min(420px, 100%);
  background: #fff;
  border-radius: 12px;
  padding: 36px 32px 28px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
}

.header {
  text-align: center;
  margin-bottom: 28px;
}

.header h2 {
  margin: 0;
  font-size: 22px;
  font-weight: 700;
  color: #1a1a1a;
}

.header p {
  margin: 8px 0 0;
  color: #999;
  font-size: 13px;
}

.form-alert {
  margin-bottom: 20px;
}

.wechat-bind-entry {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 20px;
  padding: 14px 16px;
  border-radius: 14px;
  background: #f0fdf4;
  border: 1px solid #bbf7d0;
}

.wechat-bind-copy {
  color: #166534;
  line-height: 1.6;
}

.wechat-bind-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.submit-btn {
  width: 100%;
  height: 42px;
  border-radius: 8px;
  font-size: 15px;
  font-weight: 600;
}

.bottom-link {
  text-align: center;
  margin-top: 20px;
  padding-top: 18px;
  border-top: 1px solid #f0f0f0;
}

.footer-text {
  font-size: 13px;
  color: #999;
}

@media (max-width: 480px) {
  .register-card {
    padding: 24px 20px 20px;
  }
}
</style>
