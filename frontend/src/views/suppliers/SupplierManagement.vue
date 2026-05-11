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
      </div>

      <el-table :data="filteredSuppliers" style="width: 100%" v-loading="loading">
        <el-table-column type="index" label="序号" width="80" />
        <el-table-column prop="name" label="供应商名称" />      
        <el-table-column prop="contact_person" label="联系人" />
        <el-table-column prop="phone" label="联系电话" />
        <el-table-column prop="email" label="电子邮箱" />
        
        <el-table-column prop="level" label="等级">
          <template #default="{ row }">
            <el-tag :type="row.level === 'core' ? 'success' : 'info'">     
              {{ row.level === 'core' ? '核心供应商' : '一般供应商' }}
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

        <el-table-column label="操作" width="220" v-if="userRole === 'admin'">
          <template #default="{ row }">
            <el-button size="small" type="primary" @click="handleEdit(row)">
              管理等级/状态
            </el-button>
            <el-button size="small" type="danger" plain @click="handleDelete(row)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

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

        <el-form-item label="供应商等级">
          <el-radio-group v-model="editForm.level">
            <el-radio label="general">一般</el-radio>
            <el-radio label="core">核心</el-radio>
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

const dialogVisible = ref(false)
const currentSupplierId = ref(null)
const currentSupplierName = ref('')
const submitLoading = ref(false)

const editForm = ref({
  status: 'approved',
  level: 'general'
})

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
  editForm.value.level = row.level || 'general'
  dialogVisible.value = true
}

const submitUpdate = async () => {
  submitLoading.value = true
  try {
    await api.put(`/supplier/${currentSupplierId.value}`, {
      status: editForm.value.status,
      level: editForm.value.level
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
