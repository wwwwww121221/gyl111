<template>
  <div class="page-container">
    <div class="content-card">
      <el-tabs v-model="activeTab" @tab-change="handleTabChange">
        <el-tab-pane label="供应商列表" name="suppliers">
          <div class="toolbar">
            <el-input
              v-model="searchQuery"
              placeholder="请输入供应商名称进行搜索"
              clearable
              class="search-input"
              @keyup.enter="handleSearch"
              @clear="handleSearch"
            />
            <el-button type="primary" @click="handleSearch">搜索</el-button>
            <el-button v-if="canManage" type="primary" @click="openAddDialog">新增供应商</el-button>
          </div>

          <el-table
            :data="filteredSuppliers"
            style="width: 100%"
            v-loading="loading"
            row-key="id"
            @expand-change="handleExpandChange"
            border
          >
            <el-table-column type="expand">
              <template #default="{ row }">
                <div class="expand-content" v-loading="memberLoadingMap[row.id]">
                  <div v-if="attachmentMap[row.id]?.length > 0" class="section-block">
                    <div class="section-title">资质文件</div>
                    <div class="attachment-list">
                      <div v-for="(file, index) in attachmentMap[row.id]" :key="index" class="attachment-item">
                        <el-icon class="attachment-icon"><Document /></el-icon>
                        <span class="attachment-name">{{ file.name || file.filename || `附件${index + 1}` }}</span>
                        <el-button size="small" text type="primary" @click="openAttachment(file)">查看</el-button>
                        <el-button size="small" text type="primary" @click="downloadFileDirectly(file)">下载</el-button>
                      </div>
                    </div>
                  </div>

                  <template v-if="membersMap[row.id]?.length > 0">
                    <div class="section-block">
                      <div class="section-title">成员列表（{{ membersMap[row.id].length }}人）</div>
                      <div class="member-grid">
                        <div v-for="member in membersMap[row.id]" :key="member.id" class="member-card">
                          <div class="member-card-header">
                            <span class="member-name">{{ member.member_name || '-' }}</span>
                            <el-tag size="small" :type="member.role === 'admin' ? 'danger' : 'info'" effect="plain">
                              {{ roleLabel(member.role) }}
                            </el-tag>
                            <el-tag size="small" :type="statusType(member.status)" effect="plain">
                              {{ statusText(member.status) }}
                            </el-tag>
                            <el-tag v-if="member.approval_mode" size="small" effect="plain" :type="member.approval_mode === 'platform_admin' ? 'warning' : 'success'">
                              {{ member.approval_mode === 'platform_admin' ? '平台审核' : '供应商审核' }}
                            </el-tag>
                          </div>
                          <div class="member-card-body">
                            <div class="member-info-row"><span class="label">手机号</span><span>{{ member.phone || '-' }}</span></div>
                            <div class="member-info-row"><span class="label">职位</span><span>{{ member.position || '-' }}</span></div>
                            <div v-if="member.application_note" class="member-info-row"><span class="label">说明</span><span>{{ member.application_note }}</span></div>
                            <div class="member-info-row"><span class="label">审核人</span><span>{{ member.reviewed_by_name || '-' }}</span></div>
                            <div class="member-info-row"><span class="label">加入时间</span><span>{{ formatTime(member.created_at) }}</span></div>
                          </div>
                          <div v-if="canReviewMember(member)" class="member-card-actions">
                            <el-button size="small" type="success" @click="reviewMemberRequest(memberToRequestRow(row, member), 'approved')">通过</el-button>
                            <el-button size="small" type="danger" @click="reviewMemberRequest(memberToRequestRow(row, member), 'rejected')">拒绝</el-button>
                          </div>
                        </div>
                      </div>
                    </div>
                  </template>

                  <div v-else class="expand-empty">
                    {{ memberLoadingMap[row.id] ? '' : (membersMap[row.id] ? '暂无成员数据' : '') }}
                  </div>
                </div>
              </template>
            </el-table-column>

            <el-table-column type="index" label="序号" width="80" />
            <el-table-column prop="name" label="供应商名称" min-width="160" />
            <el-table-column prop="contact_person" label="联系人" min-width="100" />
            <el-table-column prop="phone" label="联系电话" width="140">
              <template #default="{ row }">
                <span style="white-space: nowrap;">{{ row.phone || '-' }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="email" label="电子邮箱" min-width="140" />
            <el-table-column prop="grade" label="评级" width="100">
              <template #default="{ row }">
                <el-tag :type="gradeType(row.grade)">
                  {{ row.grade || '一般' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="status" label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="getStatusType(row.status)">
                  {{ getStatusText(row.status) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="reviewer_name" label="审核人" width="110" />
            <el-table-column prop="reviewed_at" label="审核时间" min-width="160" />
            <el-table-column v-if="canManage" label="操作" width="220">
              <template #default="{ row }">
                <el-button size="small" type="primary" @click="handleEdit(row)">管理等级/状态</el-button>
                <el-button v-if="userRole === 'admin'" size="small" type="danger" plain @click="handleDelete(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>

          <div class="pagination-wrap" v-if="total > 0">
            <el-pagination
              v-model:current-page="currentPage"
              v-model:page-size="pageSize"
              :page-sizes="[20, 50, 100]"
              :total="total"
              layout="total, sizes, prev, pager, next, jumper"
              @current-change="handlePageChange"
              @size-change="handleSizeChange"
            />
          </div>
        </el-tab-pane>

        <el-tab-pane name="member-requests">
          <template #label>
            <span>成员申请</span>
            <el-badge v-if="pendingMemberCount > 0" :value="pendingMemberCount" class="tab-badge" />
          </template>

          <el-alert
            type="info"
            :closable="false"
            class="member-alert"
            title="供应商第一个成员、或没有已激活管理员时的加入申请，会进入平台审核。"
          />

          <el-table
            :data="memberRequests"
            v-loading="loadingMemberRequests"
            style="width: 100%"
            empty-text="暂无待审核的成员申请"
            border
          >
            <el-table-column type="index" label="序号" width="64" />
            <el-table-column prop="supplier_name" label="供应商" min-width="140" />
            <el-table-column prop="member_name" label="申请人" min-width="100" />
            <el-table-column prop="phone" label="手机号" width="130" />
            <el-table-column prop="position" label="职位" width="100" />
            <el-table-column prop="application_note" label="申请说明" min-width="160" show-overflow-tooltip />
            <el-table-column label="审核模式" width="110" align="center">
              <template #default="{ row }">
                <el-tag size="small" :type="row.approval_mode === 'platform_admin' ? 'warning' : 'info'">
                  {{ row.approval_mode === 'platform_admin' ? '平台审核' : '供应商审核' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="created_at" label="申请时间" width="160">
              <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
            </el-table-column>
            <el-table-column label="操作" width="180">
              <template #default="{ row }">
                <template v-if="row.status === 'pending'">
                  <el-button size="small" type="success" @click="reviewMemberRequest(row, 'approved')">通过</el-button>
                  <el-button size="small" type="danger" @click="reviewMemberRequest(row, 'rejected')">拒绝</el-button>
                </template>
                <el-tag v-else :type="row.status === 'active' ? 'success' : 'danger'" size="small">
                  {{ row.status === 'active' ? '已通过' : '已拒绝' }}
                </el-tag>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </div>

    <el-dialog
      v-model="addDialogVisible"
      title="新增供应商"
      width="560px"
      draggable
      overflow
      @close="resetAddForm"
    >
      <el-form ref="addFormRef" :model="addForm" :rules="addRules" label-width="110px">
        <el-form-item label="供应商名称" prop="name">
          <el-input v-model="addForm.name" />
        </el-form-item>
        <el-form-item label="供应商编码">
          <el-input v-model="addForm.code" placeholder="选填" />
        </el-form-item>
        <el-form-item label="联系人">
          <el-input v-model="addForm.contact_person" placeholder="选填" />
        </el-form-item>
        <el-form-item label="联系电话">
          <el-input v-model="addForm.phone" placeholder="选填" />
        </el-form-item>
        <el-form-item label="电子邮箱">
          <el-input v-model="addForm.email" placeholder="选填" />
        </el-form-item>
        <el-form-item label="状态">
          <el-radio-group v-model="addForm.status">
            <el-radio label="approved">正常/已通过</el-radio>
            <el-radio label="rejected">停用/已拒绝</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="供应商评级">
          <el-radio-group v-model="addForm.grade">
            <el-radio label="A级">A级</el-radio>
            <el-radio label="B级">B级</el-radio>
            <el-radio label="C级">C级</el-radio>
            <el-radio label="一般">一般</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-divider>登录账号（可选）</el-divider>
        <el-form-item label="登录账号">
          <el-input v-model="addForm.username" placeholder="选填；填写后需同时填写密码" />
        </el-form-item>
        <el-form-item label="初始密码">
          <el-input v-model="addForm.password" type="password" show-password placeholder="选填；至少 6 位" />
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="addDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="submitAddSupplier" :loading="submitAddLoading">确认创建</el-button>
        </span>
      </template>
    </el-dialog>

    <el-dialog
      v-model="memberReviewDialogVisible"
      :title="memberReviewAction === 'approved' ? '通过成员申请' : '拒绝成员申请'"
      width="460px"
      destroy-on-close
    >
      <div class="review-info">
        <p><strong>供应商：</strong>{{ currentMemberReview?.supplier_name || '-' }}</p>
        <p><strong>申请人：</strong>{{ currentMemberReview?.member_name || '-' }}（{{ currentMemberReview?.phone || '-' }}）</p>
        <p v-if="currentMemberReview?.position"><strong>职位：</strong>{{ currentMemberReview.position }}</p>
        <p v-if="currentMemberReview?.application_note"><strong>说明：</strong>{{ currentMemberReview.application_note }}</p>
      </div>
      <el-form label-width="90px">
        <el-form-item label="审核意见">
          <el-input v-model="memberReviewComment" type="textarea" :rows="3" placeholder="选填，可填写备注信息" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="memberReviewDialogVisible = false">取消</el-button>
        <el-button
          :type="memberReviewAction === 'approved' ? 'success' : 'danger'"
          :loading="memberReviewSubmitting"
          @click="submitMemberReview"
        >
          {{ memberReviewAction === 'approved' ? '确认通过' : '确认拒绝' }}
        </el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="dialogVisible"
      title="供应商管理"
      width="500px"
      draggable
      overflow
    >
      <el-form :model="editForm" label-width="100px">
        <el-form-item label="供应商名称">
          <el-input v-model="currentSupplierName" disabled />
        </el-form-item>
        <el-form-item label="状态调整">
          <el-radio-group v-model="editForm.status">
            <el-radio label="approved">正常/已通过</el-radio>
            <el-radio label="rejected">停用/已拒绝</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="供应商评级">
          <el-radio-group v-model="editForm.grade">
            <el-radio label="A级">A级</el-radio>
            <el-radio label="B级">B级</el-radio>
            <el-radio label="C级">C级</el-radio>
            <el-radio label="一般">一般</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="dialogVisible = false">取消</el-button>
          <el-button type="primary" @click="submitUpdate" :loading="submitLoading">确认</el-button>
        </span>
      </template>
    </el-dialog>

    <el-dialog
      v-model="previewVisible"
      :title="previewFileName"
      width="80%"
      top="4vh"
      destroy-on-close
      class="preview-dialog"
    >
      <div v-if="previewLoading" class="preview-loading">
        <el-icon class="is-loading" :size="32"><Loading /></el-icon>
        <span>加载中，请稍候...</span>
      </div>
      <div v-else-if="previewType === 'image'" class="preview-image-wrap">
        <img :src="previewUrl" :alt="previewFileName" @load="onPreviewLoad" @error="onPreviewError" />
      </div>
      <iframe
        v-else-if="previewType === 'pdf' || previewType === 'office'"
        :src="previewUrl"
        class="preview-iframe"
        frameborder="0"
        @load="onPreviewOfficeLoad"
      />
      <div v-else class="preview-fallback">
        <el-result icon="warning" title="无法在线预览">
          <template #sub-title>
            <p>{{ previewFileName }} 暂不支持浏览器内预览。</p>
          </template>
          <template #extra>
            <el-button type="primary" @click="downloadAttachment">下载文件</el-button>
          </template>
        </el-result>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import api from '../../api/index'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Document, Loading } from '@element-plus/icons-vue'

const allSuppliers = ref([])
const loading = ref(false)
const searchQuery = ref('')
const currentPage = ref(1)
const pageSize = ref(20)
const total = ref(0)
const membersMap = ref({})
const attachmentMap = ref({})
const memberLoadingMap = ref({})

const previewVisible = ref(false)
const previewUrl = ref('')
const previewFileName = ref('')
const previewType = ref('')
const previewLoading = ref(true)
const currentPreviewRawUrl = ref('')

const userRole = computed(() => localStorage.getItem('role') || '')
const canManage = computed(() => ['admin', 'buyer', 'buyer_manager'].includes(userRole.value))

const dialogVisible = ref(false)
const currentSupplierId = ref(null)
const currentSupplierName = ref('')
const submitLoading = ref(false)
const addDialogVisible = ref(false)
const submitAddLoading = ref(false)
const addFormRef = ref(null)

const editForm = ref({
  status: 'approved',
  grade: '一般',
})

const addForm = ref({
  name: '',
  code: '',
  contact_person: '',
  phone: '',
  email: '',
  status: 'approved',
  grade: '一般',
  username: '',
  password: '',
})

const addRules = {
  name: [{ required: true, message: '请输入供应商名称', trigger: 'blur' }],
}

const activeTab = ref('suppliers')
const memberRequests = ref([])
const loadingMemberRequests = ref(false)
const pendingMemberCount = computed(() => memberRequests.value.filter((item) => item.status === 'pending').length)
const memberReviewDialogVisible = ref(false)
const memberReviewSubmitting = ref(false)
const currentMemberReview = ref(null)
const memberReviewAction = ref('')
const memberReviewComment = ref('')

const fetchMemberRequests = async () => {
  loadingMemberRequests.value = true
  try {
    const res = await api.get('/auth/supplier/member-requests', { params: { status_filter: '' } })
    memberRequests.value = res.data || []
  } catch (error) {
    console.error(error)
  } finally {
    loadingMemberRequests.value = false
  }
}

const handleTabChange = (tab) => {
  if (tab === 'member-requests') {
    fetchMemberRequests()
  }
}

const memberToRequestRow = (supplier, member) => ({
  ...member,
  supplier_id: supplier.id,
  supplier_name: supplier.name,
})

const canReviewMember = (member) => canManage.value && member.status === 'pending'

const reviewMemberRequest = async (row, action) => {
  currentMemberReview.value = row
  memberReviewAction.value = action
  memberReviewComment.value = ''
  memberReviewDialogVisible.value = true
}

const submitMemberReview = async () => {
  if (!currentMemberReview.value) return

  const actionText = memberReviewAction.value === 'approved' ? '通过' : '拒绝'
  memberReviewSubmitting.value = true
  try {
    await api.put(`/auth/supplier/member-requests/${currentMemberReview.value.id}/review`, {
      status: memberReviewAction.value,
      review_comment: memberReviewComment.value || undefined,
    })
    ElMessage.success(`已${actionText}该申请`)
    memberReviewDialogVisible.value = false
    await Promise.all([
      fetchMemberRequests(),
      refreshExpandedSupplierMembers(currentMemberReview.value.supplier_id),
    ])
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '操作失败')
  } finally {
    memberReviewSubmitting.value = false
  }
}

const fetchSuppliers = async () => {
  loading.value = true
  try {
    const res = await api.get('/supplier/list', {
      params: {
        page: currentPage.value,
        page_size: pageSize.value,
        keyword: searchQuery.value.trim(),
      },
    })
    allSuppliers.value = res.data.list || []
    total.value = res.data.total || 0
  } catch (error) {
    console.error(error)
  } finally {
    loading.value = false
  }
}

const handlePageChange = (page) => {
  currentPage.value = page
  fetchSuppliers()
}

const handleSizeChange = (size) => {
  pageSize.value = size
  currentPage.value = 1
  fetchSuppliers()
}

const handleSearch = () => {
  currentPage.value = 1
  fetchSuppliers()
}

const refreshList = () => {
  currentPage.value = 1
  fetchSuppliers()
}

const loadSupplierExpandData = async (supplierId) => {
  const [membersRes, detailRes] = await Promise.all([
    api.get(`/supplier/${supplierId}/members`),
    api.get(`/supplier/${supplierId}/detail`),
  ])
  membersMap.value[supplierId] = membersRes.data || []
  attachmentMap.value[supplierId] = detailRes.data?.application_attachments || []
}

const refreshExpandedSupplierMembers = async (supplierId) => {
  if (!supplierId || !membersMap.value[supplierId]) return
  try {
    await loadSupplierExpandData(supplierId)
  } catch (error) {
    console.error(error)
  }
}

const handleExpandChange = async (row, expandedRows) => {
  const isExpanded = expandedRows.some((item) => item.id === row.id)
  if (!isExpanded || membersMap.value[row.id]) return

  memberLoadingMap.value[row.id] = true
  try {
    await loadSupplierExpandData(row.id)
  } catch (error) {
    console.error(error)
    membersMap.value[row.id] = []
    attachmentMap.value[row.id] = []
  } finally {
    memberLoadingMap.value[row.id] = false
  }
}

const formatTime = (value) => (value ? String(value).slice(0, 16).replace('T', ' ') : '-')

const IMAGE_EXTS = ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'svg']
const PDF_EXTS = ['pdf']
const OFFICE_EXTS = ['xls', 'xlsx', 'doc', 'docx', 'ppt', 'pptx']

const getFileExt = (name) => {
  if (!name) return ''
  const dot = name.lastIndexOf('.')
  return dot >= 0 ? name.slice(dot + 1).toLowerCase() : ''
}

const detectPreviewType = (file) => {
  if (file.preview_file_path) return 'pdf'
  const ext = getFileExt(file.name || file.filename || '')
  if (IMAGE_EXTS.includes(ext)) return 'image'
  if (PDF_EXTS.includes(ext)) return 'pdf'
  if (OFFICE_EXTS.includes(ext)) return 'office'
  return 'other'
}

const base64ToBlobUrl = (base64Data) => {
  try {
    const byteStr = atob(base64Data.split(',')[1])
    const mime = base64Data.split(';')[0].split(':')[1] || 'application/octet-stream'
    const ab = new ArrayBuffer(byteStr.length)
    const ia = new Uint8Array(ab)
    for (let i = 0; i < byteStr.length; i += 1) ia[i] = byteStr.charCodeAt(i)
    return URL.createObjectURL(new Blob([ab], { type: mime }))
  } catch (error) {
    console.error('Base64 转换失败:', error)
    return null
  }
}

const openAttachment = async (file) => {
  const previewPath = file.preview_file_path || ''
  const url = file.file_path || file.url || file.path || ''
  if (!url && !previewPath) {
    ElMessage.warning('暂无可预览的附件地址')
    return
  }

  previewFileName.value = file.name || file.filename || '附件'
  previewType.value = detectPreviewType(file)
  currentPreviewRawUrl.value = url
  previewLoading.value = true
  previewVisible.value = true

  const resolvedUrl = previewPath || url
  if (previewType.value === 'office') {
    let srcUrl = url
    if (url.startsWith('data:')) {
      srcUrl = base64ToBlobUrl(url) || url
      currentPreviewRawUrl.value = srcUrl
    }
    previewUrl.value = `https://view.officeapps.live.com/op/view.aspx?src=${encodeURIComponent(srcUrl)}`
  } else {
    previewUrl.value = resolvedUrl
  }

  if (previewType.value === 'other') {
    previewLoading.value = false
  } else if (previewType.value !== 'office') {
    setTimeout(() => {
      previewLoading.value = false
    }, 300)
  }
}

const onPreviewLoad = () => {
  previewLoading.value = false
}

const onPreviewOfficeLoad = () => {
  setTimeout(() => {
    previewLoading.value = false
  }, 800)
}

const onPreviewError = () => {
  previewLoading.value = false
  ElMessage.warning('文件加载失败，可能格式不支持或链接已失效')
}

const downloadAttachment = () => {
  if (!currentPreviewRawUrl.value) return
  const a = document.createElement('a')
  a.href = currentPreviewRawUrl.value
  a.download = previewFileName.value || 'download'
  a.target = '_blank'
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
}

const downloadFileDirectly = (file) => {
  const url = file.file_path || file.url || file.path || ''
  if (!url) {
    ElMessage.warning('暂无可下载的附件地址')
    return
  }
  const a = document.createElement('a')
  a.href = url
  a.download = file.name || file.filename || 'download'
  a.target = '_blank'
  a.style.display = 'none'
  document.body.appendChild(a)
  a.click()
  setTimeout(() => {
    document.body.removeChild(a)
  }, 100)
}

const roleLabel = (role) => ({ admin: '管理员', member: '成员' }[role] || role || '-')
const statusText = (status) => ({ active: '已激活', pending: '待审核', rejected: '已拒绝', disabled: '已停用' }[status] || status || '-')
const statusType = (status) => ({ active: 'success', pending: 'warning', rejected: 'danger', disabled: 'info' }[status] || 'info')
const gradeType = (grade) => ({ A级: 'success', B级: 'warning', C级: 'danger', 一般: 'info' }[grade] || 'info')

const filteredSuppliers = computed(() => allSuppliers.value.filter((item) => item.status !== 'pending'))

const getStatusText = (status) => ({
  pending: '待审核',
  approved: '已通过',
  rejected: '已停用',
}[status] || status)

const getStatusType = (status) => ({
  pending: 'warning',
  approved: 'success',
  rejected: 'danger',
}[status] || 'info')

const handleEdit = (row) => {
  currentSupplierId.value = row.id
  currentSupplierName.value = row.name
  editForm.value.status = row.status || 'approved'
  editForm.value.grade = row.grade || '一般'
  dialogVisible.value = true
}

const openAddDialog = () => {
  resetAddForm()
  addDialogVisible.value = true
}

const resetAddForm = () => {
  addFormRef.value?.resetFields()
  addForm.value = {
    name: '',
    code: '',
    contact_person: '',
    phone: '',
    email: '',
    status: 'approved',
    grade: '一般',
    username: '',
    password: '',
  }
}

const submitAddSupplier = async () => {
  if (!addFormRef.value) return

  await addFormRef.value.validate(async (valid) => {
    if (!valid) return
    if ((addForm.value.username && !addForm.value.password) || (!addForm.value.username && addForm.value.password)) {
      ElMessage.warning('若要创建登录账号，请同时填写账号和密码')
      return
    }
    if (addForm.value.password && addForm.value.password.length < 6) {
      ElMessage.warning('密码长度至少 6 位')
      return
    }

    submitAddLoading.value = true
    try {
      await api.post('/supplier/manage', addForm.value)
      ElMessage.success('供应商创建成功')
      addDialogVisible.value = false
      refreshList()
    } catch (error) {
      console.error(error)
      ElMessage.error(error.response?.data?.detail || '创建失败')
    } finally {
      submitAddLoading.value = false
    }
  })
}

const submitUpdate = async () => {
  submitLoading.value = true
  try {
    await api.put(`/supplier/${currentSupplierId.value}`, {
      status: editForm.value.status,
      grade: editForm.value.grade,
    })
    ElMessage.success('更新成功')
    dialogVisible.value = false
    refreshList()
  } catch (error) {
    console.error(error)
    ElMessage.error(error.response?.data?.detail || '更新失败')
  } finally {
    submitLoading.value = false
  }
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm(
      `确定要永久删除供应商“${row.name}”及其所有关联账号和业务数据吗？此操作不可恢复。`,
      '高危操作警告',
      {
        confirmButtonText: '确认删除',
        cancelButtonText: '取消',
        type: 'error',
      },
    )
  } catch {
    return
  }

  loading.value = true
  try {
    await api.delete(`/supplier/${row.id}`)
    ElMessage.success('供应商已成功删除')
    refreshList()
  } catch (error) {
    console.error(error)
    ElMessage.error(error.response?.data?.detail || '删除失败')
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchSuppliers()
  fetchMemberRequests()
})
</script>

<style scoped>
.page-container {
  padding: 20px;
  height: 100%;
  box-sizing: border-box;
}

.content-card {
  background: white;
  padding: 20px;
  border-radius: 8px;
  height: 100%;
  display: flex;
  flex-direction: column;
}

.toolbar {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.search-input {
  width: 320px;
}

:deep(.el-table) {
  flex: 1;
  height: 100%;
}

.expand-content {
  padding: 16px 24px;
}

.expand-empty {
  text-align: center;
  color: #909399;
  padding: 16px 0;
  font-size: 13px;
}

.member-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 12px;
}

.member-card {
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  background: #fafbfc;
  overflow: hidden;
}

.member-card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  background: #f0f2f5;
  border-bottom: 1px solid #ebeef5;
  flex-wrap: wrap;
}

.member-name {
  font-weight: 600;
  font-size: 14px;
  color: #303133;
  flex-shrink: 0;
}

.member-card-body {
  padding: 10px 14px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.member-card-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 0 14px 14px;
}

.member-info-row {
  display: flex;
  align-items: baseline;
  font-size: 13px;
  line-height: 1.6;
}

.member-info-row .label {
  color: #909399;
  width: 60px;
  flex-shrink: 0;
}

.member-info-row span:last-child {
  color: #303133;
}

.section-block {
  margin-bottom: 16px;
}

.section-title {
  font-size: 13px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 10px;
  padding-bottom: 6px;
  border-bottom: 1px solid #ebeef5;
}

.attachment-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.attachment-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  background: #fff;
  border: 1px solid #e4e7ed;
  border-radius: 6px;
  font-size: 13px;
}

.attachment-icon {
  color: #409eff;
  font-size: 16px;
}

.attachment-name {
  color: #303133;
  max-width: 180px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.member-alert {
  margin-bottom: 16px;
}

.preview-dialog :deep(.el-dialog__body) {
  padding: 0;
  min-height: 400px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.preview-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  color: #909399;
  padding: 60px 0;
}

.preview-image-wrap {
  width: 100%;
  text-align: center;
  padding: 16px;
  overflow: auto;
  max-height: 75vh;
}

.preview-image-wrap img {
  max-width: 100%;
  max-height: 70vh;
  object-fit: contain;
  border-radius: 4px;
}

.preview-iframe {
  width: 100%;
  height: 70vh;
  border: none;
}

.preview-fallback {
  padding: 40px 20px;
}

.pagination-wrap {
  display: flex;
  justify-content: flex-end;
  padding: 16px 0 0;
}

.tab-badge :deep(.el-badge__content) {
  transform: translateY(-2px);
}
</style>
