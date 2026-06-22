<template>
  <div class="analysis-container">
    <div class="page-header">
      <div class="header-left">
        <el-select
          v-model="selectedSupplierId"
          placeholder="请选择要分析的供应商"
          class="supplier-selector"
          filterable
          :filter-method="filterSupplierMethod"
          :loading="loadingSuppliers"
          size="large"
          @change="handleSupplierChange"
        >
          <el-option
            v-for="item in filteredSupplierList"
            :key="String(item.id)"
            :label="item.name"
            :value="String(item.id)"
          >
            <span style="float: left">{{ item.name }}</span>
            <span v-if="item.grade" style="float: right; color: var(--el-text-color-secondary); font-size: 13px">
              {{ item.grade }}
            </span>
          </el-option>
        </el-select>
      </div>
      <el-button
        type="primary"
        :icon="RefreshRight"
        :disabled="!selectedSupplierId"
        :loading="loadingData"
        @click="refreshData(true)"
      >
        刷新数据
      </el-button>
    </div>

    <div v-if="!selectedSupplierId" class="empty-state">
      <el-empty description="请先在上方选择一个供应商，再查看分析数据。" />
    </div>

    <div v-else class="content-wrapper" v-loading="loadingData">
      <div class="stat-cards-wrapper">
        <el-row :gutter="20" class="stat-cards">
          <el-col :span="4" v-for="(stat, index) in coreStats" :key="index">
            <el-card shadow="hover" class="stat-card">
              <div class="stat-icon" :style="{ background: stat.bgColor, color: stat.color }">
                <el-icon><component :is="stat.icon" /></el-icon>
              </div>
              <div class="stat-info">
                <div class="stat-title">{{ stat.title }}</div>
                <div class="stat-value">{{ stat.prefix || '' }}{{ stat.value }}{{ stat.suffix || '' }}</div>
              </div>
            </el-card>
          </el-col>
        </el-row>
      </div>

      <div class="charts-wrapper">
        <el-row :gutter="20" class="charts-row">
          <el-col :span="24">
            <el-card shadow="hover" class="chart-card">
              <template #header>
                <div class="card-header card-header-row">
                  <span>近六个月物料含税净价走势</span>
                  <div class="chart-toolbar">
                    <el-radio-group v-model="chartMode" size="small" @change="updateChart">
                      <el-radio-button value="detail">明细版</el-radio-button>
                      <el-radio-button value="average">曲线版</el-radio-button>
                    </el-radio-group>
                    <el-select
                      v-model="chartSelectedMaterials"
                      multiple
                      collapse-tags
                      collapse-tags-tooltip
                      placeholder="选择要展示的物料"
                      style="width: 300px"
                      size="small"
                      @change="updateChart"
                    >
                      <el-option
                        v-for="item in chartAllMaterials"
                        :key="item"
                        :label="item"
                        :value="item"
                      />
                    </el-select>
                  </div>
                </div>
              </template>
              <div ref="lineChartRef" class="echarts-container"></div>
            </el-card>
          </el-col>
        </el-row>
      </div>

      <div class="table-wrapper">
        <el-card shadow="hover" class="table-card">
          <template #header>
            <div class="card-header card-header-row">
              <span>近期真实成交明细</span>
              <el-date-picker
                v-model="tableDateRange"
                type="daterange"
                range-separator="-"
                start-placeholder="开始日期"
                end-placeholder="结束日期"
                value-format="YYYY-MM-DD"
                size="small"
                :shortcuts="dateShortcuts"
                style="width: 220px"
                @change="filterTableData"
              />
            </div>
          </template>
          <div class="table-inner">
            <el-table
              :data="filteredTableData"
              style="width: 100%"
              height="100%"
              stripe
              size="small"
              row-key="bill_no"
              :expand-row-keys="expandedRowKeys"
              border
              @expand-change="handleExpand"
            >
              <el-table-column type="expand">
                <template #default="props">
                  <div style="padding: 10px 20px">
                    <el-table :data="props.row.items" size="small" border>
                      <el-table-column prop="material" label="物料名称" show-overflow-tooltip />
                      <el-table-column prop="quantity" label="采购数量" align="right" width="100" />
                      <el-table-column prop="price" label="单价(不含税)" align="right" width="120">
                        <template #default="scope">
                          <span class="money-text">￥{{ Number(scope.row.price || 0).toLocaleString() }}</span>
                        </template>
                      </el-table-column>
                      <el-table-column prop="taxNetPrice" label="含税净价" align="right" width="120">
                        <template #default="scope">
                          <span class="money-text emphasis">￥{{ Number(scope.row.taxNetPrice || 0).toLocaleString() }}</span>
                        </template>
                      </el-table-column>
                    </el-table>
                  </div>
                </template>
              </el-table-column>
              <el-table-column prop="date" label="订单日期" width="120" />
              <el-table-column prop="bill_no" label="采购订单号" width="150" />
              <el-table-column prop="total_amount" label="订单总额(含税)" align="right">
                <template #default="scope">
                  <span class="money-text emphasis">￥{{ Number(scope.row.total_amount || 0).toLocaleString() }}</span>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </el-card>
      </div>
    </div>
  </div>
