<template>
  <div class="register-page">
    <div class="register-card">
      <div class="header">
        <h2>供应商入驻与加入申请</h2>
        <p>首次合作请先完成基础注册；注册成功后可登录系统继续完善调查表与资质附件。</p>
      </div>

      <div v-if="showWechatBindEntry" class="wechat-bind-entry">
        <span class="wechat-bind-copy">当前页面未带微信身份，首次入驻或加入供应商前请先完成微信授权。</span>
        <div class="wechat-bind-actions">
          <el-button type="success" plain @click="startWechatBind('register')">微信授权后入驻</el-button>
          <el-button plain @click="startWechatBind('login')">微信授权后登录</el-button>
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

      <el-tabs v-model="activeTab" stretch>
        <el-tab-pane label="创建新供应商入驻" name="onboarding">
          <el-alert
            type="info"
            :closable="false"
            show-icon
            class="form-alert"
            title="此处仅填写基础信息。提交后账号状态为“审核中”，登录系统后继续完善调查表和资质附件。"
          />

          <el-form ref="onboardingRef" :model="onboardingForm" :rules="onboardingRules" label-position="top">
            <el-form-item label="公司名称" prop="company_name">
              <el-input v-model="onboardingForm.company_name" placeholder="请输入公司全称" />
            </el-form-item>

            <el-form-item label="首个联系人姓名" prop="contact_person">
              <el-input v-model="onboardingForm.contact_person" placeholder="请输入联系人姓名" />
            </el-form-item>

            <el-form-item label="手机号" prop="phone">
              <el-input v-model="onboardingForm.phone" maxlength="11" placeholder="请输入手机号" autocomplete="tel">
                <template #append>
                  <el-button :disabled="onboardingCountdown > 0 || smsSending" @click="sendOnboardingCode">
                    {{ onboardingCountdown > 0 ? `${onboardingCountdown}s` : '获取验证码' }}
                  </el-button>
                </template>
              </el-input>
            </el-form-item>

            <el-form-item label="验证码" prop="sms_code">
              <el-input v-model="onboardingForm.sms_code" maxlength="6" placeholder="请输入验证码" autocomplete="off" />
            </el-form-item>

            <el-form-item label="登录密码" prop="password">
              <el-input
                v-model="onboardingForm.password"
                type="password"
                show-password
                placeholder="至少 6 位"
                autocomplete="new-password"
              />
            </el-form-item>

            <el-button type="primary" class="submit-btn" :loading="submitting" @click="submitOnboarding">
              提交基础申请
            </el-button>
          </el-form>
        </el-tab-pane>

        <el-tab-pane label="申请加入已有供应商" name="join">
          <el-form ref="joinRef" :model="joinForm" :rules="joinRules" label-position="top">
            <el-form-item label="手机号" prop="phone">
              <el-input v-model="joinForm.phone" maxlength="11" placeholder="请输入手机号" autocomplete="tel">
                <template #append>
                  <el-button :disabled="joinCountdown > 0 || smsSending" @click="sendJoinCode">
                    {{ joinCountdown > 0 ? `${joinCountdown}s` : '获取验证码' }}
                  </el-button>
                </template>
              </el-input>
            </el-form-item>

            <el-form-item label="验证码" prop="sms_code">
              <el-input v-model="joinForm.sms_code" maxlength="6" placeholder="请输入验证码" autocomplete="off" />
            </el-form-item>

            <el-form-item label="公司名称或统一社会信用代码" prop="selected_supplier_id">
              <el-select
                v-model="joinForm.selected_supplier_id"
                filterable
                remote
                clearable
                placeholder="搜索公司名称或统一社会信用代码"
                :remote-method="searchCompanies"
                :loading="searchLoading"
                style="width: 100%;"
                @change="handleSupplierChange"
              >
                <el-option
                  v-for="item in companyOptions"
                  :key="item.id"
                  :label="`${item.name}${item.social_credit_code ? ` / ${item.social_credit_code}` : ''}`"
                  :value="item.id"
                />
              </el-select>
            </el-form-item>

            <el-form-item label="姓名" prop="member_name">
              <el-input v-model="joinForm.member_name" placeholder="请输入姓名" />
            </el-form-item>

            <el-form-item label="职位" prop="position">
              <el-select v-model="joinForm.position" placeholder="请选择职位" style="width: 100%;">
                <el-option label="仓库" value="仓库" />
                <el-option label="财务" value="财务" />
                <el-option label="报价员" value="报价员" />
              </el-select>
            </el-form-item>

            <el-form-item label="可选登录密码" prop="password">
              <el-input
                v-model="joinForm.password"
                type="password"
                show-password
                placeholder="选填；不填也可通过验证码登录"
                autocomplete="new-password"
              />
            </el-form-item>

            <el-form-item label="申请说明" prop="application_note">
              <el-input v-model="joinForm.application_note" type="textarea" :rows="3" placeholder="请输入申请加入说明" />
            </el-form-item>

            <el-form-item label="授权附件">
              <el-upload
                :http-request="uploadJoinAttachment"
                :file-list="joinFiles"
                :on-remove="removeJoinAttachment"
                :limit="5"
                accept=".pdf,.jpg,.jpeg,.png,.doc,.docx,.xls,.xlsx,.zip,.rar,.7z,.tar,.gz,.bz2,.xz"
                multiple
              >
                <el-button>上传附件</el-button>
              </el-upload>
              <div class="join-upload-tip">支持多附件和压缩包上传。</div>
            </el-form-item>

            <el-button type="primary" class="submit-btn" :loading="submitting" @click="submitJoinRequest">
              提交加入申请
            </el-button>
          </el-form>
        </el-tab-pane>
      </el-tabs>

      <div class="bottom-link">
        <el-button link type="primary" @click="pushWithOpenid('/login')">返回登录</el-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import api, { getApiOrigin } from '../api'

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

