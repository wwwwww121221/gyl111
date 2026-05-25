<template>
  <div class="page-container">
    <div class="header">
      <h2>系统账号管理</h2>
      <el-button type="primary" @click="dialogVisible = true">
        {{ dialogTitle }}
      </el-button>
    </div>

    <div class="content-card">
      <el-table :data="users" style="width: 100%" v-loading="loading" stripe border>
        <el-table-column type="index" label="序号" width="80" align="center" />
        <el-table-column prop="username" label="账号/姓名" />
        <el-table-column prop="role" label="角色" width="160">
          <template #default="{ row }">
            <el-tag :type="getRoleTagType(row.role)">
              {{ getRoleLabel(row.role) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="department" label="所属部门" width="140" />
        <el-table-column label="操作" width="150" align="center">
          <template #default="{ row }">
            <el-button 
              size="small" 
              type="danger" 
              plain
              @click="handleDelete(row)"
              :disabled="row.role === 'admin'"
            >
              删除账号
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 新增采购部账号弹窗 -->
    <el-dialog
      v-model="dialogVisible"
      :title="dialogTitle"
      width="420px"
      draggable
      overflow
      @close="resetForm"
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="80px">
        <el-form-item label="登录账号" prop="username">
          <el-input v-model="form.username" placeholder="建议输入员工姓名拼音" />
        </el-form-item>
        <el-form-item label="初始密码" prop="password">
          <el-input v-model="form.password" type="password" show-password placeholder="请输入至少6位密码" />
        </el-form-item>
        <el-form-item label="所属部门" prop="department">
          <el-select v-model="form.department" style="width: 100%" placeholder="请选择部门" @change="onDepartmentChange">
            <el-option v-for="dept in availableDepartments" :key="dept" :label="dept" :value="dept" />
          </el-select>
        </el-form-item>
        <el-form-item label="账号角色" prop="role">
          <el-select v-model="form.role" style="width: 100%">
            <el-option v-for="opt in roleOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="dialogVisible = false">取消</el-button>
          <el-button type="primary" @click="submitAdd" :loading="submitLoading">
            确认创建
          </el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../api/index'

const loading = ref(false)
const users = ref([])

const dialogVisible = ref(false)
const submitLoading = ref(false)
const formRef = ref(null)

const form = ref({
  username: '',
  password: '',
  role: 'buyer',
  department: ''
})

const allDepartments = ['采购部', '品质部', '仓储部', '技术部']

const currentUserRole = computed(() => localStorage.getItem('role') || '')

const dialogTitle = computed(() => {
  if (currentUserRole.value === 'admin') return '新增账号'
  return '新增采购部账号'
})

const availableDepartments = computed(() => {
  if (currentUserRole.value === 'admin') return allDepartments
  return ['采购部']
})

const roleOptions = computed(() => {
  const dept = form.value.department
  if (currentUserRole.value !== 'admin' || dept === '采购部') {
    return [
      { label: '采购员', value: 'buyer' },
      { label: '采购部经理', value: 'buyer_manager' }
    ]
  }
  return [{ label: '考核专员', value: 'scorer' }]
})

const onDepartmentChange = (dept) => {
  if (dept === '采购部') {
    form.value.role = 'buyer'
  } else {
    form.value.role = 'scorer'
  }
}

const rules = {
  username: [
    { required: true, message: '请输入登录账号', trigger: 'blur' },
    { min: 3, message: '账号长度至少3位', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入初始密码', trigger: 'blur' },
    { min: 6, message: '密码长度至少6位', trigger: 'blur' }
  ],
  role: [
    { required: true, message: '请选择账号角色', trigger: 'change' }
  ],
  department: [
    { required: true, message: '请输入所属部门', trigger: 'blur' }
  ]
}

const getRoleLabel = (role) => {
  const map = {
    admin: '超级管理员',
    buyer_manager: '采购部经理',
    buyer: '采购员',
    scorer: '考核专员'
  }
  return map[role] || role
}

const getRoleTagType = (role) => {
  if (role === 'admin') return 'danger'
  if (role === 'buyer_manager') return 'warning'
  if (role === 'scorer') return ''
  return 'primary'
}

const fetchUsers = async () => {
  loading.value = true
  try {
    const res = await api.get('/auth/users')
    users.value = res.data
  } catch (error) {
    console.error(error)
    ElMessage.error('获取账号列表失败')
  } finally {
    loading.value = false
  }
}

const resetForm = () => {
  if (formRef.value) {
    formRef.value.resetFields()
  }
  const isSuperAdmin = currentUserRole.value === 'admin'
  form.value = {
    username: '',
    password: '',
    role: 'buyer',
    department: isSuperAdmin ? '' : '采购部'
  }
}

const submitAdd = async () => {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (valid) {
      submitLoading.value = true
      try {
        await api.post('/auth/register', form.value)
        ElMessage.success(`${getRoleLabel(form.value.role)}账号创建成功`)
        dialogVisible.value = false
        fetchUsers()
      } catch (error) {
        console.error(error)
        ElMessage.error(error.response?.data?.detail || '账号创建失败')
      } finally {
        submitLoading.value = false
      }
    }
  })
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm(
      `确定要永久删除${getRoleLabel(row.role)} "${row.username}" 的账号吗？删除后该员工将无法登录系统！`,
      '高危操作警告',
      {
        confirmButtonText: '确认删除',
        cancelButtonText: '取消',
        type: 'error',
      }
    )
    
    loading.value = true
    await api.delete(`/auth/users/${row.id}`)
    ElMessage.success('账号已成功删除')
    fetchUsers()
  } catch (error) {
    if (error !== 'cancel') {
      console.error(error)
      ElMessage.error(error.response?.data?.detail || '删除失败')
    }
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchUsers()
})
</script>

<style scoped>
.page-container {
  padding: 20px;
}
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}
.header h2 {
  margin: 0;
  font-size: 20px;
  color: #303133;
}
.content-card {
  background: white;
  padding: 20px;
  border-radius: 8px;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.05);
}
</style>
