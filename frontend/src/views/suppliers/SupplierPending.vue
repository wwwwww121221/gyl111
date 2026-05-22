<template>
  <div class="page-container">
    <div class="content-card">
      <div class="page-title">待审核供应商</div>
      <el-table
        :data="pendingSuppliers"
        v-loading="loadingSuppliers"
        style="width: 100%"
        empty-text="暂无待审核供应商"
        row-key="id"
      >
        <el-table-column type="expand" width="52">
          <template #default="{ row }">
            <div class="expand-panel">
              <div class="detail-grid">
                <div class="detail-section">
                  <div class="detail-title">统一社会信用代码</div>
                  <div class="detail-text">{{ row.social_credit_code || '-' }}</div>
                </div>

                <div class="detail-section">
                  <div class="detail-title">邮箱</div>
                  <div class="detail-text">{{ row.email || '-' }}</div>
                </div>

                <div class="detail-section">
                  <div class="detail-title">当前状态</div>
                  <div class="detail-text"><el-tag :type="getAuditStatusTagType(row)" effect="light" size="small">{{ getAuditStatusText(row) }}</el-tag></div>
                </div>
              </div>

              <div class="detail-section" v-if="row.onboarding_note">
                <div class="detail-title">补充说明</div>
                <div class="detail-text">{{ row.onboarding_note }}</div>
              </div>

              <div class="detail-section change-desc-section" v-if="row.change_description">
                <div class="detail-title">📋 变更说明</div>
                <div class="detail-text change-desc-text">{{ row.change_description }}</div>
              </div>

              <div class="detail-section" v-if="row.review_comment">
                <div class="detail-title">审核意见</div>
                <div class="detail-text">{{ row.review_comment }}</div>
              </div>

              <div class="detail-section">
                <div class="detail-title">资质附件</div>
                <div v-if="row.application_attachments?.length" class="attachment-list">
                  <div
                    v-for="(file, index) in row.application_attachments"
                    :key="`${file.file_path || file.url || file.name}_${index}`"
                    class="attachment-item"
                  >
                    <span class="attachment-name">{{ file.name || file.filename || `附件${index + 1}` }}</span>
                    <div class="attachment-actions">
                      <el-button size="small" text type="primary" @click="openAttachment(file)">查看</el-button>
                      <el-button size="small" text type="primary" @click="downloadAttachment(file)">下载</el-button>
                    </div>
                  </div>
                </div>
                <div v-else class="detail-text">暂无附件</div>
              </div>
            </div>
          </template>
        </el-table-column>

        <el-table-column type="index" label="序号" width="72" />
        <el-table-column prop="name" label="供应商名称" min-width="200" show-overflow-tooltip />
        <el-table-column prop="contact_person" label="联系人" width="120" />
        <el-table-column prop="phone" label="手机号" width="140" />
        <el-table-column label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="getAuditStatusTagType(row)" effect="light">{{ getAuditStatusText(row) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="附件" width="80">
          <template #default="{ row }">
            {{ row.application_attachments?.length || 0 }} 个
          </template>
        </el-table-column>
        <el-table-column label="操作" width="260" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="success" :disabled="!canApprove(row)" @click="approveSupplier(row)">审核通过</el-button>
            <el-button size="small" type="warning" :disabled="!canReturn(row)" @click="returnSupplier(row)">退回补充</el-button>
            <el-button size="small" type="danger" :disabled="!canReject(row)" @click="rejectSupplier(row)">拒绝</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog
      v-model="previewVisible"
      :title="previewFileName"
      width="80%"
      top="4vh"
      destroy-on-close
    >
      <div v-if="previewType === 'image'" class="preview-image-wrap">
        <img :src="previewUrl" :alt="previewFileName" />
      </div>
      <iframe
        v-else-if="previewType === 'pdf'"
        :src="previewUrl"
        class="preview-iframe"
        frameborder="0"
      />
      <el-empty v-else description="该文件不支持在线预览，请下载后查看" />
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api, { resolveAssetUrl } from '../../api'

const loadingSuppliers = ref(false)
const pendingSuppliers = ref([])
const previewVisible = ref(false)
const previewUrl = ref('')
const previewFileName = ref('')
const previewType = ref('')

const getAuditStatusRaw = (row) => String(row?.profile_audit_status || '').toLowerCase()

const getAuditStatusText = (row) => {
  const auditStatus = getAuditStatusRaw(row)
  const statusMap = {
    submitted: '待审核',
    returned: '退回补充',
    change_pending: '资料变更待审',
    change_returned: '变更已退回',
    approved: '已通过',
    rejected: '已拒绝',
    draft: '待提交',
  }
  return statusMap[auditStatus] || (row?.status === 'pending' ? '待审核' : '待处理')
}

const getAuditStatusTagType = (row) => {
  const auditStatus = getAuditStatusRaw(row)
  if (auditStatus === 'returned' || auditStatus === 'change_returned') return 'warning'
  if (auditStatus === 'approved') return 'success'
  if (auditStatus === 'rejected') return 'danger'
  return ''
}

const canApprove = (row) => {
  const s = getAuditStatusRaw(row)
  return ['submitted', 'returned', 'change_returned', 'change_pending'].includes(s)
}

const canReturn = (row) => {
  const s = getAuditStatusRaw(row)
  return ['submitted', 'returned', 'change_pending', 'change_returned'].includes(s)
}

const canReject = (row) => {
  const s = getAuditStatusRaw(row)
  return ['submitted', 'returned', 'change_pending', 'change_returned'].includes(s)
}

const fetchPendingSuppliers = async () => {
  loadingSuppliers.value = true
  try {
    const res = await api.get('/supplier/pending')
    pendingSuppliers.value = Array.isArray(res.data) ? res.data : []
  } catch (error) {
    console.error(error)
  } finally {
    loadingSuppliers.value = false
  }
}

const getAttachmentUrl = (file) => resolveAssetUrl(file?.file_path || file?.url || file?.path || '')
const getAttachmentPreviewUrl = (file) => resolveAssetUrl(file?.preview_file_path || getAttachmentUrl(file))

const getFileExt = (file) => {
  const name = file?.name || file?.filename || ''
  const dotIndex = name.lastIndexOf('.')
  return dotIndex >= 0 ? name.slice(dotIndex + 1).toLowerCase() : ''
}

const openAttachment = (file) => {
  const downloadTarget = getAttachmentUrl(file)
  if (!downloadTarget) {
    ElMessage.warning('附件地址不存在')
    return
  }

  const ext = getFileExt(file)
  const previewTarget = getAttachmentPreviewUrl(file)
  if (['png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp', 'svg'].includes(ext)) {
    previewType.value = 'image'
    previewFileName.value = file?.name || file?.filename || '附件'
    previewUrl.value = previewTarget
    previewVisible.value = true
    return
  }

  if (ext === 'pdf' || (previewTarget && previewTarget !== downloadTarget)) {
    previewType.value = 'pdf'
    previewFileName.value = file?.name || file?.filename || '附件'
    previewUrl.value = previewTarget
    previewVisible.value = true
    return
  }

  downloadAttachment(file)
  ElMessage.info('该文件暂不支持在线预览，已为您下载后查看')
}

const downloadAttachment = (file) => {
  const target = getAttachmentUrl(file)
  if (!target) {
    ElMessage.warning('附件地址不存在')
    return
  }
  const link = document.createElement('a')
  link.href = target
  link.download = file?.name || file?.filename || '附件'
  link.target = '_blank'
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
}

const approveSupplier = async (row) => {
  try {
    await ElMessageBox.confirm(`确认审核通过供应商"${row.name}"吗？`, '审核确认', { type: 'warning' })
    await api.put(`/supplier/${row.id}`, { status: 'approved', level: row.level || 'general' })
    ElMessage.success('供应商已审核通过并入库')
    fetchPendingSuppliers()
  } catch (error) {
    if (error !== 'cancel') console.error(error)
  }
}

const returnSupplier = async (row) => {
  try {
    const { value } = await ElMessageBox.prompt('请填写需要供应商补充的资料或附件要求', `退回补充：${row.name}`, {
      confirmButtonText: '确认退回',
      cancelButtonText: '取消',
      inputType: 'textarea',
      inputValue: row.review_comment || '',
      inputPlaceholder: '例如：请补充供应商调查表、营业执照、体系认证文件等',
      inputValidator: (inputValue) => (String(inputValue || '').trim() ? true : '请填写退回意见'),
    })
    await api.put(`/supplier/${row.id}`, {
      status: 'pending',
      review_comment: value,
      level: row.level || 'general',
    })
    ElMessage.success('已退回供应商补充资料')
    fetchPendingSuppliers()
  } catch (error) {
    if (error !== 'cancel') console.error(error)
  }
}

const rejectSupplier = async (row) => {
  try {
    const { value } = await ElMessageBox.prompt('如有需要，请填写拒绝原因', `拒绝供应商：${row.name}`, {
      confirmButtonText: '确认拒绝',
      cancelButtonText: '取消',
      inputType: 'textarea',
      inputValue: row.review_comment || '',
      inputPlaceholder: '请输入拒绝原因',
    })
    await api.put(`/supplier/${row.id}`, {
      status: 'rejected',
      review_comment: value || '审核未通过',
    })
    ElMessage.success('供应商申请已拒绝')
    fetchPendingSuppliers()
  } catch (error) {
    if (error !== 'cancel') console.error(error)
  }
}

onMounted(() => {
  fetchPendingSuppliers()
})
</script>

<style scoped>
.page-container {
  padding: 20px;
  height: 100%;
  box-sizing: border-box;
}

.content-card {
  background: #ffffff;
  padding: 20px;
  border-radius: 12px;
  min-height: 100%;
}

.page-title {
  font-size: 18px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 16px;
}

.expand-panel {
  padding: 16px 20px;
  background: #fafbfd;
}

.detail-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px 24px;
}

.detail-section + .detail-section {
  margin-top: 16px;
}

.detail-title {
  font-size: 12px;
  font-weight: 600;
  color: #909399;
  margin-bottom: 6px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.detail-text {
  color: #303133;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-all;
}

.attachment-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.attachment-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  background: #fff;
  border: 1px solid #ebeef5;
  border-radius: 8px;
}

.attachment-name {
  flex: 1;
  color: #303133;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
}

.attachment-actions {
  display: flex;
  justify-content: flex-start;
  gap: 4px;
  flex-shrink: 0;
  margin-left: 16px;
}

.attach-count-text {
  font-size: 13px;
  color: #606266;
}

.preview-image-wrap {
  width: 100%;
  text-align: center;
  max-height: 75vh;
  overflow: auto;
}

.preview-image-wrap img {
  max-width: 100%;
  max-height: 70vh;
  object-fit: contain;
}

.preview-iframe {
  width: 100%;
  height: 70vh;
  border: none;
}

.change-desc-section {
  background: #fdf6ec;
  border: 1px solid #faecd8;
  border-radius: 8px;
  padding: 12px 16px;
}

.change-desc-text {
  color: #e6a23c;
  font-weight: 500;
}
</style>