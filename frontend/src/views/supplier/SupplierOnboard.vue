<template>
  <div class="onboard-page">
    <div class="content-card">
      <div class="card-header">
        <div>
          <h3>供应商资料提交</h3>
          <p class="header-desc">绑定已有供应商或创建新供应商入驻，资料与附件统一在此页面提交。</p>
        </div>
        <el-tag v-if="profile.id" :type="statusTagType">{{ statusText }}</el-tag>
      </div>

      <el-alert
        v-if="profile.id"
        type="info"
        :closable="false"
        show-icon
        class="page-alert"
        :title="profileAlertText"
      />

      <el-alert
        v-if="profile.review_comment"
        type="warning"
        :closable="false"
        show-icon
        class="page-alert"
        :title="`采购审核意见：${profile.review_comment}`"
      />

      <div v-if="!profile.id && activeTab === 'onboard'" class="template-box">
        <div class="template-text">
          <div class="template-title">供应商调查表</div>
          <div class="template-desc">请先下载调查表模板，填写完成后和营业执照、资质文件等一起上传。</div>
        </div>
        <el-button type="primary" plain :loading="downloadingTemplate" @click="downloadTemplate">
          下载调查表
        </el-button>
      </div>

      <div v-if="profile.id" class="submitted-panel">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="供应商名称">{{ profile.name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="联系人">{{ profile.contact_person || '-' }}</el-descriptions-item>
          <el-descriptions-item label="手机号">{{ profile.phone || '-' }}</el-descriptions-item>
          <el-descriptions-item label="统一社会信用代码">{{ profile.social_credit_code || '-' }}</el-descriptions-item>
        </el-descriptions>

        <div class="section-title">已提交附件</div>
        <div v-if="profile.application_attachments?.length" class="attachment-list">
          <div v-for="(file, idx) in profile.application_attachments" :key="`${file.file_path || file.name}_${idx}`" class="attachment-item">
            <span>{{ file.name || file.filename || `附件${idx + 1}` }}</span>
            <el-button size="small" text type="primary" @click="openAttachment(file)">查看</el-button>
          </div>
        </div>
        <el-empty v-else description="暂无附件" :image-size="80" />
      </div>

      <el-tabs v-else v-model="activeTab" stretch>
        <el-tab-pane label="绑定已有供应商" name="bind">
          <el-form label-position="top" size="large">
            <el-form-item label="搜索公司名称或统一社会信用代码">
              <el-select
                v-model="bindSelectedId"
                filterable
                remote
                clearable
                placeholder="请输入关键词搜索"
                :remote-method="searchSuppliers"
                :loading="bindSearching"
                style="width:100%"
              >
                <el-option
                  v-for="item in bindOptions"
                  :key="item.id"
                  :label="item.name + (item.social_credit_code ? ` (${item.social_credit_code})` : '')"
                  :value="item.id"
                />
              </el-select>
            </el-form-item>

            <el-form-item label="申请岗位">
              <el-select
                v-model="sharedForm.position"
                filterable
                allow-create
                default-first-option
                placeholder="请选择或输入岗位"
                style="width:100%"
              >
                <el-option label="报价员" value="报价员" />
                <el-option label="财务" value="财务" />
                <el-option label="仓库" value="仓库" />
                <el-option label="业务联系人" value="业务联系人" />
                <el-option label="质量/技术" value="质量/技术" />
              </el-select>
            </el-form-item>

            <el-form-item label="补充说明">
              <el-input v-model="sharedForm.note" type="textarea" :rows="3" placeholder="可填写申请加入原因、联系人信息或附件说明" maxlength="500" show-word-limit />
            </el-form-item>

            <AttachmentUploader
              :files="sharedForm.attachments"
              :uploading="uploading"
              @upload="uploadAttachment"
              @remove="removeSharedAttachment"
            />
          </el-form>
          <div class="action-row">
            <el-button type="primary" :loading="bindSubmitting" :disabled="!bindSelectedId" @click="submitBind">提交绑定申请</el-button>
          </div>
        </el-tab-pane>

        <el-tab-pane label="创建新供应商入驻" name="onboard">
          <el-form ref="onboardRef" :model="onboardForm" :rules="onboardRules" label-position="top" size="large">
            <el-form-item label="公司名称" prop="company_name">
              <el-input v-model="onboardForm.company_name" placeholder="请输入公司全称" />
            </el-form-item>
            <el-form-item label="统一社会信用代码" prop="social_credit_code">
              <el-input v-model="onboardForm.social_credit_code" placeholder="请输入统一社会信用代码（选填）" />
            </el-form-item>
            <el-form-item label="联系人" prop="contact_person">
              <el-input v-model="onboardForm.contact_person" placeholder="请输入联系人姓名" />
            </el-form-item>
            <el-form-item label="联系电话" prop="phone">
              <el-input v-model="onboardForm.phone" maxlength="11" placeholder="请输入联系电话" />
            </el-form-item>
            <el-form-item label="电子邮箱" prop="email">
              <el-input v-model="onboardForm.email" placeholder="请输入电子邮箱（选填）" />
            </el-form-item>
            <el-form-item label="补充说明">
              <el-input v-model="onboardForm.onboarding_note" type="textarea" :rows="3" placeholder="可填写主营业务、合作背景或附件说明" maxlength="500" show-word-limit />
            </el-form-item>

            <AttachmentUploader
              :files="onboardForm.attachments"
              :uploading="uploading"
              @upload="uploadAttachment"
              @remove="removeOnboardAttachment"
            />
          </el-form>
          <div class="action-row">
            <el-button type="primary" :loading="onboardSubmitting" @click="submitOnboard">提交入驻申请</el-button>
          </div>
        </el-tab-pane>
      </el-tabs>
    </div>
  </div>
</template>

<script setup>
import { computed, defineComponent, h, onMounted, reactive, ref } from 'vue'
import { ElButton, ElFormItem, ElMessage, ElUpload } from 'element-plus'
import { useRouter } from 'vue-router'
import api, { resolveAssetUrl } from '../../api'

const AttachmentUploader = defineComponent({
  name: 'AttachmentUploader',
  props: {
    files: { type: Array, default: () => [] },
    uploading: { type: Boolean, default: false },
  },
  emits: ['upload', 'remove'],
  setup(props, { emit }) {
    return () => h(ElFormItem, { label: '资质附件' }, () => [
      h(ElUpload, {
        httpRequest: (options) => emit('upload', options),
        showFileList: false,
        accept: '.pdf,.jpg,.jpeg,.png,.doc,.docx,.xls,.xlsx,.zip,.rar,.7z,.tar,.gz,.bz2,.xz',
        multiple: true,
      }, () => h(ElButton, { type: 'primary', plain: true, loading: props.uploading }, () => '选择并上传附件')),
      props.files.length
        ? h('div', { class: 'attachment-list' }, props.files.map((file, idx) => (
            h('div', { class: 'attachment-item', key: `${file.file_path || file.name}_${idx}` }, [
              h('span', file.name || file.filename || `附件${idx + 1}`),
              h(ElButton, { size: 'small', text: true, type: 'danger', onClick: () => emit('remove', idx) }, () => '删除'),
            ])
          )))
        : h('div', { class: 'upload-tip' }, '支持图片、PDF、Word、Excel 和压缩包，可一次选择多个附件。'),
    ])
  },
})

const router = useRouter()

const activeTab = ref('bind')
const bindSelectedId = ref(null)
const bindSearching = ref(false)
const bindSubmitting = ref(false)
const bindOptions = ref([])
const onboardRef = ref(null)
const onboardSubmitting = ref(false)
const uploading = ref(false)
const downloadingTemplate = ref(false)

const profile = ref({})

const sharedForm = reactive({
  position: '',
  note: '',
  attachments: [],
})

const onboardForm = reactive({
  company_name: '',
  social_credit_code: '',
  contact_person: '',
  phone: '',
  email: '',
  onboarding_note: '',
  attachments: [],
})

const statusText = computed(() => ({ pending: '待审核', approved: '已入库', rejected: '已拒绝' }[profile.value.status] || '待处理'))
const statusTagType = computed(() => ({ pending: 'warning', approved: 'success', rejected: 'danger' }[profile.value.status] || 'info'))
const profileAlertText = computed(() => {
  if (profile.value.status === 'approved') return '供应商已审核通过，可进入询价与资料管理。'
  if (profile.value.status === 'rejected') return '供应商申请未通过，请根据审核意见重新提交资料。'
  return '申请和附件已提交，正在等待采购审核。请勿重复申请，审核通过后即可进入供应商业务页面。'
})

const phoneValidator = (_, value, callback) => {
  if (!value) { callback(); return }
  if (!/^1[3-9]\d{9}$/.test(String(value).trim())) callback(new Error('请输入有效的手机号'))
  else callback()
}

const onboardRules = {
  company_name: [{ required: true, message: '请输入公司名称', trigger: 'blur' }],
  contact_person: [{ required: true, message: '请输入联系人', trigger: 'blur' }],
  phone: [{ validator: phoneValidator, trigger: 'blur' }],
  email: [{ type: 'email', message: '请输入有效的邮箱地址', trigger: 'blur' }],
}

const fetchProfile = async () => {
  try {
    const { data } = await api.get('/supplier/my-profile', { silentError: true })
    profile.value = data || {}
    if (data?.status) localStorage.setItem('supplier_status', data.status)
    if (data?.member_status) localStorage.setItem('member_status', data.member_status)
    if (data?.status === 'approved' && data?.member_status === 'active') {
      localStorage.setItem('bound_status', 'bound')
    } else {
      localStorage.setItem('bound_status', 'pending_review')
    }
  } catch {
    profile.value = {}
  }
}

const searchSuppliers = async (keyword) => {
  if (!keyword) { bindOptions.value = []; return }
  bindSearching.value = true
  try {
    const { data } = await api.get('/auth/supplier/companies/search', { params: { keyword } })
    bindOptions.value = data || []
  } catch {
    bindOptions.value = []
  } finally {
    bindSearching.value = false
  }
}

const submitBind = async () => {
  if (!bindSelectedId.value) return
  bindSubmitting.value = true
  try {
    const { data } = await api.post('/auth/supplier/bind-supplier', {
      supplier_id: bindSelectedId.value,
      position: sharedForm.position || null,
      application_note: sharedForm.note || null,
      attachments: sharedForm.attachments,
    })
    ElMessage.success(data.message || '绑定申请已提交，请等待审核')
    localStorage.setItem('bound_status', 'pending_review')
    await fetchProfile()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '绑定失败')
  } finally {
    bindSubmitting.value = false
  }
}

const uploadAttachment = async (options) => {
  const targetFiles = activeTab.value === 'bind' ? sharedForm.attachments : onboardForm.attachments
  const formData = new FormData()
  formData.append('file', options.file)
  uploading.value = true
  try {
    const res = await api.post('/auth/supplier/upload-attachment', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    targetFiles.push({
      name: res.data.name,
      file_path: res.data.file_path,
      preview_file_path: res.data.preview_file_path,
      size: res.data.size,
      uploaded_at: res.data.uploaded_at,
    })
    ElMessage.success('附件上传成功')
    options.onSuccess?.(res.data)
  } catch (e) {
    options.onError?.(e)
    ElMessage.error(e.response?.data?.detail || '附件上传失败')
  } finally {
    uploading.value = false
  }
}

const removeSharedAttachment = (idx) => {
  sharedForm.attachments.splice(idx, 1)
}

const removeOnboardAttachment = (idx) => {
  onboardForm.attachments.splice(idx, 1)
}

const downloadTemplate = async () => {
  downloadingTemplate.value = true
  try {
    const response = await api.get('/supplier/onboarding-template', { responseType: 'blob' })
    const blob = new Blob([response.data], { type: response.data?.type || 'application/octet-stream' })
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = '供应商调查表.doc'
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '调查表下载失败')
  } finally {
    downloadingTemplate.value = false
  }
}

const submitOnboard = async () => {
  const valid = await onboardRef.value?.validate().catch(() => false)
  if (!valid) return

  onboardSubmitting.value = true
  try {
    const { data } = await api.post('/auth/supplier/onboard-logged-in', {
      company_name: onboardForm.company_name,
      social_credit_code: onboardForm.social_credit_code || null,
      contact_person: onboardForm.contact_person,
      phone: onboardForm.phone || null,
      email: onboardForm.email || null,
      onboarding_note: onboardForm.onboarding_note || null,
      attachments: onboardForm.attachments,
    })
    ElMessage.success(data.message || '入驻申请已提交，请等待审核')
    localStorage.setItem('bound_status', 'pending_review')
    localStorage.setItem('supplier_status', 'pending')
    await fetchProfile()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '提交失败')
  } finally {
    onboardSubmitting.value = false
  }
}

