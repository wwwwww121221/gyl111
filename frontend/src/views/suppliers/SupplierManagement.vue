<template>
  <div class="page-container">
    <div class="content-card">
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
        <el-button v-if="canManage" type="primary" @click="openAddDialog">
          新增供应商
        </el-button>
      </div>

      <el-table
        :data="filteredSuppliers"
        style="width: 100%"
        v-loading="loading"
        row-key="id"
        @expand-change="handleExpandChange"
      >
        <el-table-column type="expand">
          <template #default="{ row }">
            <div class="expand-content" v-loading="memberLoadingMap[row.id]">
              <div v-if="attachmentMap[row.id]?.length > 0" class="section-block">
                <div class="section-title">资质文件</div>
                <div class="attachment-list">
                  <div v-for="(f, fIdx) in attachmentMap[row.id]" :key="fIdx" class="attachment-item">
                    <el-icon class="attachment-icon"><Document /></el-icon>
                    <span class="attachment-name">{{ f.name || f.filename || '附件' + (fIdx + 1) }}</span>
                    <el-button size="small" text type="primary" @click="openAttachment(f)">
                      查看
                    </el-button>
                    <el-button size="small" text type="primary" @click="downloadFileDirectly(f)">
                      下载
                    </el-button>
                  </div>
                </div>
              </div>

              <template v-if="membersMap[row.id]?.length > 0">
                <div class="section-block">
                  <div class="section-title">成员列表（{{ membersMap[row.id].length }}人）</div>
                <div class="member-grid">
                  <div v-for="(m, idx) in membersMap[row.id]" :key="m.id" class="member-card">
                    <div class="member-card-header">
                      <span class="member-name">{{ m.member_name || '-' }}</span>
                      <el-tag size="small" :type="m.role === 'admin' || m.role === 'owner' ? 'danger' : 'info'" effect="plain">
                        {{ roleLabel(m.role) }}
                      </el-tag>
                      <el-tag size="small" :type="statusType(m.status)" effect="plain">
                        {{ statusText(m.status) }}
                      </el-tag>
                    </div>
                    <div class="member-card-body">
                      <div class="member-info-row"><span class="label">手机号</span><span>{{ m.phone }}</span></div>
                      <div class="member-info-row"><span class="label">职位</span><span>{{ m.position || '-' }}</span></div>
                      <div v-if="m.application_note" class="member-info-row"><span class="label">说明</span><span>{{ m.application_note }}</span></div>
                      <div class="member-info-row"><span class="label">审核人</span><span>{{ m.reviewed_by_name || '-' }}</span></div>
                      <div class="member-info-row"><span class="label">加入时间</span><span>{{ formatTime(m.created_at) }}</span></div>
                    </div>
                  </div>
                </div>
                </div>
              </template>
              <div v-else class="expand-empty">{{ memberLoadingMap[row.id] ? '' : (membersMap[row.id] ? '暂无成员数据' : '') }}</div>
            </div>
          </template>
        </el-table-column>

        <el-table-column type="index" label="序号" width="80" />
        <el-table-column prop="name" label="供应商名称" />      
        <el-table-column prop="contact_person" label="联系人" />
        <el-table-column prop="phone" label="联系电话" width="140">
          <template #default="{ row }">
            <span style="white-space: nowrap;">{{ row.phone || '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="email" label="电子邮箱" />
        
        <el-table-column prop="grade" label="评级">
          <template #default="{ row }">
            <el-tag :type="row.grade === 'A级' ? 'success' : (row.grade === 'B级' ? 'warning' : (row.grade === 'C级' ? 'danger' : 'info'))">     
              {{ row.grade || '一般' }}
            </el-tag>
          </template>
        </el-table-column>
        
        <el-table-column prop="status" label="状态">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">
              {{ getStatusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column prop="reviewer_name" label="审核人" />
        <el-table-column prop="reviewed_at" label="审核时间" min-width="160" />

        <el-table-column label="操作" width="220" v-if="canManage">
          <template #default="{ row }">
            <el-button size="small" type="primary" @click="handleEdit(row)">
              管理等级/状态
            </el-button>
            <el-button v-if="userRole === 'admin'" size="small" type="danger" plain @click="handleDelete(row)">
              删除
            </el-button>
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
            <el-radio value="A级">A级</el-radio>
            <el-radio value="B级">B级</el-radio>
            <el-radio value="C级">C级</el-radio>
            <el-radio value="一般">一般</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-divider>登录账号（可选）</el-divider>
        <el-form-item label="登录账号">
          <el-input v-model="addForm.username" placeholder="选填；填写后需同时填写密码" />
        </el-form-item>
        <el-form-item label="初始密码">
          <el-input v-model="addForm.password" type="password" show-password placeholder="选填；至少6位" />
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="addDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="submitAddSupplier" :loading="submitAddLoading">
            确认创建
          </el-button>
        </span>
      </template>
    </el-dialog>

    <!-- Edit Dialog -->
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
            <el-radio value="A级">A级</el-radio>
            <el-radio value="B级">B级</el-radio>
            <el-radio value="C级">C级</el-radio>
            <el-radio value="一般">一般</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="dialogVisible = false">取消</el-button>
          <el-button type="primary" @click="submitUpdate" :loading="submitLoading">
            确认
          </el-button>
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
            <p>{{ previewFileName }} 不支持浏览器内预览</p>
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
import { ref, onMounted, computed } from 'vue'
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
  grade: '一般'
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
  password: ''
})

const addRules = {
  name: [{ required: true, message: '请输入供应商名称', trigger: 'blur' }]
}

const resetAllLoading = ref(false)

const fetchSuppliers = async () => {
  loading.value = true
  try {
    const res = await api.get('/supplier/list', {
      params: {
        page: currentPage.value,
        page_size: pageSize.value,
        keyword: searchQuery.value.trim(),
      }
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

const handleExpandChange = async (row, expandedRows) => {
  const isExpanded = expandedRows.some(r => r.id === row.id)
  if (isExpanded) {
    if (!membersMap.value[row.id]) {
      memberLoadingMap.value[row.id] = true
      try {
        const [membersRes, detailRes] = await Promise.all([
          api.get(`/supplier/${row.id}/members`),
          api.get(`/supplier/${row.id}/detail`)
        ])
        membersMap.value[row.id] = membersRes.data || []
        attachmentMap.value[row.id] = detailRes.data?.application_attachments || []
      } catch (error) {
        console.error(error)
        membersMap.value[row.id] = []
        attachmentMap.value[row.id] = []
      } finally {
        memberLoadingMap.value[row.id] = false
      }
    }
  }
}

const formatTime = (val) => val ? val.slice(0, 16).replace('T', ' ') : '-'

const IMAGE_EXTS = ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'svg']
const PDF_EXTS = ['pdf']
const OFFICE_EXTS = ['xls', 'xlsx', 'doc', 'docx', 'ppt', 'pptx']

const getFileExt = (name) => {
  if (!name) return ''
  const dot = name.lastIndexOf('.')
  return dot >= 0 ? name.slice(dot + 1).toLowerCase() : ''
}

const detectPreviewType = (f) => {
  const ext = getFileExt(f.name || f.filename || '')
  if (IMAGE_EXTS.includes(ext)) return 'image'
  if (PDF_EXTS.includes(ext)) return 'pdf'
  if (OFFICE_EXTS.includes(ext)) return 'office'
  return 'other'
}

const base64ToBlobUrl = (base64Data, fileName) => {
  try {
    const byteStr = atob(base64Data.split(',')[1])
    const mime = base64Data.split(';')[0].split(':')[1] || 'application/octet-stream'
    const ab = new ArrayBuffer(byteStr.length)
    const ia = new Uint8Array(ab)
    for (let i = 0; i < byteStr.length; i++) ia[i] = byteStr.charCodeAt(i)
    const blob = new Blob([ab], { type: mime })
    return URL.createObjectURL(blob)
  } catch (e) {
    console.error('Base64转换失败:', e)
    return null
  }
}

const openAttachment = async (f) => {
  const url = f.url || f.path || ''
  if (!url) {
    ElMessage.warning('暂无可预览的附件地址')
    return
  }
  previewFileName.value = f.name || f.filename || '附件'
  previewType.value = detectPreviewType(f)
  currentPreviewRawUrl.value = url
  previewLoading.value = true
  previewVisible.value = true

  let resolvedUrl = url

  if (previewType.value === 'office') {
    let srcUrl = url
    if (url.startsWith('data:')) {
      srcUrl = base64ToBlobUrl(url, previewFileName.value) || url
      currentPreviewRawUrl.value = srcUrl
    }
    previewUrl.value = `https://view.officeapps.live.com/op/view.aspx?src=${encodeURIComponent(srcUrl)}`
  } else {
    previewUrl.value = url
  }

  if (previewType.value === 'other') {
    previewLoading.value = false
  } else if (previewType.value !== 'office') {
    setTimeout(() => { previewLoading.value = false }, 300)
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
  if (currentPreviewRawUrl.value) {
    const a = document.createElement('a')
    a.href = currentPreviewRawUrl.value
    a.download = previewFileName.value || 'download'
    a.target = '_blank'
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
  }
}

const downloadFileDirectly = (f) => {
  const url = f.url || f.path || ''
  if (!url) {
    ElMessage.warning('暂无可下载的附件地址')
    return
  }
  const fileName = f.name || f.filename || 'download'
  const a = document.createElement('a')
  a.href = url
  a.download = fileName
  a.target = '_blank'
  a.style.display = 'none'
  document.body.appendChild(a)
  a.click()
  setTimeout(() => { document.body.removeChild(a) }, 100)
}

const roleLabel = (role) => ({ admin: '管理员', member: '成员', owner: '创建者' }[role] || role || '-')
const statusText = (status) => ({ active: '已激活', pending: '待审核', rejected: '已拒绝', disabled: '已停用' }[status] || status || '-')
const statusType = (status) => ({ active: 'success', pending: 'warning', rejected: 'danger', disabled: 'info' }[status] || 'info')

// Only show approved/rejected suppliers in this view
const filteredSuppliers = computed(() => {
  return allSuppliers.value.filter(s => s.status !== 'pending')
})

const handleResetAllAccounts = async () => {
  try {
    await ElMessageBox.confirm(
      '确定要批量重置所有已通过审核的供应商账号密码吗？\n\n重置规则：\n• 登录账号 = 公司全称\n• 初始密码 = 123456\n\n此操作不可撤销！',
      '批量重置账号密码',
      {
        confirmButtonText: '确认重置',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
  } catch {
    return
  }

  resetAllLoading.value = true
  try {
    const res = await api.post('/supplier/reset-all-accounts')
    const { updated_count, total_count, errors, errors_count } = res.data
    let message = `批量重置完成：成功 ${updated_count}/${total_count} 个供应商`
    if (errors_count > 0) {
      message += `\n\n失败 ${errors_count} 个：\n${errors.join('\n')}`
    }
    await ElMessageBox.alert(message, '重置结果', { type: errors_count > 0 ? 'warning' : 'success' })
    refreshList()
  } catch (error) {
    console.error(error)
    ElMessage.error(error.response?.data?.detail || '批量重置失败')
  } finally {
    resetAllLoading.value = false
  }
}

onMounted(() => {
  fetchSuppliers()
})

const getStatusText = (status) => {
  const map = {
    pending: '待审核',
    approved: '已通过',
    rejected: '已停用'
  }
  return map[status] || status
}

const getStatusType = (status) => {
  const map = {
    pending: 'warning',
    approved: 'success',
    rejected: 'danger'
  }
  return map[status] || 'info'
}

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
  if (addFormRef.value) {
    addFormRef.value.resetFields()
  }
  addForm.value = {
    name: '',
    code: '',
    contact_person: '',
    phone: '',
    email: '',
    status: 'approved',
    grade: '一般',
    username: '',
    password: ''
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
      ElMessage.warning('密码长度至少6位')
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
      grade: editForm.value.grade
    })
    ElMessage.success('更新成功')
    dialogVisible.value = false
    refreshList()
  } catch (error) {
    console.error(error)
  } finally {
    submitLoading.value = false
  }
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm(
      `确定要永久删除供应商 "${row.name}" 及其所有关联账号和业务数据吗？此操作不可恢复！`,
      '高危操作警告',
      {
        confirmButtonText: '确认删除',
        cancelButtonText: '取消',
        type: 'error',
      }
    )
    
    loading.value = true
    await api.delete(`/supplier/${row.id}`)
    ElMessage.success('供应商已成功删除')
    refreshList()
  } catch (error) {
    if (error !== 'cancel') {
      console.error(error)
      ElMessage.error(error.response?.data?.detail || '删除失败')
    }
  } finally {
    loading.value = false
  }
}
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
  margin-bottom: 16px;
}

.search-input {
  width: 280px;
}

/* 让表格自动占满剩余高度并内部滚动 */
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

.section-block:last-child {
  margin-bottom: 0;
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
</style>
