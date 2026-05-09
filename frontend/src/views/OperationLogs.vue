<template>
  <div class="page-container">
    <div class="header">
      <h2>系统操作日志</h2>
      <el-button type="primary" icon="Refresh" circle @click="fetchLogs" :loading="loading" />
    </div>

    <div class="content-card">
      <el-table :data="logs" style="width: 100%" v-loading="loading" stripe border>
        <el-table-column type="index" label="序号" width="80" align="center" />
        <el-table-column prop="created_at" label="操作时间" width="180" align="center" />
        <el-table-column prop="username" label="操作账号" width="150" align="center" />
        <el-table-column prop="action_type" label="操作类型" width="180" align="center">
          <template #default="{ row }">
            <el-tag :type="getActionTagType(row.action_type)">
              {{ row.action_type }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="detail" label="详细描述" min-width="300" show-overflow-tooltip />
      </el-table>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../api/index'

const loading = ref(false)
const logs = ref([])

const fetchLogs = async () => {
  loading.value = true
  try {
    const res = await api.get('/system/logs')
    logs.value = res.data
  } catch (error) {
    console.error(error)
    ElMessage.error('获取操作日志失败')
  } finally {
    loading.value = false
  }
}

const getActionTagType = (action) => {
  const map = {
    'LOGIN': 'info',
    'CREATE_USER': 'success',
    'DELETE_USER': 'danger',
    'CREATE_INQUIRY': 'primary',
    'UPDATE_SUPPLIER': 'warning',
    'SEND_WARNING': 'danger'
  }
  return map[action] || 'info'
}

onMounted(() => {
  fetchLogs()
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