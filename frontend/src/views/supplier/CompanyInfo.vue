<template>
  <div class="page-container">
    <div class="content-card">
      <div class="card-header">
        <div>
          <h3>供应商信息完善</h3>
          <p class="header-desc">请下载调查表模板，补充企业资料并上传完整资质附件，提交后等待采购审核。</p>
        </div>
        <div class="header-tags">
          <el-tag :type="statusTagType">{{ statusText }}</el-tag>
          <el-tag v-if="profile.role" :type="profile.role === 'owner' ? 'danger' : 'warning'" size="small">
            {{ roleText }}
          </el-tag>
        </div>
      </div>

      <el-alert
        v-if="profile.status !== 'approved'"
        type="info"
        :closable="false"
        show-icon
        class="page-alert"
        title="当前账号尚未入库，请先完善调查表和资质附件。采购审核通过后即可正式入库。"
      />

      <el-alert
        v-if="profile.review_comment"
        type="warning"
        :closable="false"
        show-icon
        class="page-alert"
        :title="`采购审核意见：${profile.review_comment}`"
      />

      <el-alert
        v-if="profile.role && !isEditor"
        type="info"
        :closable="false"
        show-icon
        class="page-alert"
        title="仅企业管理员可编辑公司信息，当前账号为只读模式。"
      />

      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-width="120px"
        :disabled="!isEditor || loading"
        class="info-form"
      >
        <div class="form-section-title">基础信息</div>

        <el-form-item label="供应商名称">
          <el-input v-model="profile.name" disabled />
        </el-form-item>

        <el-form-item label="统一社会信用代码" prop="social_credit_code">
          <el-input v-model="form.social_credit_code" placeholder="请输入统一社会信用代码" maxlength="30" />
        </el-form-item>

        <el-form-item label="简称" prop="short_name">
          <el-input v-model="form.short_name" placeholder="请输入公司简称" maxlength="50" />
        </el-form-item>

        <el-form-item label="联系人" prop="contact_person">
          <el-input v-model="form.contact_person" placeholder="请输入联系人姓名" maxlength="30" />
        </el-form-item>

        <el-form-item label="联系电话" prop="phone">
          <el-input v-model="form.phone" placeholder="请输入联系电话" maxlength="20" />
        </el-form-item>

        <el-form-item label="电子邮箱" prop="email">
          <el-input v-model="form.email" placeholder="请输入电子邮箱" maxlength="100" />
        </el-form-item>

        <div class="form-section-title">调查表与资质附件</div>

        <el-form-item label="调查表模板">
          <div class="template-box">
            <div class="template-text">
              <div class="template-title">供应商调查表</div>
              <div class="template-desc">请下载空白调查表，填写完成后与其他资质文件一并上传。</div>
            </div>
            <el-button type="primary" plain :loading="downloadingTemplate" @click="downloadTemplate">
              下载空表
            </el-button>
          </div>
        </el-form-item>

        <el-form-item label="当前附件">
          <div v-if="form.application_attachments?.length" class="attachment-list">
            <div v-for="(file, index) in form.application_attachments" :key="`${file.file_path || file.url || file.name}_${index}`" class="attachment-item">
              <el-icon><Document /></el-icon>
              <span class="attachment-name">{{ file.name || file.filename || `附件${index + 1}` }}</span>
              <el-button size="small" text type="primary" @click="openAttachment(file)">查看</el-button>
              <el-button v-if="isEditor" size="small" text type="danger" @click="removeAttachment(index)">删除</el-button>
            </div>
          </div>
          <span v-else class="no-attachments">暂无上传的调查表或资质附件</span>
        </el-form-item>

        <el-form-item v-if="isEditor" label="上传附件">
          <el-upload
            :http-request="uploadAttachment"
            :show-file-list="false"
            accept=".pdf,.jpg,.jpeg,.png,.doc,.docx,.xls,.xlsx,.zip,.rar,.7z,.tar,.gz,.bz2,.xz"
            multiple
          >
            <el-button type="primary" plain :loading="uploading">选择并上传附件</el-button>
          </el-upload>
          <div class="upload-tip">支持一次选择多个附件，也支持 `zip/rar/7z/tar/gz/bz2/xz` 压缩文件。</div>
        </el-form-item>

        <el-form-item label="补充说明">
          <el-input
            v-model="form.onboarding_note"
            type="textarea"
            :rows="4"
            placeholder="可填写主营业务、合作背景、附件说明等信息"
            maxlength="500"
            show-word-limit
          />
        </el-form-item>

        <el-form-item v-if="isEditor">
          <el-button type="primary" @click="handleSubmit" :loading="submitting">提交完善资料</el-button>
          <el-button @click="fetchProfile">重置</el-button>
        </el-form-item>
      </el-form>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { Document } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import api from '../../api/index'

const formRef = ref(null)
const loading = ref(false)
const submitting = ref(false)
const uploading = ref(false)
const downloadingTemplate = ref(false)

