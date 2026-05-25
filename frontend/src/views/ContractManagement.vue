<template>
  <div class="page-container">
    <div class="content-card">
      <div class="toolbar">
        <el-input
          v-model="searchKeyword"
          placeholder="搜索合同编号 / 询价单 / 供应商 / 状态"
          clearable
          style="width: 360px"
          @keyup.enter="handleSearch"
          @clear="handleSearch"
        />
        <el-button type="primary" @click="handleSearch">搜索</el-button>
      </div>

      <el-table :data="contracts" v-loading="loading" style="width: 100%" border>
        <el-table-column prop="contract_no" label="合同编号" width="130" header-align="center" align="center" />
        <el-table-column prop="inquiry_name" label="项目/询价单" min-width="180" header-align="center" align="center" />
        <el-table-column prop="supplier_name" label="供应商" min-width="160" header-align="center" align="center" />
        <el-table-column label="使用模板" min-width="180" header-align="center" align="center" show-overflow-tooltip>
          <template #default="{ row }">
            <span :class="{ 'template-fallback-text': !row.template_name }">
              {{ row.template_name || '默认/历史模板' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="总金额" min-width="120" header-align="center" align="center">
          <template #default="{ row }">
            {{ formatAmount(row.total_amount) }}
          </template>
        </el-table-column>
        <el-table-column label="状态" min-width="130" header-align="center" align="center">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">
              {{ row.status || '未知' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right" align="center" header-align="center">
          <template #default="{ row }">
            <div class="action-cell">
              <el-button link type="primary" :disabled="!canPreviewOrDownload(row)" @click="handlePreview(row)">预览</el-button>
              <el-button link type="success" :disabled="!canPreviewOrDownload(row)" @click="handleDownload(row)">下载</el-button>
              <el-dropdown trigger="click" @command="(command) => handleActionCommand(row, command)">
                <el-button link type="info" class="more-btn">
                  更多
                  <el-icon class="el-icon--right"><MoreFilled /></el-icon>
                </el-button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item v-if="canRegenerate(row)" command="regenerate">
                      {{ isFailedStatus(row?.status) ? '重试生成' : '重新生成' }}
                    </el-dropdown-item>
                    <el-dropdown-item command="delete">删除</el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </div>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-wrap">
        <el-pagination
          background
          layout="total, prev, pager, next, sizes"
          :total="total"
          :page-size="pageSize"
          :current-page="currentPage"
          :page-sizes="[10, 20, 50, 100]"
          @current-change="handlePageChange"
          @size-change="handleSizeChange"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { deleteContract, getContractList, getContractPdfBlob, regenerateContractPdf } from '../api/contract'
import { MoreFilled } from '@element-plus/icons-vue'

const route = useRoute()

const loading = ref(false)
const contracts = ref([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(20)
const searchKeyword = ref('')
const taskIdFilter = ref(undefined)

const syncFiltersFromRoute = () => {
  const keyword = String(route.query.keyword || '').trim()
  if (keyword) searchKeyword.value = keyword

  const rawTaskId = route.query.taskId
  const parsedTaskId = rawTaskId != null ? Number(rawTaskId) : undefined
  taskIdFilter.value = Number.isFinite(parsedTaskId) ? parsedTaskId : undefined
}

const fetchContracts = async () => {
  loading.value = true
  try {
    const params = {
      skip: (currentPage.value - 1) * pageSize.value,
      limit: pageSize.value,
      keyword: searchKeyword.value.trim(),
      task_id: taskIdFilter.value
    }
    const res = await getContractList(params)
    contracts.value = res.data.items || []
    total.value = res.data.total || 0
  } catch (error) {
    console.error(error)
    ElMessage.error(error.response?.data?.detail || '获取合同列表失败')
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  syncFiltersFromRoute()
  fetchContracts()
})

watch(
  () => route.query,
  () => {
    syncFiltersFromRoute()
    currentPage.value = 1
    fetchContracts()
  }
)

const formatAmount = (amount) => {
  const num = Number(amount || 0)
  return `¥ ${num.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

const normalizeStatus = (status) => String(status || '').trim().toLowerCase()
const isGeneratedStatus = (status) => {
  const s = normalizeStatus(status)
  return s.includes('generated') || s.includes('完成') || s.includes('已生成')
}
const isGeneratingStatus = (status) => {
  const s = normalizeStatus(status)
  return s.includes('generating') || s.includes('生成中')
}
const isFailedStatus = (status) => {
  const s = normalizeStatus(status)
  return s.includes('failed') || s.includes('失败')
}
const isWaitingSupplierStatus = (status) => {
  const s = normalizeStatus(status)
  return s.includes('待供应商') || s === 'pending' || s.includes('待')
}

const canPreviewOrDownload = (row) => isGeneratedStatus(row?.status)
const canRegenerate = (row) => isFailedStatus(row?.status) || isGeneratedStatus(row?.status)

const getStatusType = (status) => {
  if (!status) return 'info'
  if (isFailedStatus(status)) return 'danger'
  if (isGeneratingStatus(status)) return 'warning'
  if (isWaitingSupplierStatus(status)) return 'warning'
  if (isGeneratedStatus(status)) return 'success'
  return 'info'
}

const openBlobInNewTab = (blob) => {
  const url = URL.createObjectURL(blob)
  const tab = window.open(url, '_blank')
  if (!tab) {
    ElMessage.warning('浏览器阻止了新窗口，请允许弹窗后重试')
  }
  setTimeout(() => URL.revokeObjectURL(url), 30000)
}

const handlePreview = async (row) => {
  if (!canPreviewOrDownload(row)) {
    if (isGeneratingStatus(row?.status)) {
      ElMessage.warning('合同正在生成中，请稍后刷新再试')
      return
    }
    if (isFailedStatus(row?.status)) {
      ElMessage.error('合同生成失败，请让供应商重新提交合同信息后再试')
      return
    }
    if (isWaitingSupplierStatus(row?.status)) {
      ElMessage.warning('供应商尚未提交合同信息，暂无法预览/下载')
      return
    }
    ElMessage.warning('合同文件尚未生成，暂无法预览/下载')
    return
  }
  try {
    const res = await getContractPdfBlob(row.id)
    openBlobInNewTab(res.data)
  } catch (error) {
    console.error(error)
    const detail = error.response?.data?.detail
    if (error.response?.status === 404) {
      ElMessage.warning(detail || '合同文件尚未生成或已丢失，请稍后刷新重试')
      fetchContracts()
      return
    }
    ElMessage.error(detail || '预览失败')
  }
}

const handleDownload = async (row) => {
  if (!canPreviewOrDownload(row)) {
    if (isGeneratingStatus(row?.status)) {
      ElMessage.warning('合同正在生成中，请稍后刷新再试')
      return
    }
    if (isFailedStatus(row?.status)) {
      ElMessage.error('合同生成失败，请让供应商重新提交合同信息后再试')
      return
    }
    if (isWaitingSupplierStatus(row?.status)) {
      ElMessage.warning('供应商尚未提交合同信息，暂无法预览/下载')
      return
    }
    ElMessage.warning('合同文件尚未生成，暂无法预览/下载')
    return
  }
  try {
    const res = await getContractPdfBlob(row.id)
    const blob = res.data
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `${row.contract_no || 'contract'}.pdf`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)
  } catch (error) {
    console.error(error)
    const detail = error.response?.data?.detail
    if (error.response?.status === 404) {
      ElMessage.warning(detail || '合同文件尚未生成或已丢失，请稍后刷新重试')
      fetchContracts()
      return
    }
    ElMessage.error(detail || '下载失败')
  }
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm(
      `确认删除合同 ${row.contract_no || ''} 的记录吗？该操作不可恢复。`,
      '删除确认',
      {
        confirmButtonText: '确认删除',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    await deleteContract(row.id)
    ElMessage.success('删除成功')
    fetchContracts()
  } catch (error) {
    if (error === 'cancel') return
    console.error(error)
    ElMessage.error(error.response?.data?.detail || '删除失败')
  }
}

const handleRegenerate = async (row) => {
  try {
    if (isGeneratedStatus(row?.status)) {
      await ElMessageBox.confirm(
        `确认重新生成合同 ${row.contract_no || ''} 吗？将覆盖原PDF文件。`,
        '重新生成确认',
        {
          confirmButtonText: '确认',
          cancelButtonText: '取消',
          type: 'warning'
        }
      )
    }
    await regenerateContractPdf(row.id)
    ElMessage.success('已提交重新生成，请稍后刷新查看状态')
    fetchContracts()
  } catch (error) {
    console.error(error)
    ElMessage.error(error.response?.data?.detail || '重新生成失败')
  }
}

const handleActionCommand = (row, command) => {
  if (command === 'delete') {
    handleDelete(row)
    return
  }
  if (command === 'regenerate') {
    handleRegenerate(row)
  }
}

const handleSearch = () => {
  currentPage.value = 1
  fetchContracts()
}

const handlePageChange = (page) => {
  currentPage.value = page
  fetchContracts()
}

const handleSizeChange = (size) => {
  pageSize.value = size
  currentPage.value = 1
  fetchContracts()
}
</script>

<style scoped>
.page-container {
  padding: 20px;
}

.content-card {
  background: #fff;
  padding: 20px;
  border-radius: 8px;
}

.toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}

:deep(.el-table__header-wrapper th .cell) {
  display: flex;
  align-items: center;
  justify-content: center;
  text-align: center;
  width: 100%;
  padding-left: 0;
  padding-right: 0;
}

.action-cell {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  flex-wrap: nowrap;
  white-space: nowrap;
}

.more-btn {
  padding: 0;
}

.template-fallback-text {
  color: #909399;
}

.pagination-wrap {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}
</style>
