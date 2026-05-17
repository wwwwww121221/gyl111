<template>
  <div class="page-container">
    <div class="header">
      <h2>系统操作日志</h2>
      <el-button type="primary" icon="Refresh" circle @click="fetchLogs" :loading="loading" />
    </div>

    <div class="content-card">
      <el-table :data="logs" style="width: 100%" v-loading="loading" stripe border>
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
        <el-table-column label="操作对象" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">
            {{ formatTarget(row) }}
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
    admin: '管理员',
    buyer: '采购员',
    supplier: '供应商'
  }
  return map[normalizedRole] || (role || '未知')
}

const getRoleTagType = (role) => {
  const normalizedRole = String(role || '').toLowerCase()
  const map = {
    admin: 'danger',
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
  if (targetType && targetName) return `${targetType} / ${targetName}`
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
    return value.map((item) => formatExtraValue(item)).join('；')
  }
  if (typeof value === 'object') {
    return Object.entries(value)
      .map(([key, val]) => `${key}: ${formatExtraValue(val)}`)
      .join('；')
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
