<template>
  <div class="analysis-container">
    <el-card class="table-card" shadow="hover" v-loading="loading">
      <template #header>
        <div class="card-header">
          <span>采购员分析</span>
          <el-button type="primary" link :icon="Refresh" @click="fetchData" :loading="loading">刷新数据</el-button>
        </div>
      </template>

      <el-table :data="tableData" border stripe style="width: 100%" max-height="600">
        <el-table-column type="index" label="排名" width="70" align="center" />
        <el-table-column prop="username" label="采购员账号" min-width="180" align="center">
          <template #default="{ row }">
            <span class="buyer-name">{{ row.username }}</span>
            <el-tag v-if="row.role === 'admin'" size="small" type="danger" class="role-tag">超管</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="total_tasks" label="发起询价单总数" width="170" align="center" sortable />
        <el-table-column prop="contracts_count" label="定标生成合同数" width="170" align="center" sortable>
          <template #default="{ row }">
            <el-tag type="success">{{ row.contracts_count }} 份</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="warnings_count" label="发送催单预警数" width="170" align="center" sortable>
          <template #default="{ row }">
            <el-tag type="warning">{{ row.warnings_count }} 次</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="approved_suppliers" label="审核引入供应商数" width="180" align="center" sortable />
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import api from '../../api/index'

const loading = ref(false)
const tableData = ref([])

const fetchData = async () => {
  loading.value = true
  try {
    const res = await api.get('/system/buyer-analysis')
    tableData.value = (res.data || []).sort((a, b) => b.total_tasks - a.total_tasks)
  } catch (error) {
    console.error('Failed to fetch buyer analysis:', error)
    ElMessage.error('获取采购员分析数据失败')
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchData()
})
</script>

<style scoped>
.analysis-container {
  height: 100%;
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 20px 24px;
  background: #f5f7fb;
  box-sizing: border-box;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.page-title {
  margin: 0;
  font-size: 18px;
  font-weight: 700;
  color: #1f2a44;
}

.table-card {
  flex: 1;
  min-height: 0;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 16px;
  font-weight: 700;
  color: #1f2a44;
}

.buyer-name {
  font-weight: 700;
}

.role-tag {
  margin-left: 8px;
}
</style>
