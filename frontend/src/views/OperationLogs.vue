<template>
  <div class="page-container">
    <div class="header">
      <h2>系统操作日志</h2>
      <el-button type="primary" icon="Refresh" circle @click="fetchLogs" :loading="loading" />
    </div>

    <div class="content-card">
      <div class="filter-bar">
        <el-date-picker
          v-model="filters.dateRange"
          type="datetimerange"
          range-separator="至"
          start-placeholder="开始时间"
          end-placeholder="结束时间"
          value-format="YYYY-MM-DD HH:mm:ss"
          class="filter-item filter-date"
          clearable
        />
        <el-select v-model="filters.role" placeholder="角色" clearable class="filter-item">
          <el-option v-for="item in roleOptions" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>
        <el-select v-model="filters.module" placeholder="所属模块" clearable class="filter-item">
          <el-option v-for="item in moduleOptions" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>
        <el-select v-model="filters.actionType" placeholder="操作类型" clearable class="filter-item">
          <el-option v-for="item in actionOptions" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>
        <el-select v-model="filters.result" placeholder="结果" clearable class="filter-item">
          <el-option v-for="item in resultOptions" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>
        <el-input
          v-model="filters.keyword"
          placeholder="搜索账号/对象/描述"
          clearable
          class="filter-item filter-keyword"
          @keyup.enter="handleSearch"
        />
        <div class="filter-actions">
          <el-button type="primary" @click="handleSearch" :loading="loading">查询</el-button>
          <el-button @click="resetFilters">重置</el-button>
        </div>
      </div>

      <el-table :data="displayLogs" style="width: 100%" v-loading="loading" stripe border>
        <el-table-column type="expand" width="54">
          <template #default="{ row }">
            <div class="log-expand-card">
              <div class="log-detail-list">
                <div
                  v-for="item in buildLogDetails(row)"
                  :key="item.label"
                  class="log-detail-row"
                >
                  <div class="log-detail-label">{{ item.label }}</div>
                  <div class="log-detail-value">{{ item.value }}</div>
                </div>
              </div>

              <div v-if="hasExtraData(row.extra_data)" class="log-extra-block">
                <div class="log-extra-title">补充明细</div>
                <el-table :data="toExtraRows(row.extra_data)" size="small" border>
                  <el-table-column prop="label" label="字段" width="180" />
                  <el-table-column prop="value" label="内容" min-width="360">
                    <template #default="{ row: extraRow }">
                      <div class="log-extra-value">{{ extraRow.value }}</div>
                    </template>
                  </el-table-column>
                </el-table>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column type="index" label="序号" width="80" align="center" />
        <el-table-column prop="created_at" label="操作时间" width="180" align="center" />
        <el-table-column prop="username" label="操作账号" width="150" align="center" />
        <el-table-column label="角色" width="110" align="center">
          <template #default="{ row }">
            <el-tag
              v-if="row.user_role"
              size="small"
              effect="plain"
              :type="getRoleTagType(row.user_role)"
            >
              {{ getRoleLabel(row.user_role) }}
            </el-tag>
            <span v-else class="log-fallback-text">未知</span>
          </template>
        </el-table-column>
        <el-table-column label="所属模块" width="130" align="center" show-overflow-tooltip>
          <template #default="{ row }">
            <span :class="{ 'log-fallback-text': !row.module }">{{ row.module || '未识别' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="action_type" label="操作类型" width="180" align="center">
          <template #default="{ row }">
            <el-tag :type="getActionTagType(row.action_type)">
              {{ row.action_type }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作对象" min-width="220">
          <template #default="{ row }">
            <div class="target-cell">
              <div class="target-type">{{ row.target_type || '未识别' }}</div>
              <div class="target-name">{{ row.target_name || '-' }}</div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="结果" width="100" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="getResultTagType(row.result)">
              {{ getResultLabel(row.result) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="ip_address" label="IP" width="150" align="center" show-overflow-tooltip />
        <el-table-column prop="detail" label="摘要描述" min-width="260" show-overflow-tooltip />
      </el-table>
    </div>
  </div>
</template>

<script setup>
import { computed, reactive, ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../api/index'

const loading = ref(false)
const rawLogs = ref([])

const createEmptyFilters = () => ({
  dateRange: [],
  role: '',
  module: '',
  actionType: '',
  result: '',
  keyword: ''
})

const filters = reactive(createEmptyFilters())
const appliedFilters = ref(createEmptyFilters())

const roleOptions = [
  { label: '系统管理员', value: 'admin' },
  { label: '采购经理', value: 'buyer_manager' },
  { label: '采购员', value: 'buyer' },
  { label: '供应商', value: 'supplier' }
]

const moduleOptions = [
  { label: '认证中心', value: '认证中心' },
  { label: '账号管理', value: '账号管理' },
  { label: '账号安全', value: '账号安全' },
  { label: '询价管理', value: '询价管理' },
  { label: '供应商管理', value: '供应商管理' },
  { label: '预警管理', value: '预警管理' },
  { label: '系统管理', value: '系统管理' }
]

const actionOptions = [
  { label: '登录', value: 'LOGIN' },
  { label: '创建账号', value: 'CREATE_USER' },
  { label: '删除账号', value: 'DELETE_USER' },
  { label: '修改密码', value: 'CHANGE_PASSWORD' },
  { label: '创建询价', value: 'CREATE_INQUIRY' },
  { label: '更新供应商', value: 'UPDATE_SUPPLIER' },
  { label: '删除供应商', value: 'DELETE_SUPPLIER' },
  { label: '批量重置供应商账号', value: 'RESET_SUPPLIER_ACCOUNTS' },
  { label: '发送预警', value: 'SEND_WARNING' }
]

const resultOptions = [
  { label: '成功', value: 'success' },
  { label: '失败', value: 'failed' },
  { label: '部分成功', value: 'partial' }
]

const buildRequestParams = (sourceFilters) => {
  const params = { limit: 1000 }
  if (sourceFilters.dateRange?.length === 2) {
    params.start_time = sourceFilters.dateRange[0]
    params.end_time = sourceFilters.dateRange[1]
  }
  if (sourceFilters.role) params.role = sourceFilters.role
  if (sourceFilters.module) params.module = sourceFilters.module
  if (sourceFilters.actionType) params.action_type = sourceFilters.actionType
  if (sourceFilters.result) params.result = sourceFilters.result
  if (sourceFilters.keyword?.trim()) params.keyword = sourceFilters.keyword.trim()
  return params
}

const cloneFilters = (sourceFilters) => ({
  dateRange: Array.isArray(sourceFilters.dateRange) ? [...sourceFilters.dateRange] : [],
  role: sourceFilters.role || '',
  module: sourceFilters.module || '',
  actionType: sourceFilters.actionType || '',
  result: sourceFilters.result || '',
  keyword: sourceFilters.keyword || ''
})

const fetchLogs = async (sourceFilters = appliedFilters.value) => {
  loading.value = true
  try {
    const params = buildRequestParams(sourceFilters)
    const res = await api.get('/system/logs', { params })
    rawLogs.value = Array.isArray(res.data) ? res.data : []
  } catch (error) {
    console.error(error)
    ElMessage.error('获取操作日志失败')
  } finally {
    loading.value = false
  }
}

const matchesDateRange = (row, dateRange) => {
  if (!dateRange?.length || !row?.created_at) return true
  const rowTime = new Date(row.created_at.replace(' ', 'T')).getTime()
  const startTime = new Date(dateRange[0].replace(' ', 'T')).getTime()
  const endTime = new Date(dateRange[1].replace(' ', 'T')).getTime()
  return rowTime >= startTime && rowTime <= endTime
}

const matchesKeyword = (row, keyword) => {
  const normalizedKeyword = String(keyword || '').trim().toLowerCase()
  if (!normalizedKeyword) return true
  const haystack = [
    row?.username,
    row?.detail,
    row?.module,
    row?.action_type,
    row?.target_type,
    row?.target_name,
    row?.ip_address,
    getRoleLabel(row?.user_role),
    getResultLabel(row?.result)
  ]
    .filter(Boolean)
    .join(' ')
    .toLowerCase()
  return haystack.includes(normalizedKeyword)
}

const displayLogs = computed(() => {
  const active = appliedFilters.value
  return rawLogs.value.filter((row) => {
    if (active.role && row?.user_role !== active.role) return false
    if (active.module && row?.module !== active.module) return false
    if (active.actionType && row?.action_type !== active.actionType) return false
    if (active.result && row?.result !== active.result) return false
    if (!matchesDateRange(row, active.dateRange)) return false
    if (!matchesKeyword(row, active.keyword)) return false
    return true
  })
})

const handleSearch = async () => {
  appliedFilters.value = cloneFilters(filters)
  await fetchLogs(appliedFilters.value)
}

const resetFilters = () => {
  Object.assign(filters, createEmptyFilters())
  appliedFilters.value = createEmptyFilters()
  fetchLogs(appliedFilters.value)
}

const getActionTagType = (action) => {
  const map = {
    'LOGIN': 'info',
    'CREATE_USER': 'success',
    'DELETE_USER': 'danger',
    'CREATE_INQUIRY': 'primary',
    'UPDATE_SUPPLIER': 'warning',
    'SEND_WARNING': 'danger',
    'RESET_SUPPLIER_ACCOUNTS': 'warning',
    'DELETE_SUPPLIER': 'danger',
    'CHANGE_PASSWORD': 'info'
  }
  return map[action] || 'info'
}

const getRoleLabel = (role) => {
  const normalizedRole = String(role || '').toLowerCase()
  const map = {
    admin: '系统管理员',
    buyer_manager: '采购经理',
    buyer: '采购员',
    supplier: '供应商'
  }
  return map[normalizedRole] || (role || '未知')
}

const getRoleTagType = (role) => {
  const normalizedRole = String(role || '').toLowerCase()
  const map = {
    admin: 'danger',
    buyer_manager: 'warning',
    buyer: 'primary',
    supplier: 'success'
  }
  return map[normalizedRole] || 'info'
}

const getResultLabel = (result) => {
  const map = {
    success: '成功',
    failed: '失败',
    partial: '部分成功'
  }
  return map[result] || (result || '成功')
}

const getResultTagType = (result) => {
  const map = {
    success: 'success',
    failed: 'danger',
    partial: 'warning'
  }
  return map[result] || 'info'
}

const formatTarget = (row) => {
  const targetType = row?.target_type || ''
  const targetName = row?.target_name || ''
  if (targetType && targetName) return `${targetType}\n${targetName}`
  return targetName || targetType || '未识别'
}

const buildLogDetails = (row) => {
  return [
    { label: '操作时间', value: row?.created_at || '-' },
    { label: '操作 IP', value: row?.ip_address || '-' },
    { label: '操作账号', value: row?.username || '-' },
    { label: '账号角色', value: getRoleLabel(row?.user_role) },
    { label: '所属模块', value: row?.module || '未识别' },
    { label: '操作类型', value: row?.action_type || '-' },
    { label: '操作对象', value: formatTarget(row) },
    { label: '执行结果', value: getResultLabel(row?.result) },
    { label: '摘要描述', value: row?.detail || '-' }
  ]
}

const hasExtraData = (extraData) => {
  return extraData && typeof extraData === 'object' && Object.keys(extraData).length > 0
}

const formatExtraValue = (value) => {
  if (value === null || value === undefined || value === '') return '-'
  if (Array.isArray(value)) {
    return value.map((item) => formatExtraValue(item)).join('\n')
  }
  if (typeof value === 'object') {
    return Object.entries(value)
      .map(([key, val]) => `${key}: ${formatExtraValue(val)}`)
      .join('\n')
  }
  return String(value)
}

const toExtraRows = (extraData) => {
  if (!hasExtraData(extraData)) return []
  return Object.entries(extraData).map(([key, value]) => ({
    label: key,
    value: formatExtraValue(value)
  }))
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

.filter-bar {
  display: flex;
  flex-wrap: nowrap;
  gap: 8px;
  align-items: center;
  margin-bottom: 16px;
  overflow-x: auto;
}

.filter-item {
  width: 120px;
  flex: 0 0 120px;
}

.filter-date {
  width: 280px;
  flex: 0 0 280px;
}

.filter-keyword {
  width: 180px;
  flex: 0 0 180px;
}

.filter-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 0 0 auto;
}

:deep(.filter-item .el-input__wrapper),
:deep(.filter-item .el-select__wrapper),
:deep(.filter-date .el-input__wrapper) {
  width: 100%;
}

.target-cell {
  line-height: 1.5;
}

.target-type {
  color: #909399;
  font-size: 12px;
}

.target-name {
  color: #303133;
  word-break: break-all;
}

.log-expand-card {
  padding: 12px 8px;
}

.log-detail-list {
  border: 1px solid var(--el-border-color-lighter);
  border-bottom: none;
}

.log-detail-row {
  display: grid;
  grid-template-columns: 140px 1fr;
}

.log-detail-label,
.log-detail-value {
  padding: 10px 12px;
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.log-detail-label {
  background: var(--el-fill-color-lighter);
  color: #606266;
  font-weight: 600;
}

.log-detail-value {
  color: #303133;
  white-space: pre-wrap;
  word-break: break-all;
}

.log-extra-block {
  margin-top: 12px;
}

.log-extra-title {
  margin-bottom: 8px;
  font-size: 14px;
  font-weight: 600;
  color: #303133;
}

.log-extra-value {
  white-space: pre-wrap;
  line-height: 1.6;
  color: #606266;
}

.log-fallback-text {
  color: #909399;
}
</style>
