<template>
  <div class="page-container">
    <div class="content-card">
      <div class="toolbar">
        <el-input
          v-model="searchQuery"
          placeholder="请输入供应商名称进行搜索"
          clearable
          class="search-input"
        />
        <el-button v-if="canManage" type="primary" @click="openAddDialog">
          新增供应商
        </el-button>
      </div>

      <el-table :data="filteredSuppliers" style="width: 100%" v-loading="loading">
        <el-table-column type="index" label="序号" width="80" />
        <el-table-column prop="name" label="供应商名称" />      
        <el-table-column prop="contact_person" label="联系人" />
        <el-table-column prop="phone" label="联系电话" />
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

        <el-table-column label="操作" width="320" v-if="canManage">
          <template #default="{ row }">
            <el-button size="small" type="primary" @click="handleEdit(row)">
              管理等级/状态
            </el-button>
            <el-button size="small" type="warning" plain @click="handleAccountEdit(row)">
              编辑账号
            </el-button>
            <el-button v-if="userRole === 'admin'" size="small" type="danger" plain @click="handleDelete(row)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog v-model="addDialogVisible" title="新增供应商" width="560px" @close="resetAddForm">
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
    <el-dialog v-model="dialogVisible" title="供应商管理" width="500px">
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

    <el-dialog v-model="accountDialogVisible" title="编辑供应商登录账号" width="500px" @close="resetAccountForm">
      <el-form ref="accountFormRef" :model="accountForm" :rules="accountRules" label-width="100px">
        <el-form-item label="供应商名称">
          <el-input v-model="currentSupplierName" disabled />
        </el-form-item>
        <el-form-item label="登录账号" prop="username">
          <el-input v-model="accountForm.username" placeholder="请输入登录账号" />
        </el-form-item>
        <el-form-item label="重置密码" prop="password">
          <el-input
            v-model="accountForm.password"
            type="password"
            show-password
            placeholder="留空则不修改密码；填写需至少6位"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="accountDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="submitAccountUpdate" :loading="submitAccountLoading">
            确认保存
          </el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import api from '../../api/index'
import { ElMessage, ElMessageBox } from 'element-plus'

const allSuppliers = ref([])
const loading = ref(false)
const searchQuery = ref('')

const userRole = computed(() => localStorage.getItem('role') || '')
const canManage = computed(() => ['admin', 'buyer'].includes(userRole.value))

const dialogVisible = ref(false)
const currentSupplierId = ref(null)
const currentSupplierName = ref('')
const submitLoading = ref(false)
const addDialogVisible = ref(false)
const submitAddLoading = ref(false)
const addFormRef = ref(null)
const accountDialogVisible = ref(false)
const submitAccountLoading = ref(false)
const accountFormRef = ref(null)

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

const accountForm = ref({
  username: '',
  password: ''
})

const addRules = {
  name: [{ required: true, message: '请输入供应商名称', trigger: 'blur' }]
}

const accountRules = {
  username: [{ required: true, message: '请输入登录账号', trigger: 'blur' }],
  password: [
    {
      validator: (_, value, callback) => {
        if (!value || value.length >= 6) {
          callback()
          return
        }
        callback(new Error('密码长度至少6位'))
      },
      trigger: 'blur'
    }
  ]
}

const fetchSuppliers = async () => {
  loading.value = true
  try {
    const res = await api.get('/supplier/list')
    allSuppliers.value = res.data
  } catch (error) {
    console.error(error)
  } finally {
    loading.value = false
  }
}

// Only show approved/rejected suppliers in this view
const suppliers = computed(() => {
  return allSuppliers.value.filter(s => s.status !== 'pending')
})

const filteredSuppliers = computed(() => {
  const keyword = searchQuery.value.trim().toLowerCase()
  if (!keyword) {
    return suppliers.value
  }
  return suppliers.value.filter((supplier) =>
    (supplier.name || '').toLowerCase().includes(keyword)
  )
})

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
      fetchSuppliers()
    } catch (error) {
      console.error(error)
      ElMessage.error(error.response?.data?.detail || '创建失败')
    } finally {
      submitAddLoading.value = false
    }
  })
}

const handleAccountEdit = (row) => {
  currentSupplierId.value = row.id
  currentSupplierName.value = row.name
  accountForm.value.username = row.account_username || ''
  accountForm.value.password = ''
  accountDialogVisible.value = true
}

const resetAccountForm = () => {
  if (accountFormRef.value) {
    accountFormRef.value.clearValidate()
  }
  accountForm.value.password = ''
}

const submitAccountUpdate = async () => {
  if (!accountFormRef.value) return
  await accountFormRef.value.validate(async (valid) => {
    if (!valid) return
    submitAccountLoading.value = true
    try {
      await api.put(`/supplier/${currentSupplierId.value}/account`, {
        username: accountForm.value.username,
        password: accountForm.value.password || undefined
      })
      ElMessage.success('账号信息更新成功')
      accountDialogVisible.value = false
      fetchSuppliers()
    } catch (error) {
      console.error(error)
      ElMessage.error(error.response?.data?.detail || '账号更新失败')
    } finally {
      submitAccountLoading.value = false
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
    fetchSuppliers()
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
    fetchSuppliers()
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
</style>
