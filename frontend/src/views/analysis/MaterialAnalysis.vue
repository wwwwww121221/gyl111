<template>
  <div class="analysis-container">
    <div class="page-header">
      <div class="header-left">
        <el-select
          v-model="selectedMaterial"
          placeholder="请选择要分析的物料"
          class="material-selector"
          filterable
          :loading="loadingMaterials"
          @change="handleMaterialChange"
          @visible-change="handleMaterialDropdownVisible"
          size="large"
          style="width: 400px"
        >
          <el-option
            v-for="item in materialList"
            :key="item.material_code"
            :label="getMaterialOptionLabel(item)"
            :value="item.material_code"
          >
            <span style="float: left">
              {{ item.material_name }}
              <span v-if="item.material_model"> / {{ item.material_model }}</span>
            </span>
            <span style="float: right; color: var(--el-text-color-secondary); font-size: 13px">
              {{ item.material_code }} | {{ item.count || 0 }} 次采购
            </span>
          </el-option>
        </el-select>
      </div>
      <el-button
        type="primary"
        :icon="RefreshRight"
        :disabled="!selectedMaterial"
        :loading="loadingData"
        @click="handleSelectMaterial(true)"
      >
        刷新数据
      </el-button>
    </div>

    <div v-if="!selectedMaterial" class="empty-state">
      <el-empty description="请先在上方选择一个物料，再查看分析数据。" />
    </div>

    <div v-else class="content-wrapper" v-loading="loadingData">
      <el-row :gutter="20" class="kpi-row">
        <el-col :span="6" v-for="(kpi, index) in kpiCards" :key="index" class="kpi-col">
          <el-card shadow="hover" class="kpi-card" :class="kpi.type">
            <div class="kpi-content">
              <div class="kpi-title">{{ kpi.title }}</div>
              <div class="kpi-value">
                <span v-if="kpi.prefix" class="kpi-prefix">{{ kpi.prefix }}</span>
                {{ kpi.value }}
                <span v-if="kpi.suffix" class="kpi-suffix">{{ kpi.suffix }}</span>
              </div>
              <div v-if="kpi.desc" class="kpi-desc">{{ kpi.desc }}</div>
            </div>
            <el-icon class="kpi-icon"><component :is="kpi.icon" /></el-icon>
          </el-card>
        </el-col>
      </el-row>

      <el-row :gutter="20" class="charts-row">
        <el-col :span="24" style="margin-bottom: 20px">
          <el-card shadow="hover" class="chart-card">
            <template #header>
              <div class="card-header card-header-row">
                <span>价格趋势对比</span>
                <div class="chart-toolbar">
                  <el-select
                    v-model="selectedChartSuppliers"
                    multiple
                    collapse-tags
                    collapse-tags-tooltip
                    clearable
                    placeholder="留空显示所有供应商"
                    size="small"
                    style="width: 350px"
                    @change="renderLineChart"
                  >
                    <el-option
                      v-for="supplier in supplierOptions"
                      :key="supplier"
                      :label="supplier"
                      :value="supplier"
                    />
                  </el-select>
                  <el-radio-group v-model="chartMode" size="small" @change="renderLineChart">
                    <el-radio-button value="detail">明细点</el-radio-button>
                    <el-radio-button value="average">均价线</el-radio-button>
                  </el-radio-group>
                </div>
              </div>
            </template>
            <div ref="lineChartRef" class="echarts-container"></div>
          </el-card>
        </el-col>
      </el-row>

      <el-row :gutter="20" class="charts-row">
        <el-col :span="24" style="margin-bottom: 20px">
          <el-card shadow="hover" class="chart-card">
            <template #header>
              <div class="card-header">
                <span>采购金额分布（Top 5）</span>
              </div>
            </template>
            <div ref="pieChartRef" class="echarts-container"></div>
          </el-card>
        </el-col>
      </el-row>

      <div class="table-wrapper">
        <el-card shadow="hover" class="table-card">
          <template #header>
            <div class="card-header card-header-row">
              <span>同一物料多供应商成交明细</span>
              <div class="chart-toolbar">
                <el-select
                  v-model="filterSupplierCode"
                  placeholder="所有供应商"
                  clearable
                  size="small"
                  style="width: 180px"
                  @change="handleHistoryFilterChange"
                >
                  <el-option
                    v-for="supplier in historySupplierOptions"
                    :key="supplier.code || supplier.name"
                    :label="supplier.name"
                    :value="supplier.code"
                  />
                </el-select>
                <el-date-picker
                  v-model="tableDateRange"
                  type="daterange"
                  range-separator="-"
                  start-placeholder="开始日期"
                  end-placeholder="结束日期"
                  value-format="YYYY-MM-DD"
                  size="small"
                  :shortcuts="dateShortcuts"
                  style="width: 240px"
                  @change="handleHistoryFilterChange"
                />
              </div>
            </div>
          </template>
          <div class="table-inner">
            <el-table
              class="history-table"
              v-loading="historyLoading"
              :data="historyRows"
              style="width: 100%"
              :height="HISTORY_TABLE_HEIGHT"
              stripe
              size="small"
              border
            >
              <el-table-column prop="date" label="订单日期" width="120" sortable />
              <el-table-column prop="bill_no" label="采购单号" width="160" show-overflow-tooltip />
              <el-table-column prop="supplier_name" label="供应商名称" min-width="180" show-overflow-tooltip />
              <el-table-column prop="supplier_grade" label="评级" width="80" align="center">
                <template #default="{ row }">
                  <el-tag :type="row.supplier_grade ? 'success' : 'info'" size="small">
                    {{ row.supplier_grade || '无' }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="qty" label="采购数量" align="right" width="100" />
              <el-table-column prop="price" label="单价(不含税)" align="right" width="140">
                <template #default="{ row }">
                  <span class="money-text">￥{{ Number(row.price || 0).toLocaleString() }}</span>
                </template>
              </el-table-column>
              <el-table-column prop="tax_net_price" label="含税净价" align="right" width="140">
                <template #default="{ row }">
                  <span class="money-text emphasis">￥{{ Number(row.tax_net_price || 0).toLocaleString() }}</span>
                </template>
              </el-table-column>
              <el-table-column prop="project_number" label="项目编号" min-width="140" show-overflow-tooltip />
            </el-table>
          </div>
          <div class="table-pagination">
            <div class="table-pagination__meta">
              当前第 {{ historyPage }} 页
              <span v-if="historyRows.length">，本页 {{ historyRows.length }} 条</span>
            </div>
            <div class="table-pagination__actions">
              <el-pagination
                small
                background
                layout="prev, pager, next"
                :current-page="historyPage"
                :page-count="historyPageCount"
                @current-change="handleHistoryPageChange"
              />
            </div>
          </div>
        </el-card>
      </div>
    </div>
  </div>
</template>

<script setup>
import * as echarts from 'echarts'
import { computed, markRaw, nextTick, onMounted, onUnmounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Money, RefreshRight, ShoppingCart, TrendCharts, User } from '@element-plus/icons-vue'
import { getMaterialAnalysis, getMaterialAnalysisHistory, getMaterialList } from '../../api/material'

const MATERIAL_ANALYSIS_SESSION_PREFIX = 'material_analysis_cache:'
const MATERIAL_LIST_SESSION_KEY = 'material_analysis_material_list'
const MATERIAL_SELECTED_SESSION_KEY = 'material_analysis_selected_material'
const MATERIAL_SELECTED_META_SESSION_KEY = 'material_analysis_selected_material_meta'
const PAGE_CONTEXT_SESSION_KEY = 'procurement_agent_page_context'
const MATERIAL_LIST_LIMIT = 1200
const HISTORY_PAGE_SIZE = 20
const HISTORY_TABLE_HEIGHT = 420

const materialList = ref([])
const selectedMaterial = ref('')
const loadingData = ref(false)
const historyLoading = ref(false)
const loadingMaterials = ref(false)
const materialsLoaded = ref(false)
const selectedChartSuppliers = ref([])
const chartMode = ref('detail')

const lineChartRef = ref(null)
const pieChartRef = ref(null)
let lineChart = null
let pieChart = null

const analysisData = ref({
  trend: [],
  supplier_share: [],
  all_suppliers: [],
  history_suppliers: [],
})

const tableDateRange = ref([])
const filterSupplierCode = ref('')
const historyRows = ref([])
const historyPage = ref(1)
const historyHasMore = ref(false)
const historyPageCount = computed(() => (historyHasMore.value ? historyPage.value + 1 : historyPage.value))

const kpiCards = ref([
  { title: '历史采购总额', value: '0.00', prefix: '￥', type: 'primary', icon: markRaw(Money), desc: '' },
  { title: '总采购数量', value: '0', type: 'success', icon: markRaw(ShoppingCart), desc: '' },
  { title: '合作供应商数', value: '0', type: 'warning', icon: markRaw(User), suffix: ' 家', desc: '' },
  { title: '历史平均净价', value: '0.00', prefix: '￥', type: 'danger', icon: markRaw(TrendCharts), desc: '' },
])

const supplierOptions = computed(() => analysisData.value.all_suppliers || [])
const historySupplierOptions = computed(() => analysisData.value.history_suppliers || [])

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

const mergeMaterialIntoList = (material) => {
  if (!material?.material_code) return
  const currentList = Array.isArray(materialList.value) ? [...materialList.value] : []
  const exists = currentList.some((item) => item.material_code === material.material_code)
  materialList.value = exists ? currentList : [material, ...currentList]
}

const buildMaterialAnalysisCacheKey = (materialCode) => `${MATERIAL_ANALYSIS_SESSION_PREFIX}${materialCode || ''}`

const loadMaterialAnalysisCache = (materialCode) => {
  const payload = loadSessionJson(buildMaterialAnalysisCacheKey(materialCode), {})
  return payload?.data || null
}

const saveMaterialAnalysisCache = (materialCode, data) => {
  saveSessionJson(buildMaterialAnalysisCacheKey(materialCode), {
    data,
    cached_at: Date.now(),
  })
}

const loadMaterialListCache = () => {
  const payload = loadSessionJson(MATERIAL_LIST_SESSION_KEY, {})
  return Array.isArray(payload?.list) ? payload.list : []
}

const saveMaterialListCache = (list) => {
  saveSessionJson(MATERIAL_LIST_SESSION_KEY, {
    list,
    cached_at: Date.now(),
  })
}

const getMaterialOptionLabel = (item) => {
  const parts = [item.material_name]
  if (item.material_model) parts.push(item.material_model)
  if (item.material_code) parts.push(item.material_code)
  return parts.filter(Boolean).join(' / ')
}

const getSelectedMaterialMeta = () =>
  materialList.value.find((item) => item.material_code === selectedMaterial.value) || null

const persistSelectedMaterial = () => {
  try {
    if (selectedMaterial.value) {
      sessionStorage.setItem(MATERIAL_SELECTED_SESSION_KEY, selectedMaterial.value)
    } else {
      sessionStorage.removeItem(MATERIAL_SELECTED_SESSION_KEY)
    }
  } catch {}
}

const persistSelectedMaterialMeta = () => {
  const current = getSelectedMaterialMeta()
  if (!current) return
  saveSessionJson(MATERIAL_SELECTED_META_SESSION_KEY, current)
}

const restoreSelectedMaterial = () => {
  const cachedCode = sessionStorage.getItem(MATERIAL_SELECTED_SESSION_KEY) || ''
  if (cachedCode) {
    selectedMaterial.value = cachedCode
  }
  const cachedMeta = loadSessionJson(MATERIAL_SELECTED_META_SESSION_KEY, null)
  if (cachedMeta?.material_code) {
    mergeMaterialIntoList(cachedMeta)
  }
}

const saveMaterialPageContext = () => {
  const current = getSelectedMaterialMeta()
  saveSessionJson(PAGE_CONTEXT_SESSION_KEY, {
    route_name: '物料分析',
    material_code: selectedMaterial.value || '',
    material_name: current?.material_name || '',
    supplier_code: '',
    supplier_name: '',
  })
}

const loadHistoryPage = async (forceRefresh = false) => {
  if (!selectedMaterial.value) {
    historyRows.value = []
    historyHasMore.value = false
    return
  }

  historyLoading.value = true
  try {
    const params = {
      page: historyPage.value,
      page_size: HISTORY_PAGE_SIZE,
      supplier_code: filterSupplierCode.value || undefined,
      force_refresh: forceRefresh,
    }

    if (tableDateRange.value && tableDateRange.value.length === 2) {
      params.start_date = tableDateRange.value[0]
      params.end_date = tableDateRange.value[1]
    }

    const res = await getMaterialAnalysisHistory(selectedMaterial.value, params)
    const payload = res.data || {}
    historyRows.value = Array.isArray(payload.items) ? payload.items : []
    historyHasMore.value = Boolean(payload.has_more)
  } catch (error) {
    historyRows.value = []
    historyHasMore.value = false
    ElMessage.error('获取物料成交明细失败')
  } finally {
    historyLoading.value = false
  }
}

const handleHistoryFilterChange = async () => {
  historyPage.value = 1
  await loadHistoryPage(false)
}

const handleHistoryPrevPage = async () => {
  if (historyPage.value <= 1) return
  historyPage.value -= 1
  await loadHistoryPage(false)
}

const handleHistoryNextPage = async () => {
  if (!historyHasMore.value) return
  historyPage.value += 1
  await loadHistoryPage(false)
}

const handleHistoryPageChange = async (page) => {
  const nextPage = Number(page || 1)
  if (nextPage === historyPage.value) return
  if (nextPage < historyPage.value) {
    historyPage.value = nextPage
    await loadHistoryPage(false)
    return
  }
  if (nextPage === historyPage.value + 1 && historyHasMore.value) {
    historyPage.value = nextPage
    await loadHistoryPage(false)
  }
}

const applyMaterialAnalysisData = async (data = {}) => {
  const kpi = data.kpi || {}
  kpiCards.value[0].value = Number(kpi.total_amount || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  kpiCards.value[1].value = Number(kpi.total_qty || 0).toLocaleString('zh-CN', { maximumFractionDigits: 2 })
  kpiCards.value[2].value = kpi.supplier_count || 0
  kpiCards.value[3].value = Number(kpi.avg_price || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  kpiCards.value[3].desc = kpi.lowest_price
    ? `最低价: ￥${Number(kpi.lowest_price).toFixed(2)} (${kpi.lowest_supplier || '-'})`
    : ''

  analysisData.value = {
    trend: data.trend || [],
    supplier_share: data.supplier_share || [],
    all_suppliers: data.all_suppliers || [],
    history_suppliers: data.history_suppliers || [],
  }

  const topSupplier = analysisData.value.supplier_share?.[0]?.name
  selectedChartSuppliers.value = topSupplier && topSupplier !== '其他' ? [topSupplier] : []
  tableDateRange.value = []
  filterSupplierCode.value = ''
  historyPage.value = 1

  await nextTick()
  renderLineChart()
  renderPieChart()
}

const fetchMaterials = async (forceRefresh = false) => {
  const cachedList = !forceRefresh ? loadMaterialListCache() : []
  if (cachedList.length > 0) {
    materialList.value = cachedList
    materialsLoaded.value = true
    restoreSelectedMaterial()
  }

  if (!forceRefresh && materialsLoaded.value) return

  loadingMaterials.value = true
  try {
    const res = await getMaterialList({ limit: MATERIAL_LIST_LIMIT, force_refresh: forceRefresh })
    materialList.value = Array.isArray(res.data) ? res.data : []
    saveMaterialListCache(materialList.value)
    materialsLoaded.value = true
    restoreSelectedMaterial()
  } catch {
    if (materialList.value.length === 0) {
      ElMessage.error('获取物料列表失败')
    }
  } finally {
    loadingMaterials.value = false
  }
}

const handleMaterialDropdownVisible = (visible) => {
  if (visible && !materialsLoaded.value && !loadingMaterials.value) {
    fetchMaterials(false)
  }
}

const handleMaterialChange = async () => {
  persistSelectedMaterial()
  persistSelectedMaterialMeta()
  saveMaterialPageContext()
  await handleSelectMaterial(false)
}

const handleSelectMaterial = async (forceRefresh = false) => {
  if (!selectedMaterial.value) return

  persistSelectedMaterial()
  persistSelectedMaterialMeta()
  saveMaterialPageContext()

  const cachedData = !forceRefresh ? loadMaterialAnalysisCache(selectedMaterial.value) : null
  if (cachedData) {
    await applyMaterialAnalysisData(cachedData)
    await loadHistoryPage(false)
  }

  loadingData.value = !cachedData
  try {
    const res = await getMaterialAnalysis(selectedMaterial.value, { force_refresh: forceRefresh })
    const data = res.data || {}
    saveMaterialAnalysisCache(selectedMaterial.value, data)
    await applyMaterialAnalysisData(data)
    await loadHistoryPage(forceRefresh)
  } catch {
    if (!cachedData) {
      ElMessage.error('获取物料分析数据失败')
    }
  } finally {
    loadingData.value = false
  }
}

const renderLineChart = () => {
  if (!lineChartRef.value) return
  if (!lineChart) lineChart = echarts.init(lineChartRef.value)

  let trendData = Array.isArray(analysisData.value.trend) ? analysisData.value.trend.slice() : []
  if (selectedChartSuppliers.value.length > 0) {
    trendData = trendData.filter((item) => selectedChartSuppliers.value.includes(item.supplier))
  }

  if (trendData.length === 0) {
    lineChart.clear()
    lineChart.setOption({
      title: {
        text: '暂无符合条件的采购数据',
        left: 'center',
        top: 'center',
        textStyle: { color: '#ccc', fontSize: 14, fontWeight: 'normal' },
      },
    })
    return
  }

  const suppliers = Array.from(new Set(trendData.map((item) => item.supplier).filter(Boolean)))
  let series = []
  let tooltipFormatter = null

  if (chartMode.value === 'average') {
    series = suppliers.map((supplier) => {
      const supplierData = trendData.filter((item) => item.supplier === supplier)
      const dateMap = {}
      supplierData.forEach((item) => {
        if (!dateMap[item.date]) dateMap[item.date] = { sum: 0, count: 0 }
        dateMap[item.date].sum += Number(item.price || 0)
        dateMap[item.date].count += 1
      })
      const avgData = Object.keys(dateMap).sort().map((date) => [date, dateMap[date].sum / dateMap[date].count])
      return {
        name: supplier,
        type: 'line',
        smooth: true,
        symbolSize: 6,
        data: avgData,
      }
    })
    tooltipFormatter = (params) =>
      `${params.seriesName}<br/>日期: ${params.value[0]}<br/>日均净价: ￥${Number(params.value[1] || 0).toFixed(2)}`
  } else {
    series = suppliers.map((supplier) => ({
      name: supplier,
      type: 'scatter',
      symbolSize: 10,
      data: trendData
        .filter((item) => item.supplier === supplier)
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
      legend: { type: 'scroll', data: suppliers, top: 0, padding: [5, 20] },
      grid: { left: '3%', right: '4%', bottom: '3%', top: '15%', containLabel: true },
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

const renderPieChart = () => {
  if (!pieChartRef.value) return
  if (!pieChart) pieChart = echarts.init(pieChartRef.value)

  const pieData = Array.isArray(analysisData.value.supplier_share) ? analysisData.value.supplier_share : []
  if (pieData.length === 0) {
    pieChart.clear()
    pieChart.setOption({
      title: {
        text: '暂无数据',
        left: 'center',
        top: 'center',
        textStyle: { color: '#ccc', fontSize: 14, fontWeight: 'normal' },
      },
    })
    return
  }

  pieChart.setOption(
    {
      tooltip: {
        trigger: 'item',
        formatter: '{a} <br/>{b} : ￥{c} ({d}%)',
      },
      legend: {
        type: 'scroll',
        orient: 'vertical',
        right: 10,
        top: 20,
        bottom: 20,
      },
      series: [
        {
          name: '采购金额',
          type: 'pie',
          radius: ['40%', '70%'],
          center: ['35%', '50%'],
          avoidLabelOverlap: false,
          itemStyle: {
            borderRadius: 5,
            borderColor: '#fff',
            borderWidth: 2,
          },
          label: { show: false },
          emphasis: { label: { show: false } },
          labelLine: { show: false },
          data: pieData,
        },
      ],
    },
    true,
  )
}

const handleResize = () => {
  lineChart?.resize()
  pieChart?.resize()
}

onMounted(async () => {
  const cachedList = loadMaterialListCache()
  if (cachedList.length > 0) {
    materialList.value = cachedList
    materialsLoaded.value = true
  }

  restoreSelectedMaterial()

  if (selectedMaterial.value) {
    saveMaterialPageContext()
    await handleSelectMaterial(false)
  }

  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  lineChart?.dispose()
  pieChart?.dispose()
  lineChart = null
  pieChart = null
})
</script>

<style scoped>
.analysis-container {
  height: 100%;
  display: flex;
  flex-direction: column;
  background-color: var(--el-bg-color-page);
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  background-color: #fff;
  border-radius: 8px;
  margin-bottom: 16px;
  box-shadow: 0 1px 4px rgba(0, 21, 41, 0.04);
}

.empty-state {
  flex: 1;
  display: flex;
  justify-content: center;
  align-items: center;
  background: #fff;
  border-radius: 8px;
}

.content-wrapper {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
  gap: 16px;
  padding-right: 10px;
  padding-bottom: 96px;
}

.kpi-row {
  margin-bottom: 0 !important;
  display: flex;
  align-items: stretch;
}

.kpi-col {
  display: flex;
}

.kpi-card {
  border: none;
  border-radius: 8px;
  transition: all 0.3s;
  position: relative;
  overflow: hidden;
  width: 100%;
  display: flex;
  flex-direction: column;
}

.kpi-card :deep(.el-card__body) {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: center;
}

.kpi-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.kpi-content {
  position: relative;
  z-index: 1;
}

.kpi-title {
  font-size: 14px;
  color: var(--el-text-color-secondary);
  margin-bottom: 8px;
}

.kpi-value {
  font-size: 28px;
  font-weight: bold;
  color: var(--el-text-color-primary);
  margin-bottom: 4px;
}

.kpi-prefix,
.kpi-suffix {
  font-size: 14px;
  font-weight: normal;
  color: var(--el-text-color-regular);
}

.kpi-desc {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-top: 4px;
  min-height: 17px;
}

.kpi-icon {
  position: absolute;
  right: 20px;
  top: 50%;
  transform: translateY(-50%);
  font-size: 48px;
  opacity: 0.1;
  z-index: 0;
}

.kpi-card.primary .kpi-icon {
  color: var(--el-color-primary);
}

.kpi-card.success .kpi-icon {
  color: var(--el-color-success);
}

.kpi-card.warning .kpi-icon {
  color: var(--el-color-warning);
}

.kpi-card.danger .kpi-icon {
  color: var(--el-color-danger);
}

.charts-row {
  margin-bottom: 0 !important;
}

.chart-card {
  border-radius: 8px;
  border: none;
  height: 380px;
  display: flex;
  flex-direction: column;
}

.chart-card :deep(.el-card__body) {
  flex: 1;
  padding: 10px;
  height: calc(100% - 55px);
}

.echarts-container {
  width: 100%;
  height: 100%;
}

.card-header {
  font-weight: bold;
  color: var(--el-text-color-primary);
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

.table-wrapper {
  flex: 0 0 auto;
  min-height: 0;
}

.table-card {
  display: flex;
  flex-direction: column;
  border: none;
  border-radius: 8px;
}

.table-card :deep(.el-card__body) {
  padding: 0;
  overflow: visible;
  display: flex;
  flex-direction: column;
}

.table-inner {
  padding: 16px 16px 0;
  box-sizing: border-box;
}

.table-pagination {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px 16px;
  background: #fff;
  border-top: 1px solid var(--el-border-color-lighter);
  color: var(--el-text-color-secondary);
  font-size: 13px;
  flex-shrink: 0;
  position: sticky;
  bottom: 0;
  z-index: 2;
}

.table-pagination__actions {
  display: flex;
  gap: 8px;
}

.money-text {
  font-family: 'Courier New', Courier, monospace;
}

.money-text.emphasis {
  color: #ff4d4f;
  font-weight: bold;
}
</style>
