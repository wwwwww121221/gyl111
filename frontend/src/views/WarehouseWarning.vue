<template>
  <div class="dashboard-container">
    <div class="header">
      <div class="header-left">
        <h1 class="dashboard-title">仓库入库预警看板</h1>
        <el-button type="primary" :icon="Refresh" circle @click="handleRefresh" :loading="loading" class="refresh-btn" />
        <span class="refresh-time">最后更新: {{ lastUpdateTime }}</span>
      </div>
    </div>

    <!-- Summary Statistics -->
    <div class="summary-section">
      <div class="summary-item">
        <div class="summary-label">待入库订单 (Pending Stockin)</div>
        <div class="summary-value">{{ summary.total_items }}</div>
      </div>
      <div class="summary-item">
        <div class="summary-label">总物料数量 (Total Material Qty)</div>
        <div class="summary-value">{{ summary.total_qty.toFixed(0) }}</div>
      </div>
      <div class="summary-item">
        <div class="summary-label">总供应商数量 (Total Suppliers)</div>
        <div class="summary-value warning">{{ summary.supplier_count }}</div>
      </div>
    </div>

    <!-- Filter Toolbar -->
    <div class="filter-toolbar">
      <div class="filter-left">
        <el-input
          v-model="searchQuery"
          placeholder="搜索物料/项目号/供应商..."
          prefix-icon="Search"
          clearable
          style="width: 300px; margin-right: 15px;"
        />
        <el-select
          v-model="filterDays"
          placeholder="到期时间筛选"
          clearable
          style="width: 150px"
        >
          <el-option label="全部" value="" />
          <el-option label="今天到期" :value="0" />
          <el-option label="1天内到期" :value="1" />
          <el-option label="2天内到期" :value="2" />
          <el-option label="3天内到期" :value="3" />
          <el-option label="已逾期" :value="-1" />
        </el-select>
      </div>
    </div>

    <!-- Main Content: Grouped by Supplier -->
    <div class="main-content" v-loading="loading">
      <template v-if="Object.keys(groupedData).length > 0">
        <div v-for="(group, supplierName) in groupedData" :key="supplierName" class="supplier-card">
          <div class="supplier-header">
            <span class="supplier-name">{{ supplierName }}</span>
            <span class="supplier-badge">{{ group.length }} 项物料</span>
            <el-button type="warning" size="small" @click="handleSendWarning(supplierName, group)" style="margin-left: auto;">催促入库</el-button>
          </div>
          
          <el-table :data="group" style="width: 100%" size="small" :row-class-name="tableRowClassName" border>
            <el-table-column prop="material_name" label="物料名称 (Material)" min-width="180" show-overflow-tooltip />
            <el-table-column prop="project_number" label="项目号 (Project)" width="150" show-overflow-tooltip />
            <el-table-column 
              prop="warning_unstockin_qty"
              label="未入库数量" 
              width="120" 
              align="center" 
            />
            <el-table-column prop="delivery_date" label="交货日期" width="180" align="center">
              <template #default="scope">
                {{ formatDateTime(scope.row.delivery_date) }}
              </template>
            </el-table-column>
            <el-table-column label="状态 (Status)" width="150" align="center">
              <template #default="scope">
                <el-tag :type="getStatusType(scope.row.days_remaining)" effect="dark" size="small">
                  {{ getStatusText(scope.row.days_remaining) }}
                </el-tag>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </template>
      <el-empty v-else description="暂无符合条件的数据" />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { getWarningDashboard, sendWarningToSupplier } from '../api/warning'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh, Search } from '@element-plus/icons-vue'

const loading = ref(false)
const lastUpdateTime = ref('-')
const searchQuery = ref('')
const filterDays = ref('') // '' for all, number for days

const unstockinList = ref([])

// Helper to calculate days remaining
const calculateDaysRemaining = (dateStr) => {
  const deliveryDate = new Date(dateStr)
  const now = new Date()
  // Reset time part for accurate day calculation
  now.setHours(0, 0, 0, 0)
  deliveryDate.setHours(0, 0, 0, 0)
  
  const diffTime = deliveryDate - now
  return Math.ceil(diffTime / (1000 * 60 * 60 * 24))
}

// 1. First filter the raw list based on search and days
const filteredList = computed(() => {
  let result = unstockinList.value

  // Search Filter (物料/项目号/供应商)
  if (searchQuery.value) {
    const query = searchQuery.value.toLowerCase()
    result = result.filter(item => 
      (item.material_name && item.material_name.toLowerCase().includes(query)) || 
      (item.project_number && item.project_number.toLowerCase().includes(query)) ||
      (item.supplier_name && item.supplier_name.toLowerCase().includes(query))
    )
  }

  // Days Filter
  if (filterDays.value !== '') {
    result = result.filter(item => {
      const days = calculateDaysRemaining(item.delivery_date)
      if (filterDays.value === -1) {
        return days < 0 // Overdue
      } else {
        return days <= filterDays.value && days >= 0
      }
    })
  }

  return result
})

// 2. Then Aggregate: Same Material + Project + Delivery Date
const aggregatedList = computed(() => {
  const map = new Map()
  
  filteredList.value.forEach(item => {
    // Create a unique key
    const key = `${item.supplier_name}_${item.material_name}_${item.project_number}_${item.delivery_date}`
    
    if (map.has(key)) {
      const existing = map.get(key)
      existing.warning_unstockin_qty += item.warning_unstockin_qty
    } else {
      map.set(key, { ...item }) // Clone item
    }
  })
  
  return Array.from(map.values())
})