const startWechatBind = (target = 'register') => {
  const normalizedTarget = target === 'login' ? 'login' : 'register'
  window.location.href = `${getApiOrigin()}/wechat/oauth/start?target=${normalizedTarget}`
}

const activeTab = ref('onboarding')
const onboardingRef = ref(null)
const joinRef = ref(null)
const smsSending = ref(false)
const searchLoading = ref(false)
const submitting = ref(false)
const onboardingCountdown = ref(0)
const joinCountdown = ref(0)
const companyOptions = ref([])
const joinFiles = ref([])

let onboardingTimer = null
let joinTimer = null

const onboardingForm = reactive({
  company_name: '',
  contact_person: '',
  phone: '',
  sms_code: '',
  password: '',
})

const joinForm = reactive({
  phone: '',
  sms_code: '',
  selected_supplier_id: null,
  company_name: '',
  social_credit_code: '',
  member_name: '',
  position: '',
  application_note: '',
  approval_mode: 'supplier_admin',
  password: '',
})

const phoneValidator = (_, value, callback) => {
  if (!/^1[3-9]\d{9}$/.test(String(value || '').trim())) {
    callback(new Error('请输入有效的 11 位手机号'))
    return
  }
  callback()
}

const supplierValidator = (_, value, callback) => {
  if (!joinForm.selected_supplier_id) {
    callback(new Error('请选择要加入的供应商企业'))
    return
  }
  callback()
}

const onboardingRules = {
  company_name: [{ required: true, message: '请输入公司名称', trigger: 'blur' }],
  contact_person: [{ required: true, message: '请输入联系人姓名', trigger: 'blur' }],
  phone: [{ required: true, validator: phoneValidator, trigger: 'blur' }],
  sms_code: [{ required: true, message: '请输入验证码', trigger: 'blur' }],
  password: [{ required: true, min: 6, message: '密码至少 6 位', trigger: 'blur' }],
}

const joinRules = {
  phone: [{ required: true, validator: phoneValidator, trigger: 'blur' }],
  sms_code: [{ required: true, message: '请输入验证码', trigger: 'blur' }],
  selected_supplier_id: [{ required: true, validator: supplierValidator, trigger: 'change' }],
  member_name: [{ required: true, message: '请输入姓名', trigger: 'blur' }],
  position: [{ required: true, message: '请选择职位', trigger: 'change' }],
}

const startCountdown = (target) => {
  target.value = 60
  const timerRef = target === onboardingCountdown ? 'onboarding' : 'join'
  const timer = setInterval(() => {
    target.value -= 1
    if (target.value <= 0) {
      clearInterval(timer)
      if (timerRef === 'onboarding') onboardingTimer = null
      if (timerRef === 'join') joinTimer = null
    }
  }, 1000)

  if (timerRef === 'onboarding') {
    if (onboardingTimer) clearInterval(onboardingTimer)
    onboardingTimer = timer
  } else {
    if (joinTimer) clearInterval(joinTimer)
    joinTimer = timer
  }
}

const showSmsDebugIfNeeded = (data) => {
  if (data?.debug_code) {
    ElMessage.info(`调试验证码：${data.debug_code}`)
  }
}

const sendSceneCode = async (phone, scene, countdownRef) => {
  smsSending.value = true
  try {
    const res = await api.post('/auth/supplier/send-sms-code', { phone, scene })
    showSmsDebugIfNeeded(res.data)
    ElMessage.success(res.data.message || '验证码已发送')
    startCountdown(countdownRef)
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '验证码发送失败')
  } finally {
    smsSending.value = false
  }
}

