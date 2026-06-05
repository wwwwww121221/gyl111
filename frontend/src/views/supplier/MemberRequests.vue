<template>
  <div class="page-container">
    <div class="content-card">
      <el-tabs v-model="activeTab" @tab-change="handleTabChange">
        <el-tab-pane name="pending">
          <template #label>
            <span class="tab-label">
              待审核申请
              <el-badge v-if="pendingCount > 0" :value="pendingCount" class="tab-badge" />
            </span>
          </template>
          <div v-if="!isReviewer" class="no-permission-tip">
            <el-result icon="warning" title="无权限" sub-title="仅企业管理员可查看和审核成员加入申请" />
          </div>
          <template v-else>
            <el-table :data="pendingList" v-loading="loadingPending" style="width: 100%" empty-text="暂无待审核的加入申请" border>
              <el-table-column type="index" label="序号" width="64" />
              <el-table-column prop="member_name" label="申请人姓名" min-width="120" />
              <el-table-column prop="phone" label="手机号" width="140" />
              <el-table-column prop="position" label="申请职位" width="120" />
              <el-table-column prop="application_note" label="申请说明" min-width="200" show-overflow-tooltip />
              <el-table-column prop="created_at" label="申请时间" width="170">
                <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
              </el-table-column>
              <el-table-column label="附件" width="80" align="center">
                <template #default="{ row }">
                  <span v-if="row.application_attachments?.length">{{ row.application_attachments.length }} 个</span>
                  <span v-else>-</span>
                </template>
              </el-table-column>
              <el-table-column label="操作" width="220" fixed="right">
                <template #default="{ row }">
                  <el-button size="small" type="success" @click="openReviewDialog(row, 'approved')">通过</el-button>
                  <el-button size="small" type="danger" @click="openReviewDialog(row, 'rejected')">拒绝</el-button>
                </template>
              </el-table-column>
            </el-table>
          </template>
        </el-tab-pane>

        <el-tab-pane label="全部成员" name="all">
          <el-table :data="memberList" v-loading="loadingAll" style="width: 100%" empty-text="暂无成员记录" border>
            <el-table-column type="index" label="序号" width="64" />
            <el-table-column prop="member_name" label="姓名" min-width="110" />
            <el-table-column prop="phone" label="手机号" width="140" />
            <el-table-column prop="position" label="职位" width="110" />
            <el-table-column label="角色" width="90">
              <template #default="{ row }">
                <el-tag size="small" :type="row.role === 'admin' ? 'danger' : 'info'">
                  {{ roleLabel(row.role) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="100">
              <template #default="{ row }">
                <el-tag size="small" :type="statusType(row.status)">
                  {{ statusLabel(row.status) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="reviewed_by_name" label="审核人" width="100" />
            <el-table-column prop="reviewed_at" label="处理时间" width="170">
                <template #default="{ row }">{{ formatTime(row.reviewed_at) }}</template>
            </el-table-column>
            <el-table-column label="操作" width="120" fixed="right">
              <template #default="{ row }">
                <el-button
                  v-if="isAdmin && row.status === 'active' && row.role === 'member'"
                  size="small"
                  type="warning"
                  @click="handleTransferAdmin(row)"
                >
                  移交管理员
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </div>

    <el-dialog v-model="reviewDialogVisible" :title="reviewAction === 'approved' ? '通过申请' : '拒绝申请'" width="460px" destroy-on-close>
      <div class="review-info">
        <p><strong>申请人：</strong>{{ currentReview?.member_name }}（{{ currentReview?.phone }}）</p>
        <p><strong>申请职位：</strong>{{ currentReview?.position || '-' }}</p>
        <p v-if="currentReview?.application_note"><strong>申请说明：</strong>{{ currentReview.application_note }}</p>
      </div>
      <el-form label-width="90px">
        <el-form-item label="审核意见">
          <el-input v-model="reviewComment" type="textarea" :rows="3" placeholder="选填，可填写备注信息" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="reviewDialogVisible = false">取消</el-button>
        <el-button :type="reviewAction === 'approved' ? 'success' : 'danger'" :loading="reviewing" @click="submitReview">
          {{ reviewAction === 'approved' ? '确认通过' : '确认拒绝' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, ref, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../../api'

const activeTab = ref('pending')
const loadingPending = ref(false)
const loadingAll = ref(false)
const pendingList = ref([])
const memberList = ref([])
const pendingCount = ref(0)
const isReviewer = ref(true)
const currentRole = ref('')

const isAdmin = computed(() => currentRole.value === 'admin')

const reviewDialogVisible = ref(false)
const reviewing = ref(false)
const currentReview = ref(null)
const reviewAction = ref('')
const reviewComment = ref('')

const fetchPendingRequests = async () => {
  loadingPending.value = true
  try {
    const res = await api.get('/auth/supplier/member-requests', { params: { status_filter: 'pending' } })
    pendingList.value = res.data || []
    pendingCount.value = pendingList.value.length
  } catch (error) {
    if (error.response?.status === 403) {
      isReviewer.value = false
    }
  } finally {
    loadingPending.value = false
  }
}

const fetchAllMembers = async () => {
  loadingAll.value = true
  try {
    const res = await api.get('/auth/supplier/member-requests', { params: { status_filter: '' } })
    memberList.value = res.data || []
  } catch (error) {
    if (error.response?.status === 403) {
      isReviewer.value = false
    }
  } finally {
    loadingAll.value = false
  }
}

const handleTabChange = () => {
  if (activeTab.value === 'pending' && !pendingList.value.length && isReviewer.value) {
    fetchPendingRequests()
  }
  if (activeTab.value === 'all' && !memberList.value.length && isReviewer.value) {
    fetchAllMembers()
  }
}

const openReviewDialog = (row, action) => {
  currentReview.value = row
  reviewAction.value = action
  reviewComment.value = ''
  reviewDialogVisible.value = true
}

const submitReview = async () => {
  const actionText = reviewAction.value === 'approved' ? '通过' : '拒绝'
  try {
    await ElMessageBox.confirm(
      `确认${actionText} ${currentReview.value.member_name} 的加入申请吗？`,
      '审核确认',
      { type: 'warning' }
    )
  } catch {
    return
  }

  reviewing.value = true
  try {
    await api.put(`/auth/supplier/member-requests/${currentReview.value.id}/review`, {
      status: reviewAction.value,
      review_comment: reviewComment.value || undefined,
    })
    ElMessage.success(`已${actionText}该申请`)
    reviewDialogVisible.value = false
    fetchPendingRequests()
    fetchAllMembers()
  } finally {
    reviewing.value = false
  }
}

const handleTransferAdmin = async (row) => {
  try {
    await ElMessageBox.confirm(
      `确认将管理员身份移交给 "${row.member_name || row.phone}" 吗？移交后您将变为普通成员。`,
      '管理员移交确认',
      { type: 'warning', confirmButtonText: '确认移交', cancelButtonText: '取消' }
    )
  } catch {
    return
  }
  try {
    await api.post('/auth/supplier/transfer-admin', { target_member_id: row.id })
    ElMessage.success('管理员身份移交成功')
    currentRole.value = 'member'
    fetchAllMembers()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '移交失败')
  }
}

const fetchCurrentRole = async () => {
  try {
    const res = await api.get('/supplier/my-profile')
    currentRole.value = res.data.role || ''
  } catch (e) {
    // ignore
  }
}

const formatTime = (val) => {
  if (!val) return '-'
  return new Date(val).toLocaleString('zh-CN')
}

const roleLabel = (role) => ({ admin: '管理员', member: '成员' }[role] || '成员')
const statusType = (status) => ({
  active: 'success',
  pending: 'warning',
  rejected: 'danger',
  disabled: 'info',
}[status] || 'info')

const statusLabel = (status) => ({
  active: '已激活',
  pending: '待审核',
  rejected: '已拒绝',
  disabled: '已停用',
}[status] || '未知状态')

onMounted(() => {
  fetchCurrentRole()
  fetchPendingRequests()
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

.tab-label {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.tab-badge :deep(.el-badge__content) {
  transform: translateY(-2px);
}

.no-permission-tip {
  padding: 60px 0;
}

.review-info p {
  margin: 8px 0;
  color: #334155;
  font-size: 14px;
  line-height: 1.6;
}
</style>
