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
              <div class="detail-section">
                <div class="detail-title">补充说明</div>
                <div class="detail-text">{{ row.onboarding_note || '暂无补充说明' }}</div>
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
        <el-table-column prop="name" label="供应商名称" min-width="220" />
        <el-table-column prop="social_credit_code" label="统一社会信用代码" min-width="180" />
        <el-table-column prop="contact_person" label="联系人" width="140" />
        <el-table-column prop="phone" label="手机号" width="140" />
        <el-table-column prop="email" label="邮箱" min-width="180" show-overflow-tooltip />
        <el-table-column label="附件" width="120">
          <template #default="{ row }">
            <el-button
              v-if="row.application_attachments?.length"
              link
              type="primary"
              @click="openAttachmentList(row)"
            >
              {{ row.application_attachments.length }} 个
            </el-button>
            <span v-else>0 个</span>
          </template>
        </el-table-column>
        <el-table-column prop="review_comment" label="审核意见" min-width="220" show-overflow-tooltip />
        <el-table-column label="操作" width="280" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="success" @click="approveSupplier(row)">审核通过</el-button>
            <el-button size="small" type="warning" @click="returnSupplier(row)">退回补充</el-button>
            <el-button size="small" type="danger" @click="rejectSupplier(row)">拒绝</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog v-model="attachmentDialogVisible" title="附件列表" width="720px">
      <div v-if="currentSupplier" class="dialog-header">
        <div class="dialog-name">{{ currentSupplier.name }}</div>
        <div class="dialog-note">{{ currentSupplier.onboarding_note || '暂无补充说明' }}</div>
      </div>

      <div v-if="currentSupplier?.application_attachments?.length" class="dialog-attachment-list">
        <div
          v-for="(file, index) in currentSupplier.application_attachments"
          :key="`${file.file_path || file.url || file.name}_${index}`"
          class="dialog-attachment-item"
        >
          <span class="attachment-name">{{ file.name || file.filename || `附件${index + 1}` }}</span>
          <div class="attachment-actions">
            <el-button size="small" text type="primary" @click="openAttachment(file)">查看</el-button>
            <el-button size="small" text type="primary" @click="downloadAttachment(file)">下载</el-button>
          </div>
        </div>
      </div>
      <el-empty v-else description="暂无附件" />
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../../api'

const loadingSuppliers = ref(false)
const pendingSuppliers = ref([])
const attachmentDialogVisible = ref(false)
const currentSupplier = ref(null)

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

const openAttachmentList = (row) => {
  currentSupplier.value = row
  attachmentDialogVisible.value = true
}

const getAttachmentUrl = (file) => file?.file_path || file?.url || file?.path || ''

const openAttachment = (file) => {
  const target = getAttachmentUrl(file)
  if (!target) {
    ElMessage.warning('附件地址不存在')
    return
  }
  window.open(target, '_blank')
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
    await ElMessageBox.confirm(`确认审核通过供应商“${row.name}”吗？`, '审核确认', { type: 'warning' })
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
  padding: 8px 12px;
  background: #fafbfd;
}

.detail-section + .detail-section {
  margin-top: 16px;
}

.detail-title {
  font-size: 13px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 8px;
}

.detail-text {
  color: #606266;
  line-height: 1.7;
  white-space: pre-wrap;
}

.attachment-list,
.dialog-attachment-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.attachment-item,
.dialog-attachment-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 10px 12px;
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
}

.attachment-actions {
  flex-shrink: 0;
}

.dialog-header {
  margin-bottom: 16px;
}

.dialog-name {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.dialog-note {
  margin-top: 8px;
  color: #606266;
  line-height: 1.7;
  white-space: pre-wrap;
}
</style>