const profile = ref({
  id: null,
  name: '',
  code: '',
  short_name: '',
  contact_person: '',
  phone: '',
  email: '',
  social_credit_code: '',
  application_attachments: [],
  onboarding_note: '',
  review_comment: '',
  status: '',
  role: '',
  member_status: '',
})

const form = ref({
  short_name: '',
  contact_person: '',
  phone: '',
  email: '',
  social_credit_code: '',
  application_attachments: [],
  onboarding_note: '',
})

const isEditor = computed(() => ['owner', 'admin'].includes(profile.value.role))
const roleText = computed(() => ({ owner: '创建者', admin: '管理员', member: '成员' }[profile.value.role] || profile.value.role || ''))
const statusText = computed(() => ({ pending: '审核中', approved: '已入库', rejected: '已拒绝' }[profile.value.status] || (profile.value.status || '未知')))
const statusTagType = computed(() => ({ pending: 'warning', approved: 'success', rejected: 'danger' }[profile.value.status] || 'info'))

const rules = {
  phone: [{ pattern: /^[\d\-+\s]{6,20}$/, message: '请输入有效的联系电话', trigger: 'blur' }],
  email: [{ type: 'email', message: '请输入有效的邮箱地址', trigger: 'blur' }],
}

const fetchProfile = async () => {
  loading.value = true
  try {
    const res = await api.get('/supplier/my-profile')
    profile.value = { ...res.data }
    localStorage.setItem('supplier_status', res.data.status || '')
    localStorage.setItem('member_status', res.data.member_status || '')
    form.value = {
      short_name: res.data.short_name || '',
      contact_person: res.data.contact_person || '',
      phone: res.data.phone || '',
      email: res.data.email || '',
      social_credit_code: res.data.social_credit_code || '',
      application_attachments: Array.isArray(res.data.application_attachments) ? [...res.data.application_attachments] : [],
      onboarding_note: res.data.onboarding_note || '',
    }
  } catch (error) {
    console.error(error)
    ElMessage.error('获取公司信息失败')
  } finally {
    loading.value = false
  }
}

const removeAttachment = (index) => {
  form.value.application_attachments.splice(index, 1)
}

const openAttachment = (file) => {
  const target = file.file_path || file.url || file.path
  if (!target) {
    ElMessage.warning('附件地址不存在')
    return
  }
  window.open(target, '_blank')
}

const uploadAttachment = async (options) => {
  const formData = new FormData()
  formData.append('file', options.file)
  uploading.value = true
  try {
    const res = await api.post('/auth/supplier/upload-attachment', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    form.value.application_attachments.push({
      name: res.data.name,
      file_path: res.data.file_path,
      size: res.data.size,
      uploaded_at: res.data.uploaded_at,
    })
    ElMessage.success('附件上传成功')
    options.onSuccess?.(res.data)
  } catch (error) {
    console.error(error)
    options.onError?.(error)
    ElMessage.error(error.response?.data?.detail || '附件上传失败')
  } finally {
    uploading.value = false
  }
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
    console.error(error)
    ElMessage.error(error.response?.data?.detail || '调查表下载失败')
  } finally {
    downloadingTemplate.value = false
  }
}

const handleSubmit = async () => {
  if (!formRef.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    await api.put('/supplier/my-profile', {
      short_name: form.value.short_name || null,
      contact_person: form.value.contact_person || null,
      phone: form.value.phone || null,
      email: form.value.email || null,
      social_credit_code: form.value.social_credit_code || null,
      application_attachments: form.value.application_attachments,
      onboarding_note: form.value.onboarding_note || null,
    })
    ElMessage.success('资料已提交，请等待采购审核')
    await fetchProfile()
  } catch (error) {
    console.error(error)
    ElMessage.error(error.response?.data?.detail || '提交失败')
  } finally {
    submitting.value = false
  }
}

onMounted(fetchProfile)
</script>

<style scoped>
.page-container {
  padding: 24px;
}

.content-card {
  background: #fff;
  border-radius: 8px;
  padding: 24px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
  max-width: 880px;
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

.header-tags {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.page-alert {
  margin-bottom: 16px;
}

.info-form {
  max-width: 720px;
}

.form-section-title {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
  margin: 20px 0 16px;
  padding-left: 10px;
  border-left: 3px solid #409eff;
}

.form-section-title:first-child {
  margin-top: 0;
}

.template-box {
  width: 100%;
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: center;
  padding: 14px 16px;
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

.attachment-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
}

.attachment-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: #f5f7fa;
  border-radius: 6px;
  font-size: 13px;
}

.attachment-name {
  flex: 1;
  color: #303133;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.no-attachments {
  color: #909399;
  font-size: 13px;
}

.upload-tip {
  margin-top: 8px;
  color: #909399;
  font-size: 12px;
}
</style>