const summary = computed(() => {
  const list = aggregatedList.value
  let totalQty = list.reduce((sum, item) => sum + item.warning_unstockin_qty, 0)
  
  const suppliers = new Set(list.map(item => item.supplier_name).filter(Boolean))
  
  return {
    total_items: list.length,
    total_qty: totalQty,
    supplier_count: suppliers.size
  }
})

// 3. Finally Group by Supplier for UI
const groupedData = computed(() => {
  const groups = {}
  aggregatedList.value.forEach(item => {
    const supplier = item.supplier_name || '未知供应商'
    if (!groups[supplier]) {
      groups[supplier] = []
    }
    // Calculate days remaining dynamically for display
    item.days_remaining = calculateDaysRemaining(item.delivery_date)
    groups[supplier].push(item)
  })
  return groups
})

const handleRefresh = async () => {
  loading.value = true
  try {
    const res = await getWarningDashboard()
    if (res.data && res.data.warehouse_unstockin) {
      unstockinList.value = res.data.warehouse_unstockin
    } else {
      unstockinList.value = []
    }
    lastUpdateTime.value = new Date().toLocaleString()
  } catch (error) {
    console.error('Failed to fetch warning dashboard data', error)
    ElMessage.error('获取预警数据失败')
  } finally {
    loading.value = false
  }
}

const handleSendWarning = async (supplierName, items) => {
  try {
    await ElMessageBox.confirm(
      `确定要向仓库发送催办通知吗？将包含 ${items.length} 项逾期或即将逾期的物料信息。`,
      '催促入库',
      {
        confirmButtonText: '确定发送',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )
    ElMessage.success(`预警已发送给仓库管理人员`)
  } catch (e) {
    if (e !== 'cancel') {
      console.error(e)
      ElMessage.error('发送预警失败')
    }
  }
}

const formatDateTime = (dateStr) => {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleDateString()
}

const getStatusType = (days) => {
  if (days < 0) return 'danger'       // 红：已逾期
  if (days === 0) return 'warning'    // 橙黄：今天到期
  if (days <= 3) return 'warning'     // 橙黄：即将到期
  return 'success'                    // 绿：安全期内
}

const getStatusText = (days) => {
  if (days < 0) return `已逾期 ${Math.abs(days)} 天`
  if (days === 0) return '紧急：今天到期'
  if (days <= 3) return `即将到期：余 ${days} 天`
  return `正常：余 ${days} 天`
}

const tableRowClassName = ({ row }) => {
  if (row.days_remaining < 0) {
    return 'danger-row'   // 已逾期 - 浅红底色
  } else if (row.days_remaining === 0) {
    return 'urgent-row'   // 今天到期 - 浅黄底色
  } else if (row.days_remaining <= 3) {
    return 'warning-row'  // 3天内到期 - 极浅黄底色
  }
  return 'safe-row'       // 正常交期 - 白色/默认
}

onMounted(() => {
  handleRefresh()
})
</script>

<style scoped>
.dashboard-container {
  padding: 20px;
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-sizing: border-box;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  flex-shrink: 0;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 15px;
}

.dashboard-title {
  margin: 0;
  font-size: 24px;
  color: #303133;
}

.refresh-btn {
  margin-left: 10px;
}

.refresh-time {
  font-size: 12px;
  color: #909399;
}

.summary-section {
  display: flex;
  gap: 20px;
  margin-bottom: 20px;
  flex-shrink: 0;
}

.summary-item {
  flex: 1;
  background: white;
  padding: 20px;
  border-radius: 8px;
  box-shadow: 0 2px 12px 0 rgba(0,0,0,0.05);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}

.summary-label {
  font-size: 14px;
  color: #606266;
  margin-bottom: 10px;
}

.summary-value {
  font-size: 28px;
  font-weight: bold;
  color: #409EFF;
}

.summary-value.warning {
  color: #E6A23C;
}

.filter-toolbar {
  margin-bottom: 20px;
  display: flex;
  align-items: center;
  flex-shrink: 0;
}

.filter-left {
  display: flex;
  align-items: center;
}

.main-content {
  flex: 1;
  overflow-y: auto;
  background: white;
  padding: 20px;
  border-radius: 8px;
  box-shadow: 0 2px 12px 0 rgba(0,0,0,0.05);
}

.supplier-card {
  margin-bottom: 30px;
  border: 1px solid #EBEEF5;
  border-radius: 8px;
  overflow: hidden;
}

.supplier-header {
  background-color: #F5F7FA;
  padding: 10px 15px;
  display: flex;
  align-items: center;
  gap: 15px;
  border-bottom: 1px solid #EBEEF5;
}

.supplier-name {
  font-weight: bold;
  font-size: 16px;
  color: #303133;
}

.supplier-badge {
  background-color: #409EFF;
  color: white;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 12px;
}

/* 表格行高亮状态样式重构 */
:deep(.el-table .danger-row) {
  background-color: #fff0f0 !important; /* 浅红：已逾期 */
}
:deep(.el-table .danger-row:hover > td.el-table__cell) {
  background-color: #fde2e2 !important;
}

:deep(.el-table .urgent-row) {
  background-color: #fff7e6 !important; /* 浅黄：今天到期 */
}
:deep(.el-table .urgent-row:hover > td.el-table__cell) {
  background-color: #ffebd2 !important;
}

:deep(.el-table .warning-row) {
  background-color: #fdfaf4 !important; /* 极浅黄：即将到期 */
}
:deep(.el-table .warning-row:hover > td.el-table__cell) {
  background-color: #fcf1db !important;
}

/* 正常状态就用白色默认即可，避免页面颜色过于花哨 */
:deep(.el-table .safe-row) {
  background-color: #ffffff !important;
}
</style>