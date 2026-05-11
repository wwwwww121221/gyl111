<template>
  <div class="page-container">
    <el-tabs v-model="activeTaskType" @tab-change="handleTaskTypeChange" class="task-type-tabs">
      <el-tab-pane label="自动询价任务" name="auto"></el-tab-pane>
      <el-tab-pane label="手动询价任务" name="manual"></el-tab-pane>
    </el-tabs>

    <div class="content-card" style="height: calc(100% - 50px);">
      <div class="toolbar">
        <div class="toolbar-left">
          <el-input
            v-model="searchQuery"
            placeholder="搜索任务标题..."
            :prefix-icon="Search"
            clearable
            style="width: 250px;"
          />
        </div>
        <div class="toolbar-right">
          <el-button type="primary" @click="fetchTasks" :icon="Refresh" circle />
        </div>
      </div>

      <div class="table-container">
        <el-table 
          v-loading="loadingTasks" 
          :data="filteredTaskList" 
          border 
          stripe 
          highlight-current-row
          style="width: 100%"
          height="100%"
        >
          <el-table-column type="index" label="序号" width="80" align="center" />
          <el-table-column prop="title" label="任务标题" />
          <el-table-column prop="buyer_name" label="负责采购员" width="120" align="center" v-if="userRole === 'admin'" />
          <el-table-column prop="deadline" label="截止时间" width="190" align="center">
            <template #default="scope">
              <div>{{ formatDateTime(scope.row.deadline) }}</div>
              <el-tag v-if="hasTaskExpired(scope.row)" type="danger" size="small" effect="plain">已逾期</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="status" label="状态" width="120">
            <template #default="scope">
              <el-tag :type="getTaskStatusType(scope.row.status)">{{ getTaskStatusLabel(scope.row.status) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="created_at" label="创建时间" width="180">
            <template #default="scope">
              {{ formatDateTime(scope.row.created_at) }}
            </template>
          </el-table-column>
          <el-table-column label="操作" width="320" align="center">
            <template #default="scope">
              <template v-if="scope.row.type === 'manual'">
                <el-button size="small" type="warning" plain @click="openEditQuotesDialog(scope.row)">
                  修改报价
                </el-button>
                <el-button size="small" type="primary" @click="goToCompare(scope.row)">
                  智能比价
                </el-button>
                <el-button 
                  v-if="scope.row.status !== 'closed'" 
                  size="small" 
                  type="success" 
                  plain
                  @click="handleFinishManualTask(scope.row)"
                >
                  结束流程
                </el-button>
              </template>
              <template v-else>
                <el-button size="small" type="primary" @click="viewTaskDetails(scope.row)">
                  详情 / 管理
                </el-button>
                <el-button
                  v-if="scope.row.status === 'awaiting_award'"
                  size="small"
                  type="warning"
                  @click="goToCompare(scope.row)"
                >
                  智能比价 / 定标
                </el-button>
              </template>

              <el-button 
                v-if="scope.row.status === 'closed'" 
                size="small" 
                type="danger" 
                plain
                @click="handleDeleteTask(scope.row)"
              >
                删除
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </div>

    <!-- Dialog: Task Details -->
    <el-dialog v-model="detailsVisible" title="询价任务详情" width="85%" top="5vh" class="custom-dialog">
      <div v-if="currentTaskDetails" v-loading="loadingDetails" class="task-details-container">
        
        <!-- Header Info Card -->
        <el-card shadow="never" class="info-card">
          <template #header>
            <div class="card-header">
              <div class="header-title">
                <span class="task-title">{{ currentTaskDetails.title }}</span>
                <el-tag :type="getTaskStatusType(currentTaskDetails.status)" effect="dark" size="default" style="margin-left: 15px;">
                  {{ getTaskStatusLabel(currentTaskDetails.status) }}
                </el-tag>
                <el-tag v-if="hasTaskExpired(currentTaskDetails)" type="danger" effect="plain" size="default" style="margin-left: 8px;">
                  已逾期
                </el-tag>
              </div>
              <div class="header-actions">
                <el-button
                  v-if="currentTaskDetails.status === 'awaiting_award'"
                  type="warning"
                  @click="goToCompare(currentTaskDetails)"
                >
                  前往智能比价 / 定标
                </el-button>
                <el-button v-if="currentTaskDetails.status === 'active'" type="danger" plain @click="handleCloseTask()">
                  终止任务 (流标)
                </el-button>
              </div>
            </div>
          </template>
          <el-descriptions :column="4" border size="small">
            <el-descriptions-item label="期望单价(¥)">
              <span style="color: #f56c6c; font-weight: bold; font-size: 16px;">详见下方明细</span>
            </el-descriptions-item>
            <el-descriptions-item label="最大自动谈判轮次">
              <el-tag type="info" size="small">{{ currentTaskDetails.strategy_config?.max_rounds }} 轮</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="AI 期望降价幅度">
              <el-tag type="warning" size="small">{{ (currentTaskDetails.strategy_config?.bargain_ratio * 100).toFixed(0) }}%</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="截止时间">
              {{ formatDateTime(currentTaskDetails.deadline) }}
            </el-descriptions-item>
            <el-descriptions-item label="剩余时间" :span="3">
              <span :class="['countdown-text', { 'countdown-urgent': isDetailDeadlineUrgent }]">
                {{ detailCountdownText }}
              </span>
            </el-descriptions-item>
          </el-descriptions>
        </el-card>

        <el-alert
          v-if="isAwaitingAwardTask"
          title="自动谈判已提前结束：当前任务进入“待份额分配”状态，请前往智能比价页面完成拆单定标。"
          type="warning"
          :closable="false"
          show-icon
          class="awaiting-award-alert"
        />

        <!-- Main Content Tabs -->
        <el-tabs v-model="detailsActiveTab" class="details-tabs" type="border-card">
          
          <!-- Tab 1: Suppliers -->
          <el-tab-pane name="suppliers">
            <template #label>
              <span class="tab-label-with-status">
                <span>供应商与报价动态</span>
                <el-tag
                  v-if="isAwaitingAwardTask"
                  size="small"
                  type="warning"
                  effect="plain"
                >
                  待份额分配
                </el-tag>
              </span>
            </template>
            <div class="tab-toolbar">
              <el-form :inline="true" :model="supplierForm" class="supplier-form" size="default">
                <el-form-item label="新增供应商">
                  <el-input v-model="supplierForm.name" placeholder="输入供应商名称" style="width: 200px;" />
                </el-form-item>
                <el-form-item>
                  <el-button type="primary" @click="handleAddSupplier" :loading="addingSupplier" :disabled="currentTaskDetails.status !== 'active'">
                    添加供应商
                  </el-button>
                </el-form-item>
              </el-form>
            </div>

            <el-table :data="currentTaskDetails.links" border stripe style="width: 100%">
              <el-table-column type="expand">
                <template #default="props">
                  <div class="expand-content">
                    <h4 class="expand-title"><el-icon style="vertical-align: middle; margin-right: 5px;"><DocumentCopy /></el-icon>历史报价记录</h4>
                    <el-timeline style="padding-top: 10px;">
                      <el-timeline-item
                        v-for="(quotes, round) in props.row.quotes"
                        :key="round"
                        :timestamp="`第 ${round} 轮报价`"
                        placement="top"
                        type="primary"
                      >
                        <el-card shadow="hover" body-style="padding: 10px;">
                          <el-table :data="quotes" :row-class-name="getQuoteRowClassName" border size="small">
                            <el-table-column prop="item_id" label="明细项ID" width="100" align="center" />
                            <el-table-column prop="qty" label="可供数量" width="100" align="center" />
                            <el-table-column prop="delivery_date" label="承诺交期" width="120" align="center">
                              <template #default="scope">
                                {{ formatDate(scope.row.delivery_date) }}
                              </template>
                            </el-table-column>
                            <el-table-column label="单价(¥)" width="150" align="right">
                              <template #default="scope">
                                <span style="color: #f56c6c; font-weight: bold;">{{ Number(scope.row.price).toFixed(2) }}</span>
                                <el-tooltip
                                  v-if="scope.row.is_anomaly"
                                  :content="scope.row.anomaly_reason"
                                  placement="top"
                                  effect="light"
                                >
                                  <el-icon color="#e6a23c" style="margin-left: 5px; cursor: pointer; vertical-align: middle;">
                                    <Warning />
                                  </el-icon>
                                </el-tooltip>
                              </template>
                            </el-table-column>
                            <el-table-column prop="remark" label="备注说明" />
                          </el-table>
                        </el-card>
                      </el-timeline-item>
                    </el-timeline>
                    <el-empty v-if="!props.row.quotes || Object.keys(props.row.quotes).length === 0" description="暂无报价记录" :image-size="60"></el-empty>
                  </div>
                </template>
              </el-table-column>

              <el-table-column prop="supplier_name" label="供应商名称" min-width="150" />
              <el-table-column prop="status" label="当前状态" width="120" align="center">
                <template #default="scope">
                  <el-tag :type="getLinkStatusType(scope.row.status)" effect="light">{{ getLinkStatusText(scope.row.status) }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="current_round" label="当前轮次" width="100" align="center" />
              <el-table-column label="本轮总价(¥)" width="120" align="right">
                <template #default="scope">
                  <span v-if="scope.row.total_price > 0" style="font-weight: bold;">{{ Number(scope.row.total_price).toFixed(2) }}</span>
                  <span v-else>-</span>
                </template>
              </el-table-column>
              <el-table-column label="平均交期(天)" width="110" align="center">
                <template #default="scope">
                  <span v-if="scope.row.avg_delivery_days > 0">{{ Number(scope.row.avg_delivery_days).toFixed(1) }}</span>
                  <span v-else>-</span>
                </template>
              </el-table-column>
              <el-table-column label="综合评分" width="120" align="center">
                <template #default="scope">
                  <span v-if="scope.row.total_score > 0" style="color: #409EFF; font-weight: bold; font-size: 15px;">
                    {{ Number(scope.row.total_score).toFixed(2) }}
                  </span>
                  <span v-else>-</span>
                </template>
              </el-table-column>
              <el-table-column label="当前排名" width="90" align="center">
                <template #default="scope">
                  <el-tag v-if="scope.row.score_rank" :type="scope.row.score_rank === 1 ? 'danger' : 'info'" effect="dark">
                    第 {{ scope.row.score_rank }} 名
                  </el-tag>
                  <span v-else>-</span>
                </template>
              </el-table-column>

              <el-table-column label="操作" width="260" align="center" fixed="right">
                <template #default="scope">
                  <el-button 
                    v-if="currentTaskDetails.status === 'active' && scope.row.status !== 'deal' && scope.row.status !== 'reject'" 
                    size="small" 
                    type="success" 
                    plain
                    @click="handleCloseTask(scope.row.link_id)">
                    选定成交
                  </el-button>
                  <span v-else-if="scope.row.status === 'deal'" style="color: #67c23a; font-weight: bold;">已成交</span>
                  <span v-else-if="scope.row.status === 'reject'" style="color: #909399;">已淘汰</span>
                  <span v-else>-</span>
                  <el-button
                    v-if="currentTaskDetails.status === 'active' && scope.row.status === 'negotiation'"
                    size="small"
                    type="warning"
                    plain
                    @click="openManualInterventionDialog(scope.row, 'continue')"
                  >
                    人工通过
                  </el-button>
                  <el-button
                    v-if="currentTaskDetails.status === 'active' && scope.row.status === 'negotiation'"
                    size="small"
                    type="danger"
                    plain
                    @click="openManualInterventionDialog(scope.row, 'reject')"
                  >
                    人工淘汰
                  </el-button>
                </template>
              </el-table-column>
            </el-table>
          </el-tab-pane>

          <!-- Tab 2: Items -->
          <el-tab-pane label="询价明细 (Items)" name="items">
            <el-table :data="currentTaskDetails.items" border stripe size="small">
              <el-table-column prop="id" label="明细项ID" width="100" align="center" />
              <el-table-column prop="material_code" label="物料编码" width="150" />
              <el-table-column prop="material_name" label="物料名称" min-width="200" />
              <el-table-column prop="qty" label="需求数量" width="120" align="right" />
              <el-table-column prop="target_price" label="设定期望单价(¥)" width="150" align="right">
                <template #default="scope">
                  <span v-if="scope.row.target_price" style="color: #f56c6c; font-weight: bold;">{{ Number(scope.row.target_price).toFixed(2) }}</span>
                  <span v-else style="color: #909399;">不设限</span>
                </template>
              </el-table-column>
              <el-table-column prop="delivery_date" label="需求日期" width="150" align="center">
                <template #default="scope">{{ formatDate(scope.row.delivery_date) }}</template>
              </el-table-column>
            </el-table>
          </el-tab-pane>

        </el-tabs>
      </div>
    </el-dialog>

    <el-dialog
      v-model="manualInterventionDialogVisible"
      :title="manualInterventionMode === 'continue' ? '人工通过谈判' : '人工淘汰供应商'"
      width="520px"
    >
      <el-form :model="manualInterventionForm" label-width="92px">
        <el-form-item label="处理说明">
          <el-input
            v-model="manualInterventionForm.message"
            type="textarea"
            :rows="4"
            :placeholder="manualInterventionMode === 'continue' ? '请输入给供应商的人工复核反馈' : '请输入淘汰原因（将同步给供应商）'"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="manualInterventionDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="manualInterventionSubmitting" @click="submitManualIntervention">
          确认提交
        </el-button>
      </template>
    </el-dialog>
    <el-dialog
      v-model="editQuotesDialogVisible"
      title="修改手工报价"
      width="70%"
      top="5vh"
    >
      <div v-loading="editQuotesLoading" style="min-height: 200px;">
        <div v-for="(item, idx) in editQuotesData" :key="idx" style="margin-bottom: 20px;">
          <h4 style="margin: 0 0 10px 0; color: #303133;">物料: {{ item.material_name }} ({{ item.material_code }}) - 数量: {{ item.qty }}</h4>
          <el-table :data="[item]" border size="small">
            <el-table-column
              v-for="link in item.links"
              :key="link.supplier_code"
              :label="link.supplier_name + ' (含税单价)'"
              min-width="150"
              align="center"
            >
              <template #default="scope">
                <el-input-number
                  v-model="scope.row.quotes[link.supplier_code]"
                  :precision="2"
                  :step="1"
                  :min="0"
                  :controls="false"
                  size="small"
                  style="width: 100%; text-align: center;"
                  placeholder="请输入含税单价"
                ></el-input-number>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </div>
      <template #footer>
        <el-button @click="editQuotesDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingQuotes" @click="saveEditedQuotes">保存修改</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { getInquiryTasks, addSupplierToTask, getTaskDetails, closeInquiryTask, updateTaskStatus } from '../../api/inquiry'
import api from '../../api/index'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh, DocumentCopy, Search, Warning } from '@element-plus/icons-vue'

const router = useRouter()
const userRole = computed(() => localStorage.getItem('role') || '')

const activeTaskType = ref('auto')
const loadingTasks = ref(false)
const taskList = ref([])
const searchQuery = ref('')

const handleTaskTypeChange = () => {
  fetchTasks()
}

const goToCompare = (task) => {
  if (task.status === 'pending_fill') {
    updateTaskStatus(task.id, 'analyzing').then(() => {
      fetchTasks()
    }).catch(err => console.error(err))
  }
  router.push({
    name: 'IntelligentCompare',
    query: { taskId: task.id }
  })
}

const handleFinishManualTask = async (task) => {
  try {
    await ElMessageBox.confirm(`确定要结束任务 "${task.title}" 吗？`, '结束任务', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    await updateTaskStatus(task.id, 'closed')
    ElMessage.success('任务已结束')
    fetchTasks()
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('操作失败: ' + (e.response?.data?.detail || e.message))
    }
  }
}

const filteredTaskList = computed(() => {
  if (!searchQuery.value) return taskList.value
  return taskList.value.filter(task => 
    task.title.toLowerCase().includes(searchQuery.value.toLowerCase())
  )
})

const detailsVisible = ref(false)
const detailsActiveTab = ref('suppliers')
const currentTask = ref(null)
const currentTaskDetails = ref(null)
const loadingDetails = ref(false)
const addingSupplier = ref(false)
const supplierForm = reactive({
  name: '',
  contact: '',
  phone: ''
})
const manualInterventionDialogVisible = ref(false)
const manualInterventionSubmitting = ref(false)
const manualInterventionMode = ref('continue')
const manualInterventionLinkId = ref(null)
const manualInterventionForm = reactive({
  message: ''
})
const nowTs = ref(Date.now())
let timerId = null

const editQuotesDialogVisible = ref(false)
const editingTask = ref(null)
const editQuotesData = ref([])
const editQuotesLoading = ref(false)
const savingQuotes = ref(false)

const openEditQuotesDialog = async (task) => {
  editingTask.value = task
  editQuotesDialogVisible.value = true
  editQuotesLoading.value = true
  try {
    const res = await getTaskDetails(task.id)
    const details = res.data
    const items = details.items || []
    const links = details.links || []
    
    editQuotesData.value = items.map(item => {
      const quotesObj = {}
      links.forEach(link => {
        const round = link.current_round || 1
        const quotesRound = link.quotes ? (link.quotes[round] || link.quotes['1'] || []) : []
        const quote = quotesRound.find(q => q.item_id === item.id)
        if (quote && quote.price) {
          quotesObj[link.supplier_code] = Number((quote.price * 1.13).toFixed(2))
        } else {
          quotesObj[link.supplier_code] = undefined
        }
      })
      return {
        ...item,
        quotes: quotesObj,
        links: links
      }
    })
  } catch (error) {
    console.error(error)
    ElMessage.error('获取任务详情失败')
  } finally {
    editQuotesLoading.value = false
  }
}

const saveEditedQuotes = async () => {
  if (!editingTask.value) return
  savingQuotes.value = true
  try {
    for (const item of editQuotesData.value) {
      const suppliersQuotes = []
      for (const link of item.links) {
        const taxNetPrice = item.quotes[link.supplier_code]
        if (taxNetPrice > 0) {
          suppliersQuotes.push({
            supplier_code: link.supplier_code,
            supplier_name: link.supplier_name,
            tax_net_price: Number(taxNetPrice),
            price: Number((taxNetPrice / 1.13).toFixed(2)),
            qty: Number(item.qty) || 1
          })
        }
      }
      if (suppliersQuotes.length > 0) {
        await api.post(`/inquiry/tasks/${editingTask.value.id}/save-manual-quotes`, {
          material_code: item.material_code,
          suppliers: suppliersQuotes
        })
      }
    }
    ElMessage.success('报价修改成功')
    editQuotesDialogVisible.value = false
  } catch (error) {
    console.error(error)
    ElMessage.error('修改报价失败')
  } finally {
    savingQuotes.value = false
  }
}

const fetchTasks = async () => {
  loadingTasks.value = true
  try {
    const res = await getInquiryTasks({ type: activeTaskType.value === 'auto' ? 'auto' : 'manual' })
    taskList.value = res.data || []
  } catch (error) {
    console.error(error)
    ElMessage.error('获取任务列表失败')
  } finally {
    loadingTasks.value = false
  }
}

const viewTaskDetails = async (task) => {
  currentTask.value = task
  detailsActiveTab.value = 'suppliers'
  detailsVisible.value = true
  loadingDetails.value = true
  try {
    const res = await getTaskDetails(task.id)
    currentTaskDetails.value = res.data
  } catch (error) {
    console.error(error)
    ElMessage.error('获取任务详情失败')
  } finally {
    loadingDetails.value = false
  }
}

const handleCloseTask = async (linkId = null) => {
  try {
    await closeInquiryTask(currentTaskDetails.value.id, linkId)
    ElMessage.success(linkId ? '已选定该供应商并自动关闭任务' : '任务已手动结束 (流标)')
    viewTaskDetails(currentTask.value)
    fetchTasks()
  } catch (error) {
    console.error(error)
    ElMessage.error('操作失败')
  }
}

const handleDeleteTask = async (task) => {
  try {
    await ElMessageBox.confirm('确认删除该询价单吗？相关的报价记录将一并删除，且操作不可恢复。', '警告', {
      confirmButtonText: '确认删除',
      cancelButtonText: '取消',
      type: 'warning'
    })
    
    await api.delete(`/inquiry/tasks/${task.id}`)
    ElMessage.success('删除成功')
    fetchTasks()
  } catch (e) {
    if (e !== 'cancel') {
      console.error(e)
      ElMessage.error('删除失败')
    }
  }
}

const openManualInterventionDialog = (row, mode) => {
  manualInterventionMode.value = mode
  manualInterventionLinkId.value = row.link_id
  manualInterventionForm.message = ''
  manualInterventionDialogVisible.value = true
}

const submitManualIntervention = async () => {
  if (!currentTaskDetails.value || !manualInterventionLinkId.value) return
  manualInterventionSubmitting.value = true
  try {
    const endpoint = manualInterventionMode.value === 'continue' ? 'manual-continue' : 'manual-reject'
    await api.post(`/inquiry/tasks/${currentTaskDetails.value.id}/links/${manualInterventionLinkId.value}/${endpoint}`, {
      message: manualInterventionForm.message || null
    })
    ElMessage.success(manualInterventionMode.value === 'continue' ? '已人工通过，供应商可继续谈判' : '已人工淘汰该供应商')
    manualInterventionDialogVisible.value = false
    await viewTaskDetails(currentTask.value)
    await fetchTasks()
  } catch (error) {
    console.error(error)
    ElMessage.error('人工干预失败')
  } finally {
    manualInterventionSubmitting.value = false
  }
}

const handleAddSupplier = async () => {
  if (!supplierForm.name) {
    ElMessage.warning('请输入供应商名称')
    return
  }
  addingSupplier.value = true
  try {
    await addSupplierToTask(currentTask.value.id, {
      supplier_name: supplierForm.name,
      contact_person: supplierForm.contact,
      phone: supplierForm.phone
    })
    ElMessage.success(`供应商添加成功`)
    supplierForm.name = ''
    viewTaskDetails(currentTask.value)
  } catch (error) {
    console.error(error)
    ElMessage.error('添加供应商失败')
  } finally {
    addingSupplier.value = false
  }
}

const getLinkStatusType = (status) => {
  const map = {
    'sent': 'info',
    'quoted': 'primary',
    'negotiation': 'warning',
    'deal': 'success',
    'reject': 'danger'
  }
  return map[status] || ''
}

const getLinkStatusText = (status) => {
  const map = {
    'sent': '已发送(未报)',
    'quoted': '已报价',
    'negotiation': '谈判中',
    'deal': '已成交',
    'reject': '已淘汰'
  }
  return map[status] || status
}

const formatDateTime = (dateStr) => {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString()
}

const formatDate = (dateStr) => {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleDateString()
}

const getCountdownMeta = (deadline) => {
  if (!deadline) return { text: '未设置截止时间', urgent: false }
  const deadlineMs = new Date(deadline).getTime()
  if (Number.isNaN(deadlineMs)) return { text: '截止时间无效', urgent: false }
  const diffMs = deadlineMs - nowTs.value
  if (diffMs <= 0) return { text: '已逾期', urgent: true }
  const totalSeconds = Math.floor(diffMs / 1000)
  const days = Math.floor(totalSeconds / 86400)
  const hours = Math.floor((totalSeconds % 86400) / 3600)
  const minutes = Math.floor((totalSeconds % 3600) / 60)
  const seconds = totalSeconds % 60
  const text = days > 0
    ? `${days}天 ${hours}时 ${minutes}分 ${seconds}秒`
    : `${hours}时 ${minutes}分 ${seconds}秒`
  return { text, urgent: diffMs < 2 * 3600 * 1000 }
}

const hasTaskExpired = (task) => {
  if (!task || task.status !== 'active' || !task.deadline) return false
  const deadlineMs = new Date(task.deadline).getTime()
  if (Number.isNaN(deadlineMs)) return false
  return nowTs.value > deadlineMs
}

const detailCountdownMeta = computed(() => getCountdownMeta(currentTaskDetails.value?.deadline))
const isAwaitingAwardTask = computed(() => currentTaskDetails.value?.status === 'awaiting_award')
const detailCountdownText = computed(() =>
  isAwaitingAwardTask.value ? '自动谈判已结束，等待采购员完成份额定标' : detailCountdownMeta.value.text
)
const isDetailDeadlineUrgent = computed(() => !isAwaitingAwardTask.value && detailCountdownMeta.value.urgent)

const getTaskStatusType = (status) => {
  const map = {
    'draft': 'info',
    'active': 'success',
    'closed': 'info',
    'awaiting_award': 'warning',
    'cancelled': 'danger',
    'pending_fill': 'warning',
    'analyzing': 'primary'
  }
  return map[status] || ''
}

const getTaskStatusLabel = (status) => {
  const map = {
    'draft': '草稿',
    'active': '进行中',
    'closed': '已结束',
    'awaiting_award': '待份额分配',
    'cancelled': '已取消',
    'pending_fill': '待填写',
    'analyzing': '分析中'
  }
  return map[status] || status
}

const getQuoteRowClassName = ({ row }) => {
  return row?.is_anomaly ? 'anomaly-row' : ''
}

onMounted(() => {
  fetchTasks()
  timerId = window.setInterval(() => {
    nowTs.value = Date.now()
  }, 1000)
})

onUnmounted(() => {
  if (timerId) {
    window.clearInterval(timerId)
  }
})
</script>

<style scoped>
.page-container {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  background: white;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.page-title {
  margin: 0;
  font-size: 24px;
  color: #303133;
}

.content-card {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  padding: 15px;
}

.table-container {
  flex: 1;
  min-height: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

:deep(.el-table) {
  flex: 1;
  height: 100%;
}

.toolbar {
  margin-bottom: 15px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-shrink: 0;
}

.toolbar-left, .toolbar-right {
  display: flex;
  align-items: center;
  gap: 10px;
}

/* 任务详情弹窗美化 */
.task-details-container {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.awaiting-award-alert {
  margin-top: -8px;
}

.tab-label-with-status {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.info-card {
  border-radius: 8px;
  background-color: #fcfcfc;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-title {
  display: flex;
  align-items: center;
}

.task-title {
  font-size: 18px;
  font-weight: bold;
  color: #303133;
}

.details-tabs {
  box-shadow: 0 2px 12px 0 rgba(0,0,0,0.05);
  border-radius: 8px;
  overflow: hidden;
}

.tab-toolbar {
  margin-bottom: 15px;
  display: flex;
  justify-content: flex-start;
  align-items: center;
  background-color: #f5f7fa;
  padding: 10px 15px;
  border-radius: 4px;
}

.supplier-form {
  margin-bottom: 0;
}

.supplier-form .el-form-item {
  margin-bottom: 0;
  margin-right: 15px;
}

.expand-content {
  padding: 20px 40px;
  background-color: #fafafa;
  border-top: 1px solid #ebeef5;
  border-bottom: 1px solid #ebeef5;
}

.expand-title {
  margin-top: 0;
  margin-bottom: 15px;
  color: #606266;
  font-size: 15px;
}

.countdown-text {
  font-weight: 500;
  color: #606266;
}

.countdown-urgent {
  color: #f56c6c;
  font-weight: 700;
}

:deep(.anomaly-row) {
  background-color: #fff8e1;
}
</style>