</template>

<script setup>
import * as echarts from 'echarts'
import { nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { Connection, DocumentChecked, Money, RefreshRight, Timer, TrendCharts, Trophy } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import api from '../../api/index'

const SUPPLIER_ANALYSIS_SESSION_PREFIX = 'supplier_analysis_cache:'
const SUPPLIER_LIST_SESSION_KEY = 'supplier_analysis_supplier_list'
const SUPPLIER_SELECTED_SESSION_KEY = 'supplier_analysis_selected_supplier'
const PAGE_CONTEXT_SESSION_KEY = 'procurement_agent_page_context'

const supplierList = ref([])
const filteredSupplierList = ref([])
const selectedSupplierId = ref('')
const loadingSuppliers = ref(false)
const loadingData = ref(false)

const lineChartRef = ref(null)
let lineChart = null

const coreStats = ref([
  { title: '历史采购总额', value: '0', prefix: '￥', icon: Money, bgColor: '#e6f4ff', color: '#1677ff' },
  { title: '采购订单数', value: '0', suffix: ' 单', icon: DocumentChecked, bgColor: '#f6ffed', color: '#52c41a' },
  { title: '供应物料种类', value: '0', suffix: ' 种', icon: TrendCharts, bgColor: '#fff0f6', color: '#eb2f96' },
  { title: '平均含税单价', value: '0', prefix: '￥', icon: Trophy, bgColor: '#fffbe6', color: '#faad14' },
  { title: '最大单笔采购量', value: '0', suffix: ' 件', icon: Timer, bgColor: '#f0f5ff', color: '#2f54eb' },
  { title: '最近交易距今', value: '0', suffix: ' 天', icon: Connection, bgColor: '#fcffe6', color: '#ad8b00' },
])

const tableData = ref([])
const filteredTableData = ref([])
const tableDateRange = ref([])
const expandedRowKeys = ref([])
const chartAllMaterials = ref([])
const chartSelectedMaterials = ref([])
const trendDataStore = ref([])
const chartMode = ref('detail')

const dateShortcuts = [
  {
    text: '最近一周',
    value: () => {
      const end = new Date()
      const start = new Date()
      start.setDate(start.getDate() - 7)
      return [start, end]
    },
  },
  {
    text: '最近一个月',
    value: () => {
      const end = new Date()
      const start = new Date()
      start.setDate(start.getDate() - 30)
      return [start, end]
    },
  },
  {
    text: '最近三个月',
    value: () => {
      const end = new Date()
      const start = new Date()
      start.setDate(start.getDate() - 90)
      return [start, end]
    },
  },
]

const loadSessionJson = (key, fallback = null) => {
  try {
    const raw = sessionStorage.getItem(key)
    return raw ? JSON.parse(raw) : fallback
  } catch {
    return fallback
  }
}

const saveSessionJson = (key, value) => {
  try {
    sessionStorage.setItem(key, JSON.stringify(value))
  } catch {}
}

const buildSupplierAnalysisCacheKey = (supplierId) => `${SUPPLIER_ANALYSIS_SESSION_PREFIX}${supplierId || ''}`

const loadSupplierAnalysisCache = (supplierId) => {
  const payload = loadSessionJson(buildSupplierAnalysisCacheKey(supplierId), {})
  return payload?.data || null
}

const saveSupplierAnalysisCache = (supplierId, data) => {
  saveSessionJson(buildSupplierAnalysisCacheKey(supplierId), {
    data,
    cached_at: Date.now(),
  })
}

const loadSupplierListCache = () => {
  const payload = loadSessionJson(SUPPLIER_LIST_SESSION_KEY, {})
  return Array.isArray(payload?.list) ? payload.list : []
}

const saveSupplierListCache = (list) => {
  saveSessionJson(SUPPLIER_LIST_SESSION_KEY, {
    list,
    cached_at: Date.now(),
  })
}

const filterSupplierMethod = (query) => {
  if (!query) {
    filteredSupplierList.value = supplierList.value
    return
  }

  const keyword = String(query).toLowerCase()
  filteredSupplierList.value = supplierList.value.filter((item) => {
    return (item.name && item.name.toLowerCase().includes(keyword))
      || (item.short_name && item.short_name.toLowerCase().includes(keyword))
      || (item.code && item.code.toLowerCase().includes(keyword))
  })
}

const getSelectedSupplierMeta = () =>
  supplierList.value.find((item) => String(item.id) === String(selectedSupplierId.value)) || null

const persistSelectedSupplier = () => {
  try {
    if (selectedSupplierId.value) {
      sessionStorage.setItem(SUPPLIER_SELECTED_SESSION_KEY, String(selectedSupplierId.value))
    } else {
      sessionStorage.removeItem(SUPPLIER_SELECTED_SESSION_KEY)
    }
  } catch {}
}

const restoreSelectedSupplier = () => {
  const cachedId = sessionStorage.getItem(SUPPLIER_SELECTED_SESSION_KEY) || ''
  if (cachedId && supplierList.value.some((item) => String(item.id) === cachedId)) {
    selectedSupplierId.value = cachedId
  }
}

const saveSupplierPageContext = () => {
  const current = getSelectedSupplierMeta()
  saveSessionJson(PAGE_CONTEXT_SESSION_KEY, {
    route_name: '供应商分析',
    material_code: '',
    material_name: '',
    supplier_code: current?.code || '',
    supplier_name: current?.name || '',
  })
}

const filterTableData = () => {
  if (!tableDateRange.value || tableDateRange.value.length !== 2) {
    filteredTableData.value = [...tableData.value]
    return
  }

  const [start, end] = tableDateRange.value
  filteredTableData.value = tableData.value.filter((row) => row.date >= start && row.date <= end)
}

const handleExpand = (_row, expandedRows) => {
  expandedRowKeys.value = expandedRows.map((item) => item.bill_no)
}

const applySupplierAnalysisData = async (data = {}) => {
  const stats = data.coreStats || {}
  coreStats.value[0].value = Number(stats.totalAmount || 0).toLocaleString()
  coreStats.value[1].value = stats.orderCount || 0
  coreStats.value[2].value = stats.materialCount || 0
  coreStats.value[3].value = stats.avgTaxNetPrice || 0
  coreStats.value[4].value = stats.maxQty || 0
  coreStats.value[5].value = stats.daysSinceLastOrder || 0

  tableData.value = Array.isArray(data.tableData) ? data.tableData : []

  const today = new Date()
  const lastSixMonths = new Date(today)
  lastSixMonths.setMonth(today.getMonth() - 6)
  const formatDate = (date) => `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
  tableDateRange.value = [formatDate(lastSixMonths), formatDate(today)]
  filterTableData()

  const trendInfo = data.trend || { data: [], topMaterials: [], allMaterials: [] }
  chartAllMaterials.value = trendInfo.allMaterials || []
  chartSelectedMaterials.value = trendInfo.topMaterials || []
  trendDataStore.value = trendInfo.data || []

  await nextTick()
  updateChart()
}

const refreshData = async (forceRefresh = false) => {
  if (!selectedSupplierId.value) return

  persistSelectedSupplier()
  saveSupplierPageContext()

  const cachedData = !forceRefresh ? loadSupplierAnalysisCache(selectedSupplierId.value) : null
  if (cachedData) {
    await applySupplierAnalysisData(cachedData)
  }

  loadingData.value = !cachedData
  try {
    const res = await api.get(`/supplier/${selectedSupplierId.value}/analysis`, {
      params: { force_refresh: forceRefresh },
    })
    saveSupplierAnalysisCache(selectedSupplierId.value, res.data || {})
    await applySupplierAnalysisData(res.data || {})
  } catch (error) {
    if (!cachedData) {
      console.error(error)
      ElMessage.error('获取供应商分析数据失败')
    }
  } finally {
    loadingData.value = false
  }
}

const handleSupplierChange = async () => {
  persistSelectedSupplier()
  saveSupplierPageContext()
  await refreshData(false)
}

const initCharts = (trendData = []) => {
  if (!lineChartRef.value) return
  if (!lineChart) lineChart = echarts.init(lineChartRef.value)

  if (trendData.length === 0 || chartSelectedMaterials.value.length === 0) {
    lineChart.clear()
    lineChart.setOption({
      title: {
        text: '暂无历史采购数据或未选择物料',
        left: 'center',
        top: 'center',
        textStyle: { color: '#ccc', fontSize: 14, fontWeight: 'normal' },
      },
    })
    return
  }

  const filteredTrendData = trendData.filter((item) => chartSelectedMaterials.value.includes(item.material))
  const materials = [...chartSelectedMaterials.value]

  let series = []
  let tooltipFormatter = null

  if (chartMode.value === 'average') {
    series = materials.map((material) => {
      const materialRows = filteredTrendData.filter((item) => item.material === material)
      const dateMap = {}
      materialRows.forEach((item) => {
        if (!dateMap[item.date]) dateMap[item.date] = { sum: 0, count: 0 }
        dateMap[item.date].sum += Number(item.price || 0)
        dateMap[item.date].count += 1
      })
      const avgData = Object.keys(dateMap).sort().map((date) => [date, dateMap[date].sum / dateMap[date].count])
      return {
        name: material,
        type: 'line',
        smooth: true,
        symbolSize: 6,
        data: avgData,
      }
    })
    tooltipFormatter = (params) =>
      `${params.seriesName}<br/>日期: ${params.value[0]}<br/>日均净价: ￥${Number(params.value[1] || 0).toFixed(2)}`
  } else {
    series = materials.map((material) => ({
      name: material,
      type: 'scatter',
      symbolSize: 10,
      data: filteredTrendData
        .filter((item) => item.material === material)
        .map((item) => [item.date, Number(item.price || 0), item.bill_no || '']),
    }))
    tooltipFormatter = (params) => {
      const billNo = params.value[2] ? `<br/>订单号: ${params.value[2]}` : ''
      return `${params.seriesName}<br/>日期: ${params.value[0]}${billNo}<br/>净价: ￥${Number(params.value[1] || 0).toFixed(2)}`
    }
  }

  lineChart.setOption(
    {
      tooltip: { trigger: 'item', formatter: tooltipFormatter },
      legend: { data: materials, top: 0 },
      grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
      xAxis: {
        type: 'time',
        name: '订单日期',
        splitLine: { show: false },
        axisLabel: {
          formatter(value) {
            const date = new Date(value)
            return `${date.getMonth() + 1}月${date.getDate()}日`
          },
        },
      },
      yAxis: { type: 'value', name: '采购含税净价(元)' },
      series,
    },
    true,
  )
}

const updateChart = () => {
  nextTick(() => {
    initCharts(trendDataStore.value || [])
  })
}

const fetchAllSuppliersForAnalysis = async (forceRefresh = false) => {
  const cachedList = !forceRefresh ? loadSupplierListCache() : []
  if (cachedList.length > 0) {
    supplierList.value = cachedList
    filteredSupplierList.value = cachedList
    restoreSelectedSupplier()
  }

  loadingSuppliers.value = cachedList.length === 0
  try {
    const pageSize = 200
    let page = 1
    let total = 0
    let allSuppliers = []

    do {
      const res = await api.get('/supplier/list', {
        params: {
          page,
          page_size: pageSize,
        },
      })
      const payload = res.data || {}
      const currentList = Array.isArray(payload.list) ? payload.list : []
      total = Number(payload.total || 0)
      allSuppliers = allSuppliers.concat(currentList)
      page += 1
    } while (allSuppliers.length < total)

    supplierList.value = allSuppliers
    filteredSupplierList.value = allSuppliers
    saveSupplierListCache(allSuppliers)

    const previous = selectedSupplierId.value
    restoreSelectedSupplier()
    if (!selectedSupplierId.value && allSuppliers.length > 0) {
      selectedSupplierId.value = String(allSuppliers[0].id)
    }

    if (selectedSupplierId.value && selectedSupplierId.value !== previous) {
      await refreshData(false)
    }
  } catch (error) {
    console.error(error)
    if (cachedList.length === 0) {
      ElMessage.error('获取供应商列表失败')
    }
  } finally {
    loadingSuppliers.value = false
  }
}

const handleResize = () => {
  lineChart?.resize()
}

onMounted(async () => {
  const cachedList = loadSupplierListCache()
  if (cachedList.length > 0) {
    supplierList.value = cachedList
    filteredSupplierList.value = cachedList
    restoreSelectedSupplier()
  }

  if (selectedSupplierId.value) {
    saveSupplierPageContext()
    await refreshData(false)
  }

  await fetchAllSuppliersForAnalysis(false)
  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  lineChart?.dispose()
  lineChart = null
})
</script>

<style scoped>
.analysis-container {
  height: 100%;
  display: flex;
  flex-direction: column;
  background-color: var(--bg-secondary);
  box-sizing: border-box;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 15px 20px;
  background: white;
  border-bottom: 1px solid #ebeef5;
  flex-shrink: 0;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 20px;
}

.supplier-selector {
  width: 350px;
}

.empty-state {
  flex: 1;
  display: flex;
  justify-content: center;
  align-items: center;
  background: white;
  margin: 15px;
  border-radius: 8px;
}

.content-wrapper {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 15px;
  gap: 15px;
  min-height: 0;
  overflow-y: auto;
}

.stat-cards-wrapper {
  flex-shrink: 0;
}

.stat-cards {
  margin-bottom: 0;
}

.stat-card {
  border-radius: 8px;
  height: 100%;
}

:deep(.stat-card .el-card__body) {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  padding: 15px;
  text-align: center;
}

.stat-icon {
  width: 48px;
  height: 48px;
  border-radius: 8px;
  display: flex;
  justify-content: center;
  align-items: center;
  font-size: 24px;
  margin-bottom: 10px;
}

.stat-info {
  flex: 1;
  width: 100%;
}

.stat-title {
  font-size: 13px;
  color: var(--text-secondary);
  margin-bottom: 5px;
  white-space: normal;
}

.stat-value {
  font-size: 20px;
  font-weight: bold;
  color: var(--text-primary);
  white-space: nowrap;
}

.charts-wrapper {
  flex-shrink: 0;
  height: 350px;
}

.charts-row,
.charts-row .el-col {
  height: 100%;
}

.chart-card {
  border-radius: 8px;
  height: 100%;
  display: flex;
  flex-direction: column;
}

:deep(.chart-card .el-card__body) {
  flex: 1;
  padding: 10px;
  height: 100%;
  min-height: 0;
}

.echarts-container {
  width: 100%;
  height: 100%;
}

.table-wrapper {
  flex: 1;
  min-height: 400px;
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
}

.table-card {
  border-radius: 8px;
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

:deep(.table-card .el-card__body) {
  flex: 1;
  padding: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.table-inner {
  flex: 1;
  min-height: 0;
}

.card-header {
  font-weight: bold;
  font-size: 15px;
}

.card-header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
}

.chart-toolbar {
  display: flex;
  align-items: center;
  gap: 15px;
}

.money-text {
  font-family: Monaco, Consolas, monospace;
  font-weight: 500;
  color: #f56c6c;
}

.money-text.emphasis {
  font-weight: bold;
}
</style>