const sendOnboardingCode = async () => {
  const valid = await onboardingRef.value?.validateField('phone').then(() => true).catch(() => false)
  if (!valid) return
  await sendSceneCode(onboardingForm.phone, 'onboarding', onboardingCountdown)
}

const sendJoinCode = async () => {
  const valid = await joinRef.value?.validateField('phone').then(() => true).catch(() => false)
  if (!valid) return
  await sendSceneCode(joinForm.phone, 'join', joinCountdown)
}

const uploadJoinAttachment = async (options) => {
  const formData = new FormData()
  formData.append('file', options.file)
  try {
    const res = await api.post('/auth/supplier/upload-attachment', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    joinFiles.value.push({
      name: res.data.name,
      file_path: res.data.file_path,
      preview_file_path: res.data.preview_file_path,
      size: res.data.size,
      uploaded_at: res.data.uploaded_at,
      uid: options.file.uid,
      status: 'success',
    })
    options.onSuccess?.(res.data)
  } catch (error) {
    options.onError?.(error)
    ElMessage.error(error.response?.data?.detail || '附件上传失败')
  }
}

const removeJoinAttachment = (file) => {
  joinFiles.value = joinFiles.value.filter((item) => item.uid !== file.uid && item.file_path !== file.file_path)
}

const searchCompanies = async (keyword) => {
  if (!keyword) {
    companyOptions.value = []
    return
  }
  searchLoading.value = true
  try {
    const res = await api.get('/auth/supplier/companies/search', { params: { keyword } })
    companyOptions.value = res.data || []
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '企业搜索失败')
  } finally {
    searchLoading.value = false
  }
}

const handleSupplierChange = (supplierId) => {
  const target = companyOptions.value.find((item) => item.id === supplierId)
  joinForm.company_name = target?.name || ''
  joinForm.social_credit_code = target?.social_credit_code || ''
}

const submitOnboarding = async () => {
  const valid = await onboardingRef.value?.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    await api.post('/auth/supplier/onboarding', {
      ...onboardingForm,
      openid: route.query.openid || undefined,
    })
    ElMessage.success('基础申请已提交，请登录系统继续完善调查表和资质附件')
    pushWithOpenid('/login')
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '提交失败')
  } finally {
    submitting.value = false
  }
}

const submitJoinRequest = async () => {
  const valid = await joinRef.value?.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    await api.post('/auth/supplier/join-request', {
      phone: joinForm.phone,
      sms_code: joinForm.sms_code,
      company_name: joinForm.company_name,
      social_credit_code: joinForm.social_credit_code,
      member_name: joinForm.member_name,
      position: joinForm.position,
      application_note: joinForm.application_note,
      attachments: joinFiles.value.map(({ name, file_path, size, uploaded_at }) => ({ name, file_path, size, uploaded_at })),
      approval_mode: 'supplier_admin',
      password: joinForm.password || undefined,
      openid: route.query.openid || undefined,
    })
    ElMessage.success('加入申请已提交，请等待供应商管理员审核')
    pushWithOpenid('/login')
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '提交失败')
  } finally {
    submitting.value = false
  }
}

onBeforeUnmount(() => {
  if (onboardingTimer) clearInterval(onboardingTimer)
  if (joinTimer) clearInterval(joinTimer)
})

onMounted(() => {
  const wechatError = String(route.query.wechat_error || '').trim()
  if (wechatError) {
    wechatHint.value = wechatError
  }
})
</script>

<style scoped>
.register-page {
  min-height: 100vh;
  padding: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  background:
    linear-gradient(135deg, rgba(15, 118, 110, 0.08), rgba(37, 99, 235, 0.08)),
    #f8fafc;
}

.register-card {
  width: min(860px, 100%);
  background: #ffffff;
  border-radius: 20px;
  padding: 28px 28px 20px;
  box-shadow: 0 24px 60px rgba(15, 23, 42, 0.1);
}

.header h2 {
  margin: 0;
  font-size: 28px;
  color: #0f172a;
}

.header p {
  margin: 10px 0 22px;
  color: #475569;
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

.join-upload-tip {
  margin-top: 8px;
  color: #909399;
  font-size: 12px;
}

.submit-btn {
  width: 100%;
  height: 44px;
}

.bottom-link {
  text-align: center;
  margin-top: 18px;
}

@media (max-width: 720px) {
  .register-card {
    padding: 22px 18px 18px;
  }

  .wechat-bind-entry {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
