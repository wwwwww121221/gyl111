<template>
  <div class="analysis-container">
    <div class="header-section">
      <h1 class="page-title">采购员工作效能分析</h1>
      <div class="header-actions">
        <el-button type="primary" icon="Refresh" @click="fetchData" :loading="loading">刷新数据</el-button>
      </div>
    </div>

    <div class="table-wrapper" v-loading="loading">
      <el-card shadow="hover" class="table-card">
        <template #header>
          <div class="card-header">
            <span>各采购员业务数据汇总</span>
          </div>
        </template>
        <el-table :data="tableData" border stripe style="width: 100%" max-height="600">
          <el-table-column type="index" label="排名" width="60" align="center" />
          <el-table-column prop="username" label="采购员账号" min-width="150" align="center">
            <template #default="{ row }">
              <span style="font-weight: bold;">{{ row.username }}</span>
              <el-tag v-if="row.role === 'admin'" size="small" type="danger" style="margin-left: 8px">超管</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="total_tasks" label="发起询价单总数" width="160" align="center" sortable />
          <el-table-column prop="contracts_count" label="定标生成合同数" width="160" align="center" sortable>
            <template #default="{ row }">
              <el-tag type="success">{{ row.contracts_count }} 份</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="warnings_count" label="发送催单预警数" width="160" align="center" sortable>
            <template #default="{ row }">
              <el-tag type="warning">{{ row.warnings_count }} 次</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="approved_suppliers" label="审核引入供应商数" width="180" align="center" sortable />
        </el-table>
      </el-card>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../../api/index'

const loading = ref(false)
const tableData = ref([])

const fetchData = async () => {
  loading.value = true
  try {
    const res = await api.get('/system/buyer-analysis')
    // 默认按发单数降序排序
    tableData.value = res.data.sort((a, b) => b.total_tasks - a.total_tasks)
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
  padding: 20px;
  background-color: #f0f2f5;
  box-sizing: border-box;
}

.header-section {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  flex-shrink: 0;
}

.page-title {
  margin: 0;
  font-size: 24px;
  color: #303133;
  font-weight: 600;
}

.table-wrapper {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.table-card {
  flex: 1;
  display: flex;
  flex-direction: column;
  border-radius: 8px;
}

:deep(.table-card .el-card__body) {
  flex: 1;
  padding: 0;
  overflow: hidden;
}

.card-header {
  font-weight: bold;
  font-size: 16px;
}
</style>