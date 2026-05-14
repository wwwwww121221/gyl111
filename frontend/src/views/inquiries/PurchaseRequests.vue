<template>
  <div class="page-container">
    <div class="content-card">
      <div class="toolbar">
        <div class="toolbar-top">
          <!-- 高级筛选表单 -->
          <el-form :inline="true" :model="searchForm" class="advanced-search-form">
            <el-form-item>
              <el-input
                v-model="searchForm.keyword"
                placeholder="单号 / 项目号 / 物料名"
                :prefix-icon="Search"
                clearable
                style="width: 220px;"
                @keyup.enter="handleSyncErp"
              />
            </el-form-item>
            
            <el-form-item>
              <el-select v-model="searchForm.bill_type_id" placeholder="单据类型" clearable style="width: 140px;">
                <el-option label="标准采购" value="93591469feb54ca2b08eb635f8b79de3" />
                <el-option label="零星采购" value="66387c8fd05437" />
                <el-option label="委外采购" value="66d0038d59a406" />
                <el-option label="资产采购" value="60d2460b0e5742d58432f70a06f193b6" />
                <el-option label="费用采购" value="03c6c047c65c4a17a792f85dcf3cabec" />
              </el-select>
            </el-form-item>

            <el-form-item>
              <el-date-picker
                v-model="searchForm.dateRange"
                type="daterange"
                range-separator="至"
                start-placeholder="创建开始日期"
                end-placeholder="结束日期"
                value-format="YYYY/MM/DD HH:mm:ss"
                style="width: 260px;"
              />
            </el-form-item>

            <el-form-item>
              <el-button type="primary" :icon="Search" @click="handleSyncErp" :loading="syncingErp">
                查询
              </el-button>
            </el-form-item>
          </el-form>
        </div>
        
        <div class="toolbar-bottom">
          <div class="toolbar-actions">
            <el-badge :value="selectedRequests.length" :hidden="selectedRequests.length === 0" class="cart-badge">
              <el-button @click="cartVisible = true">
                查看已选清单
              </el-button>
            </el-badge>
            <el-button type="success" @click="handleIntelligentCompare" :disabled="selectedRequests.length === 0" style="margin-left: 15px;">
              发起智能比价
            </el-button>
            <el-button type="primary" @click="showCreateTaskDialog" :disabled="selectedRequests.length === 0" style="margin-left: 15px;">
              发起询价任务
            </el-button>
          </div>
        </div>
      </div>

      <div class="table-container">
        <el-table
          ref="tableRef"
          v-loading="syncingErp"
          :data="paginatedRequestList"
          @selection-change="handleSelectionChange"
          style="width: 100%"
          row-key="_uid"
          size="small"
          height="100%"
        >
          <el-table-column type="selection" width="45" :reserve-selection="true" />
          <el-table-column prop="bill_no" label="单据编号" width="130" show-overflow-tooltip />
          <el-table-column prop="bill_type" label="单据类型" width="90" />
          <el-table-column label="项目信息" min-width="160" show-overflow-tooltip>
            <template #default="scope">
              <div v-if="scope.row.project_info">
                <div style="font-weight: 500;">{{ scope.row.project_info.number }}</div>
                <small style="color: #909399">{{ scope.row.project_info.name }}</small>
              </div>
              <span v-else style="color: #ccc;">-</span>
            </template>
          </el-table-column>
          <el-table-column prop="material_name" label="物料名称" min-width="150" show-overflow-tooltip />
          <el-table-column prop="material_code" label="物料编码" width="120" show-overflow-tooltip />
          <el-table-column prop="qty" label="数量" width="80" align="right" />
          <el-table-column prop="delivery_date" label="需求日期" width="100" align="center">
            <template #default="scope">
              {{ formatDate(scope.row.delivery_date) }}
            </template>
          </el-table-column>
          <el-table-column prop="created_at" label="创建时间" width="150" align="center">
            <template #default="scope">
              {{ formatDateTime(scope.row.created_at) }}
            </template>
          </el-table-column>
        </el-table>
      </div>

      <div class="pagination-container">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :page-sizes="[50, 100, 200, 500]"
          background
          layout="total, sizes, prev, pager, next, jumper"
          :total="filteredRequestList.length"
          @size-change="handleSizeChange"
          @current-change="handleCurrentChange"
        />
      </div>
    </div>

    <!-- Dialog: Create Task -->
    <el-dialog v-model="dialogVisible" title="创建新询价任务" width="800px" @close="isJumpToCompare = false">
      <el-form ref="taskFormRef" :model="taskForm" :rules="taskFormRules" label-width="100px" size="default">
        <el-form-item label="任务类型" prop="type">
          <el-radio-group v-model="taskForm.type">
            <el-radio value="auto">自动询价 (系统自动多轮谈判)</el-radio>
            <el-radio value="manual">手动询价 (人工线下录入报价比价)</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="任务标题">
          <el-input v-model="taskForm.title" placeholder="例如：3月份电子元器件采购" />
        </el-form-item>
        <el-form-item v-if="taskForm.type === 'auto'" label="截止日期" prop="deadline">
          <div class="deadline-inputs">
            <el-date-picker
              v-model="taskForm.deadlineDate"
              type="date"
              placeholder="请选择日期"
              value-format="YYYY-MM-DD"
              :teleported="false"
              style="width: 100%"
            />
            <el-time-select
              v-model="taskForm.deadlineTime"
              placeholder="请选择时间"
              start="00:00"
              step="00:30"
              end="23:30"
              :teleported="false"
              style="width: 100%"
            />
          </div>
        </el-form-item>
        
        <el-row :gutter="20" v-if="taskForm.type === 'auto'">
          <el-col :span="12">
            <el-form-item label="最大轮次">
              <el-input-number v-model="taskForm.strategy_config.max_rounds" :min="1" :max="10" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="砍价比例">
              <el-input-number v-model="taskForm.strategy_config.bargain_ratio" :step="0.01" :min="0" :max="1" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="指定供应商">
          <el-select v-model="taskForm.supplier_ids" multiple filterable placeholder="请选择要派发的供应商（选填，不选则后续手动添加）" style="width: 100%">
            <el-option v-for="s in supplierList" :key="s.id" :label="s.name" :value="s.id">
              <span style="float: left">{{ s.name }}</span>
              <span style="float: right; color: var(--el-text-color-secondary); font-size: 13px">
                {{ getGradeLabel(s) }} | 历史交易: {{ s.transaction_count || 0 }} 次
              </span>
            </el-option>
          </el-select>
        </el-form-item>

        <!-- Quote Input Grid for Manual Tasks -->
        <div v-if="taskForm.type === 'manual' && taskForm.supplier_ids.length > 0 && selectedRequestsForTask.length > 0" style="margin-top: 20px;">
          <span style="font-size: 14px; color: #606266; font-weight: bold;">直接录入报价 (选填)</span>
          <el-divider style="margin: 8px 0;"></el-divider>
          <el-table :data="selectedRequestsForTask" border size="small" style="margin-bottom: 10px;">
            <el-table-column label="物料名称" min-width="150" prop="material_name" />
            <el-table-column v-for="supplierId in taskForm.supplier_ids" :key="supplierId" :label="getSupplierName(supplierId) + ' (含税单价)'" min-width="150" align="center">
              <template #default="scope">
                <el-input-number 
                  v-model="scope.row.quotes[supplierId]" 
                  :precision="2" :step="1" :min="0" :controls="false"
                  size="small" style="width: 100%; text-align: center;" 
                  placeholder="请输入单价"
                ></el-input-number>
              </template>
            </el-table-column>
          </el-table>
        </div>

        <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 20px;">
          <span style="font-size: 14px; color: #606266; font-weight: bold;">询价物料清单</span>
          <el-button type="primary" link @click="addCustomMaterial">+ 添加自定义物料</el-button>
        </div>
        <el-divider style="margin: 8px 0;"></el-divider>
        
        <el-table :data="selectedRequestsForTask" border size="small" style="margin-bottom: 10px;">
          <el-table-column label="物料编码" width="120">
            <template #default="scope">
              <el-input v-if="scope.row.is_custom" v-model="scope.row.material_code" size="small" placeholder="选填" />
              <span v-else>{{ scope.row.material_code }}</span>
            </template>
          </el-table-column>
          <el-table-column label="物料名称" min-width="150">
            <template #default="scope">
              <el-input v-if="scope.row.is_custom" v-model="scope.row.material_name" size="small" placeholder="必填" />
              <span v-else>{{ scope.row.material_name }}</span>
            </template>
          </el-table-column>
          <el-table-column label="需求数量" width="120">
            <template #default="scope">
              <el-input-number v-model="scope.row.qty" :min="1" size="small" style="width: 100%" controls-position="right" />
            </template>
          </el-table-column>
          <el-table-column label="期望交期" width="150">
            <template #default="scope">
              <el-date-picker v-model="scope.row.delivery_date" type="date" placeholder="选择交期" size="small" style="width: 100%" value-format="YYYY-MM-DD" />
            </template>
          </el-table-column>
          <el-table-column label="期望单价(¥)" width="130">
            <template #default="scope">
              <el-input-number v-model="scope.row.target_price" :min="0" :precision="2" :step="0.1" size="small" placeholder="不设限" style="width: 100%" controls-position="right" />
            </template>
          </el-table-column>
          <el-table-column label="操作" width="60" align="center">
            <template #default="scope">
              <el-button type="danger" link @click="removeMaterial(scope.$index)">移除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="dialogVisible = false">取消</el-button>
          <el-button type="primary" @click="confirmCreateTask" :loading="creatingTask">
            创建任务
          </el-button>
        </span>
      </template>
    </el-dialog>

    <!-- Drawer: Selected Requests Cart -->
    <el-drawer v-model="cartVisible" title="已选询价物料清单" size="40%">
      <div v-if="selectedRequests.length === 0" style="text-align: center; color: #909399; margin-top: 50px;">
        暂未选择任何物料
      </div>
      <el-table v-else :data="selectedRequests" style="width: 100%" size="small" border>
        <el-table-column prop="material_name" label="物料名称" min-width="120" show-overflow-tooltip />
        <el-table-column prop="qty" label="数量" width="80" align="right" />
        <el-table-column prop="delivery_date" label="需求日期" width="100">
          <template #default="scope">
            {{ formatDate(scope.row.delivery_date) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="80" align="center">
          <template #default="scope">
            <el-button type="danger" link @click="removeFromCart(scope.row)">移除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <template #footer>
        <div style="display: flex; justify-content: flex-end; gap: 10px;">
          <el-button @click="cartVisible = false">关闭</el-button>
          <el-button type="primary" @click="showCreateTaskDialog" :disabled="selectedRequests.length === 0">去发起询价</el-button>
        </div>
      </template>
    </el-drawer>

  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed, watch } from 'vue'
import { createInquiryTask, syncErpRequisitions } from '../../api/inquiry'
import api from '../../api/index'
import { ElMessage } from 'element-plus'
import { Download, Search } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const syncingErp = ref(false)
const requestList = ref([])
const selectedRequests = ref([])
const selectedRequestsForTask = ref([])
const cartVisible = ref(false)

const tableRef = ref(null)

const removeFromCart = (row) => {
  if (tableRef.value) {
    tableRef.value.toggleRowSelection(row, false)
  } else {
    selectedRequests.value = selectedRequests.value.filter(item => item._uid !== row._uid)
  }
}

// Search and Pagination
const searchQuery = ref('')

// 计算本月初和当前时间
const getStartOfMonth = () => {
  const now = new Date()
  const start = new Date(now.getFullYear(), now.getMonth(), 1)
  const pad = (n) => (n < 10 ? '0' + n : n)
  return `${start.getFullYear()}/${pad(start.getMonth() + 1)}/${pad(start.getDate())} 00:00:00`
}
const getCurrentTime = () => {
  const now = new Date()
  const pad = (n) => (n < 10 ? '0' + n : n)
  return `${now.getFullYear()}/${pad(now.getMonth() + 1)}/${pad(now.getDate())} ${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`
}

const searchForm = reactive({
  keyword: '',
  bill_type_id: '',
  dateRange: [getStartOfMonth(), getCurrentTime()]
})
const currentPage = ref(1)
const pageSize = ref(100)

// 搜索条件变化时重置页码
watch(searchQuery, () => {
  currentPage.value = 1
})

const filteredRequestList = computed(() => {
  let result = [...requestList.value]

  if (searchQuery.value) {
    const query = searchQuery.value.toLowerCase()
    result = result.filter(item => {
      const matName = item.material_name ? String(item.material_name).toLowerCase() : ''
      const billNo = item.bill_no ? String(item.bill_no).toLowerCase() : ''
      const projNum = (item.project_info && item.project_info.number) ? String(item.project_info.number).toLowerCase() : ''
      const projName = (item.project_info && item.project_info.name) ? String(item.project_info.name).toLowerCase() : ''
      
      return matName.includes(query) || 
             billNo.includes(query) || 
             projNum.includes(query) || 
             projName.includes(query)
    })
  }
  
  return result
})

const paginatedRequestList = computed(() => {
  const list = filteredRequestList.value
  const page = currentPage.value
  const size = pageSize.value
  
  const start = (page - 1) * size
  const end = start + size
  
  return list.slice(start, end)
})

const handleSizeChange = (val) => {
  pageSize.value = val
  currentPage.value = 1
}

const handleCurrentChange = (val) => {
  currentPage.value = val
}

// Create Task Dialog
const dialogVisible = ref(false)
const creatingTask = ref(false)
const supplierList = ref([])
const taskFormRef = ref(null)
const taskForm = reactive({
  title: '',
  type: 'auto',
  deadline: '',
  deadlineDate: '',
  deadlineTime: '',
  supplier_ids: [],
  strategy_config: {
    max_rounds: 3,
    bargain_ratio: 0.05,
    target_total_price: undefined
  }
})

const DEFAULT_DEADLINE_TIME = '00:00'

const syncDeadlineValue = () => {
  if (taskForm.type !== 'auto') {
    taskForm.deadline = ''
    return
  }
  if (!taskForm.deadlineDate || !taskForm.deadlineTime) {
    taskForm.deadline = ''
    return
  }
  taskForm.deadline = `${taskForm.deadlineDate}T${taskForm.deadlineTime}:00`
}

const validateDeadline = (_, value, callback) => {
  if (taskForm.type !== 'auto') {
    callback()
    return
  }
  if (!value) {
    callback(new Error('请选择截止日期'))
    return
  }
  const deadlineTime = new Date(value).getTime()
  if (Number.isNaN(deadlineTime)) {
    callback(new Error('截止日期格式无效'))
    return
  }
  if (deadlineTime <= Date.now()) {
    callback(new Error('截止日期必须晚于当前时间'))
    return
  }
  callback()
}

const taskFormRules = {
  deadline: [
    { validator: validateDeadline, trigger: 'change' }
  ]
}

watch(() => taskForm.type, (newType) => {
  if (newType === 'manual') {
    taskForm.deadline = ''
    taskForm.deadlineDate = ''
    taskForm.deadlineTime = ''
    return
  }
  if (!taskForm.deadlineTime) {
    taskForm.deadlineTime = DEFAULT_DEADLINE_TIME
  }
})

watch(
  () => [taskForm.deadlineDate, taskForm.deadlineTime, taskForm.type],
  () => {
    syncDeadlineValue()
  }
)

const fetchSuppliers = async () => {
  try {
    const res = await api.get('/supplier/list')
    const list = res.data || []
    // Sort suppliers by transaction_count in descending order
    list.sort((a, b) => (b.transaction_count || 0) - (a.transaction_count || 0))
    supplierList.value = list
  } catch (error) {
    console.error('Failed to fetch suppliers:', error)
  }
}

const getSupplierName = (supplierId) => {
  const s = supplierList.value.find(s => s.id === supplierId)
  return s ? s.name : '未知供应商'
}

const getGradeType = (grade, level) => {
  const actualGrade = grade || (level === 'core' ? 'A级' : '一般')
  if (actualGrade === 'A级') return 'success'
  if (actualGrade === 'B级') return 'warning'
  if (actualGrade === 'C级') return 'danger'
  return 'info'
}

const getGradeLabel = (row) => {
  return row.grade || (row.level === 'core' ? 'A级' : '一般');
}

const addCustomMaterial = () => {
  selectedRequestsForTask.value.push({
    is_custom: true,
    erp_request_id: `MANUAL-${Math.random().toString(36).substr(2, 9)}`,
    material_code: '',
    material_name: '',
    qty: 1,
    target_price: undefined,
    quotes: {}
  })
}

const removeMaterial = (index) => {
  selectedRequestsForTask.value.splice(index, 1)
}

const handleSyncErp = async () => {
  syncingErp.value = true
  try {
    // 组装查询参数
    const params = {
      keyword: searchForm.keyword || null,
      bill_type_id: searchForm.bill_type_id || null,
      start_date: searchForm.dateRange && searchForm.dateRange[0] ? searchForm.dateRange[0] : null,
      end_date: searchForm.dateRange && searchForm.dateRange[1] ? searchForm.dateRange[1] : null
    }

    const res = await syncErpRequisitions(params)
    if (res.data && res.data.length > 0) {
      requestList.value = res.data.map((item, index) => ({
        ...item,
        _uid: `sync_${index}_${Math.random().toString(36).substring(2, 9)}`
      }))
      currentPage.value = 1
      ElMessage.success(`精准同步成功，获取到 ${res.data.length} 条记录`)
    } else {
      requestList.value = []
      ElMessage.info('未获取到符合该高级条件的 ERP 数据')
    }
  } catch (error) {
    console.error('Sync ERP failed:', error)
    ElMessage.error('同步ERP数据失败: ' + (error.response?.data?.detail || error.message))
  } finally {
    syncingErp.value = false
  }
}

const handleSelectionChange = (val) => {
  selectedRequests.value = val
}

const isJumpToCompare = ref(false)

const handleIntelligentCompare = async () => {
  if (selectedRequests.value.length === 0) {
    ElMessage.warning('请先选择采购申请明细')
    return
  }
  showCreateTaskDialog(true)
}

const showCreateTaskDialog = (isJump = false) => {
  isJumpToCompare.value = isJump === true
  const aggregatedMap = new Map()
  
  if (selectedRequests.value && selectedRequests.value.length > 0) {
    selectedRequests.value.forEach(item => {
      const dateStr = item.delivery_date ? String(item.delivery_date).substring(0, 10) : 'none'
      const key = `${item.material_code}_${dateStr}`
      
      if (aggregatedMap.has(key)) {
        const existing = aggregatedMap.get(key)
        existing.qty += Number(item.qty) || 0
        
        if (item.erp_request_id && !existing.erp_request_id.includes(item.erp_request_id)) {
          existing.erp_request_id = `${existing.erp_request_id},${item.erp_request_id}`
        }
        if (item.bill_no && !existing.bill_no.includes(item.bill_no)) {
          existing.bill_no = `${existing.bill_no},${item.bill_no}`
        }
        if (item.project_info && existing.project_info) {
          if (item.project_info.number) {
            const extNum = existing.project_info.number || '';
            if (!extNum.includes(item.project_info.number)) {
              existing.project_info.number = extNum ? `${extNum},${item.project_info.number}` : item.project_info.number;
            }
          }
          if (item.project_info.name) {
            const extName = existing.project_info.name || '';
            if (!extName.includes(item.project_info.name)) {
              existing.project_info.name = extName ? `${extName},${item.project_info.name}` : item.project_info.name;
            }
          }
        }
      } else {
        const newItem = JSON.parse(JSON.stringify(item))
        newItem.qty = Number(newItem.qty) || 0
        newItem.target_price = undefined
        newItem.quotes = {} // Initialize quotes object
        aggregatedMap.set(key, newItem)
      }
    })
  }
  
  selectedRequestsForTask.value = Array.from(aggregatedMap.values())
  
  if (selectedRequestsForTask.value.length === 0) {
    addCustomMaterial()
  }
  
  const date = new Date().toISOString().slice(0, 10)
  taskForm.title = `${date} 批量询价 (${selectedRequestsForTask.value.length}项物料)`
  taskForm.type = isJump === true ? 'manual' : 'auto'
  taskForm.deadline = ''
  taskForm.deadlineDate = ''
  taskForm.deadlineTime = isJump === true ? '' : DEFAULT_DEADLINE_TIME
  taskForm.supplier_ids = []
  
  fetchSuppliers()
  dialogVisible.value = true
}

const confirmCreateTask = async () => {
  const formValid = await taskFormRef.value?.validate().catch(() => false)
  if (!formValid) return

  for (let i = 0; i < selectedRequestsForTask.value.length; i++) {
    const item = selectedRequestsForTask.value[i]
    if (item.is_custom && !item.material_name) {
      ElMessage.warning(`第 ${i + 1} 行物料名称不能为空`)
      return
    }
  }

  if (selectedRequestsForTask.value.length === 0) {
    ElMessage.warning('请至少添加一项物料')
    return
  }

  creatingTask.value = true
  try {
    const payload = {
      title: taskForm.title,
      type: taskForm.type,
      deadline: taskForm.type === 'auto' ? (taskForm.deadline || null) : null,
      strategy_config: taskForm.strategy_config,
      raw_requests: selectedRequestsForTask.value.map(item => ({
        ...item,
        delivery_date: item.delivery_date ? (item.delivery_date.length === 10 ? item.delivery_date + 'T00:00:00' : item.delivery_date) : null
      })),
      supplier_ids: taskForm.supplier_ids
    }
    const res = await createInquiryTask(payload)
    const createdTaskId = res.data?.id || res.id

    // 保存手动录入的报价 (如果有)
    if (taskForm.type === 'manual' && taskForm.supplier_ids.length > 0) {
      for (const item of selectedRequestsForTask.value) {
        if (!item.material_code) continue; // 必须有物料编码才能保存报价
        
        const suppliersQuotes = []
        for (const supplierId of taskForm.supplier_ids) {
          const taxNetPrice = item.quotes ? item.quotes[supplierId] : undefined
          if (taxNetPrice > 0) {
            const supplier = supplierList.value.find(s => s.id === supplierId)
            if (supplier) {
              suppliersQuotes.push({
                supplier_code: supplier.code || '',
                supplier_name: supplier.name || '未知',
                tax_net_price: Number(taxNetPrice),
                price: Number((taxNetPrice / 1.13).toFixed(2)),
                qty: Number(item.qty) || 1
              })
            }
          }
        }
        
        if (suppliersQuotes.length > 0) {
          try {
            await api.post(`/inquiry/tasks/${createdTaskId}/save-manual-quotes`, {
              material_code: item.material_code,
              suppliers: suppliersQuotes
            })
          } catch (e) {
            console.error('保存物料报价失败:', item.material_name, e)
          }
        }
      }
    }

    ElMessage.success('询价任务创建成功')
    const selectedIds = new Set(selectedRequests.value.map(r => r.erp_request_id))
    requestList.value = requestList.value.filter(r => !selectedIds.has(r.erp_request_id))
    
    const shouldJump = isJumpToCompare.value
    dialogVisible.value = false
    
    if (shouldJump) {
      isJumpToCompare.value = false
      router.push({ name: 'IntelligentCompare', query: { taskId: res.data.id || res.id } })
    } else {
      // Switch to tasks page
      router.push('/inquiries/tasks')
    }
  } catch (error) {
    console.error(error)
    ElMessage.error('创建任务失败')
  } finally {
    creatingTask.value = false
  }
}

const formatDateTime = (dateStr) => {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString()
}

const formatDate = (dateStr) => {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleDateString()
}

onMounted(() => {
  handleSyncErp()
})
</script>

<style scoped>
.page-container {
  flex: 1; /* 占据 wrapper 剩余空间 */
  min-height: 0; /* 核心：防止 flex 撑大导致外层出现滚动条 */
  display: flex;
  flex-direction: column;
  background: white;
  box-sizing: border-box;
}

.content-card {
  flex: 1;
  min-height: 0; /* 核心：传递收缩限制 */
  display: flex;
  flex-direction: column;
  overflow: hidden;
  padding: 15px;
}

.table-container {
  flex: 1;
  min-height: 0; /* 核心：让表格只占剩余空间 */
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

/* 让表格内部自己滚动，撑满父容器 */
:deep(.el-table) {
  flex: 1;
  height: 100%;
}

.toolbar {
  margin-bottom: 15px;
  display: flex;
  flex-direction: column;
  gap: 15px;
  flex-shrink: 0;
}

.toolbar-top {
  display: flex;
  justify-content: flex-start;
}

.toolbar-bottom {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.advanced-search-form {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 0;
}

.advanced-search-form .el-form-item {
  margin-bottom: 0;
  margin-right: 0;
}

.deadline-inputs {
  width: 100%;
  display: grid;
  grid-template-columns: 1fr 160px;
  gap: 12px;
}

.pagination-container {
  margin-top: 15px;
  display: flex;
  justify-content: flex-end;
  flex-shrink: 0;
}

:deep(.el-table .cell) {
  padding: 0 5px;
  line-height: 1.2;
}

:deep(.el-table td.el-table__cell, .el-table th.el-table__cell.is-leaf) {
  padding: 4px 0;
}
</style>
