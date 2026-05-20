<template>
  <div class="page-container">
    <div class="content-card">
      <el-tabs v-model="activeTab">
        <el-tab-pane label="待审核供应商" name="suppliers">
          <el-table :data="pendingSuppliers" v-loading="loadingSuppliers" style="width: 100%">
            <el-table-column type="index" label="序号" width="72" />
            <el-table-column prop="name" label="供应商名称" min-width="220" />
            <el-table-column prop="social_credit_code" label="统一社会信用代码" min-width="180" />
            <el-table-column prop="contact_person" label="联系人" width="140" />
            <el-table-column prop="phone" label="手机号" width="140" />
            <el-table-column prop="email" label="邮箱" min-width="180" />
            <el-table-column label="状态" width="110">
              <template #default>
                <el-tag type="warning">待审核</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="220">
              <template #default="{ row }">
                <el-button size="small" type="success" @click="approveSupplier(row)">通过</el-button>
                <el-button size="small" type="danger" @click="rejectSupplier(row)">拒绝</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane label="待审核成员申请" name="members">
          <el-table :data="pendingMembers" v-loading="loadingMembers" style="width: 100%">
            <el-table-column type="index" label="序号" width="72" />
            <el-table-column prop="supplier_name" label="企业名称" min-width="220" />
            <el-table-column prop="member_name" label="申请人" width="130" />
            <el-table-column prop="phone" label="手机号" width="140" />
            <el-table-column prop="position" label="职位" width="140" />
            <el-table-column prop="approval_mode" label="审核方式" width="150">
              <template #default="{ row }">
                {{ row.approval_mode === 'supplier_admin' ? '供应商管理员审核' : '平台管理员审核' }}
              </template>
            </el-table-column>
            <el-table-column prop="application_note" label="申请说明" min-width="220" show-overflow-tooltip />
            <el-table-column label="附件" width="120">
              <template #default="{ row }">
                <span>{{ row.application_attachments?.length || 0 }} 个</span>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="220">
              <template #default="{ row }">
                <el-button size="small" type="success" @click="approveMember(row)">通过</el-button>
                <el-button size="small" type="danger" @click="rejectMember(row)">拒绝</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../../api'

const activeTab = ref('suppliers')
const loadingSuppliers = ref(false)
const loadingMembers = ref(false)
const pendingSuppliers = ref([])
const pendingMembers = ref([])

const fetchPendingSuppliers = async () => {
  loadingSuppliers.value = true
  try {
    const res = await api.get('/supplier/list')
    pendingSuppliers.value = (res.data || []).filter((item) => item.status === 'pending')
  } catch (error) {
    console.error(error)
  } finally {
    loadingSuppliers.value = false
  }
}

const fetchPendingMembers = async () => {
  loadingMembers.value = true
  try {
    const res = await api.get('/auth/supplier/member-requests', { params: { status_filter: 'pending' } })
    pendingMembers.value = res.data || []
  } catch (error) {
    console.error(error)
  } finally {
    loadingMembers.value = false
  }
}

const approveSupplier = async (row) => {
  try {
    await ElMessageBox.confirm(`确认通过供应商“${row.name}”的入驻申请吗？`, '审核确认', {
      type: 'warning',
    })
    await api.put(`/supplier/${row.id}`, { status: 'approved', level: 'general' })
    ElMessage.success('供应商已审核通过')
    fetchPendingSuppliers()
  } catch (error) {
    if (error !== 'cancel') console.error(error)
  }
}

const rejectSupplier = async (row) => {
  try {
    await ElMessageBox.confirm(`确认拒绝供应商“${row.name}”的入驻申请吗？`, '审核确认', {
      type: 'warning',
    })
    await api.put(`/supplier/${row.id}`, { status: 'rejected' })
    ElMessage.success('供应商申请已拒绝')
    fetchPendingSuppliers()
  } catch (error) {
    if (error !== 'cancel') console.error(error)
  }
}

const approveMember = async (row) => {
  try {
    await ElMessageBox.confirm(`确认通过 ${row.member_name} 加入 ${row.supplier_name} 的申请吗？`, '审核确认', {
      type: 'warning',
    })
    await api.put(`/auth/supplier/member-requests/${row.id}/review`, { status: 'approved', role: row.role || 'member' })
    ElMessage.success('成员申请已通过')
    fetchPendingMembers()
  } catch (error) {
    if (error !== 'cancel') console.error(error)
  }
}

const rejectMember = async (row) => {
  try {
    await ElMessageBox.confirm(`确认拒绝 ${row.member_name} 的加入申请吗？`, '审核确认', {
      type: 'warning',
    })
    await api.put(`/auth/supplier/member-requests/${row.id}/review`, { status: 'rejected' })
    ElMessage.success('成员申请已拒绝')
    fetchPendingMembers()
  } catch (error) {
    if (error !== 'cancel') console.error(error)
  }
}

onMounted(() => {
  fetchPendingSuppliers()
  fetchPendingMembers()
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
</style>