const openAttachment = (file) => {
  const downloadTarget = resolveAssetUrl(file.file_path || file.url || file.path)
  const previewTarget = resolveAssetUrl(file.preview_file_path || downloadTarget)
  if (!downloadTarget) {
    ElMessage.warning('附件地址不存在')
    return
  }
  window.open(previewTarget || downloadTarget, '_blank')
}

onMounted(fetchProfile)
</script>

<style scoped>
.onboard-page {
  padding: 24px;
}

.content-card {
  background: #fff;
  border-radius: 8px;
  padding: 24px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
  max-width: 760px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
  margin-bottom: 20px;
}

.card-header h3 {
  font-size: 18px;
  color: #303133;
  margin: 0;
}

.header-desc {
  margin: 8px 0 0;
  color: #606266;
  font-size: 13px;
}

.page-alert {
  margin-bottom: 16px;
}

.template-box {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: center;
  padding: 14px 16px;
  margin-bottom: 18px;
  background: #f5f7fa;
  border-radius: 8px;
}

.template-title {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
}

.template-desc {
  margin-top: 4px;
  font-size: 12px;
  color: #606266;
}

.submitted-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.section-title {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
}

.action-row {
  margin-top: 20px;
}

.attachment-list {
  margin-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
}

.attachment-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 8px 12px;
  background: #f5f7fa;
  border-radius: 6px;
  font-size: 13px;
}

.attachment-item span {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.upload-tip {
  margin-top: 8px;
  color: #909399;
  font-size: 12px;
}

@media (max-width: 640px) {
  .template-box {
    align-items: stretch;
    flex-direction: column;
  }
}
</style>
