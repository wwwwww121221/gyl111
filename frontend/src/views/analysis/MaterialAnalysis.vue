<template>
  <div class="analysis-container">
    <div class="page-header">
      <div class="header-left">
        <el-select
          v-model="selectedMaterial"
          placeholder="请选择要分析的物料"
          class="material-selector"
          @change="handleSelectMaterial"
          filterable
          :loading="loadingMaterials"
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
            <span style="float: left">{{ item.material_name }}<span v-if="item.material_model"> / {{ item.material_model }}</span></span>
            <span style="float: right; color: var(--el-text-color-secondary); font-size: 13px">
              {{ item.material_code }} | {{ item.count }} 次采购
            </span>
          </el-option>
        </el-select>
      </div>
      <el-button type="primary" :icon="RefreshRight" @click="handleSelectMaterial" :disabled="!selectedMaterial" :loading="loadingData">刷新数据</el-button>
    </div>

    <!-- 空状态 -->
    <div v-if="!selectedMaterial" class="empty-state">
      <el-empty description="请在上方选择一个物料以查看供应商比价分析" />
    </div>

    <div v-else class="content-wrapper" v-loading="loadingData">
      <!-- 核心指标 KPI -->
      <el-row :gutter="20" class="kpi-row">
        <el-col :span="6" v-for="(kpi, index) in kpiCards" :key="index" class="kpi-col">
          <el-card shadow="hover" class="kpi-card" :class="kpi.type">
            <div class="kpi-content">
              <div class="kpi-title">{{ kpi.title }}</div>
              <div class="kpi-value">
                <span class="kpi-prefix" v-if="kpi.prefix">{{ kpi.prefix }}</span>
                {{ kpi.value }}
                <span class="kpi-suffix" v-if="kpi.suffix">{{ kpi.suffix }}</span>
              </div>
              <div class="kpi-desc" v-if="kpi.desc">{{ kpi.desc }}</div>
            </div>
            <el-icon class="kpi-icon"><component :is="kpi.icon" /></el-icon>
          </el-card>
        </el-col>
      </el-row>

      <!-- 图表区域 -->
      <el-row :gutter="20" class="charts-row">
        <el-col :span="24" style="margin-bottom: 20px;">
          <el-card shadow="hover" class="chart-card">
            <template #header>
              <div class="card-header" style="display: flex; justify-content: space-between; align-items: center;">
                <span>价格走势对比</span>
                <div style="display: flex; align-items: center;">
                  <el-select
                    v-model="selectedChartSuppliers"
                    multiple
                    collapse-tags
                    collapse-tags-tooltip
                    clearable
                    placeholder="留空展示所有供应商"
                    size="small"
                    @change="renderLineChart"
                    style="width: 350px; margin-right: 15px;"
                  >
                    <el-option v-for="s in supplierOptions" :key="s" :label="s" :value="s" />
                  </el-select>
                  <el-radio-group v-model="chartMode" size="small" @change="renderLineChart">
                    <el-radio-button label="detail">明细版</el-radio-button>
                    <el-radio-button label="average">曲线版</el-radio-button>
                  </el-radio-group>
                </div>
              </div>
            </template>
            <div ref="lineChartRef" class="echarts-container"></div>
          </el-card>
        </el-col>
      </el-row>
      
      <el-row :gutter="20" class="charts-row">
        <el-col :span="24" style="margin-bottom: 20px;">
          <el-card shadow="hover" class="chart-card">
            <template #header>
              <div class="card-header">
                <span>采购份额分布 (Top 5)</span>
              </div>
            </template>
            <div ref="pieChartRef" class="echarts-container"></div>
          </el-card>
        </el-col>
      </el-row>

      <!-- 供应商近期成交明细 -->
      <div class="table-wrapper">
        <el-card shadow="hover" class="table-card">
          <template #header>
            <div class="card-header" style="display: flex; justify-content: space-between; align-items: center;">
              <span>同一物料多供应商成交明细</span>
              <div style="display: flex; gap: 15px;">
                <el-select v-model="filterSupplier" placeholder="所有供应商" clearable size="small" @change="filterTableData" style="width: 160px">
                  <el-option v-for="s in supplierOptions" :key="s" :label="s" :value="s" />
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
                  @change="filterTableData"
                  style="width: 200px;"
                />
              </div>
            </div>
          </template>
          <div class="table-inner">
            <el-table :data="filteredTableData" style="width: 100%" height="100%" stripe size="small" border>
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
              <el-table-column prop="price" label="单价(不含税)" align="right" width="120">
                <template #default="{ row }">
                  <span class="money-text">¥ {{ row.price.toLocaleString() }}</span>
                </template>
              </el-table-column>
              <el-table-column prop="tax_net_price" label="含税净价" align="right" width="120">
                <template #default="{ row }">
                  <span class="money-text" style="color: #ff4d4f; font-weight: bold;">¥ {{ row.tax_net_price.toLocaleString() }}</span>
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
import { onMounted, ref, computed, nextTick, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { RefreshRight, Money, ShoppingCart, User, TrendCharts } from '@element-plus/icons-vue'
import { getMaterialList, getMaterialAnalysis } from '../../api/material'

const materialList = ref([])
const selectedMaterial = ref('')
const loadingData = ref(false)
const loadingMaterials = ref(false)
const materialsLoaded = ref(false)

const selectedChartSuppliers = ref([])

const kpiCards = ref([
  { title: '历史采购总额', value: '0.00', prefix: '¥', type: 'primary', icon: 'Money' },
  { title: '总采购数量', value: '0', type: 'success', icon: 'ShoppingCart' },
  { title: '合作供应商数', value: '0', type: 'warning', icon: 'User', suffix: ' 家' },
  { title: '历史平均净价', value: '0.00', prefix: '¥', type: 'danger', icon: 'TrendCharts' }
])

const chartMode = ref('detail') // detail or average
const lineChartRef = ref(null)
const pieChartRef = ref(null)
let lineChart = null
let pieChart = null

const analysisData = ref({
  trend: [],
  supplier_share: [],
  history: [],
  all_suppliers: []
})

// Table filter state
const tableDateRange = ref([])
const filterSupplier = ref('')
const filteredTableData = ref([])

const dateShortcuts = [
  {
    text: '最近一周',
    value: () => {
      const end = new Date()
      const start = new Date()
      start.setTime(start.getTime() - 3600 * 1000 * 24 * 7)
      return [start, end]
    },
  },
  {
    text: '最近一个月',
    value: () => {
      const end = new Date()
      const start = new Date()
      start.setTime(start.getTime() - 3600 * 1000 * 24 * 30)
      return [start, end]
    },
  },
  {
    text: '最近三个月',
    value: () => {
      const end = new Date()
      const start = new Date()
      start.setTime(start.getTime() - 3600 * 1000 * 24 * 90)
      return [start, end]
    },
  }
]

const supplierOptions = computed(() => {
  return analysisData.value.all_suppliers || []
})

const getMaterialOptionLabel = (item) => {
  const parts = [item.material_name]
  if (item.material_model) {
    parts.push(item.material_model)
  }
  if (item.material_code) {
    parts.push(item.material_code)
  }
  return parts.filter(Boolean).join(' / ')
}

const fetchMaterials = async () => {
  loadingMaterials.value = true
  try {
    const res = await getMaterialList({ limit: 5000 })
    materialList.value = res.data || []
    materialsLoaded.value = true
  } catch (error) {
    ElMessage.error('获取物料列表失败')
  } finally {
    loadingMaterials.value = false
  }
}

const handleMaterialDropdownVisible = (visible) => {
  if (visible && !materialsLoaded.value) {
    fetchMaterials()
  }
}

const handleSelectMaterial = async () => {
  if (!selectedMaterial.value) return
  loadingData.value = true
  try {
    const res = await getMaterialAnalysis(selectedMaterial.value)
    const data = res.data || {}
    
    // Update KPI
    const kpi = data.kpi || {}
    kpiCards.value[0].value = (kpi.total_amount || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
    kpiCards.value[1].value = (kpi.total_qty || 0).toLocaleString('zh-CN', { maximumFractionDigits: 2 })
    kpiCards.value[2].value = kpi.supplier_count || 0
    kpiCards.value[3].value = (kpi.avg_price || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
    
    if (kpi.lowest_price) {
      kpiCards.value[3].desc = `最低价: ¥${kpi.lowest_price.toFixed(2)} (${kpi.lowest_supplier})`
    } else {
      kpiCards.value[3].desc = ''
    }

    analysisData.value = {
      trend: data.trend || [],
      supplier_share: data.supplier_share || [],
      history: data.history || [],
      all_suppliers: data.all_suppliers || []
    }
    
    // Set default chart suppliers to the top 1
    if (data.supplier_share && data.supplier_share.length > 0) {
      const top1 = data.supplier_share[0].name
      selectedChartSuppliers.value = top1 !== '其他' ? [top1] : []
    } else {
      selectedChartSuppliers.value = []
    }
    
    // Reset filters
    tableDateRange.value = []
    filterSupplier.value = ''
    filterTableData()
    
    await nextTick()
    renderLineChart()
    renderPieChart()
  } catch (error) {
    ElMessage.error('获取物料分析数据失败')
  } finally {
    loadingData.value = false
  }
}

const filterTableData = () => {
  let result = analysisData.value.history
  
  if (filterSupplier.value) {
    result = result.filter(row => row.supplier_name === filterSupplier.value)
  }
  
  if (tableDateRange.value && tableDateRange.value.length === 2) {
    const [start, end] = tableDateRange.value
    result = result.filter(row => row.date >= start && row.date <= end)
  }
  
  filteredTableData.value = result
}

const renderLineChart = () => {
  if (!lineChartRef.value) return
  if (!lineChart) lineChart = echarts.init(lineChartRef.value)
  
  let trendData = analysisData.value.trend
  if (selectedChartSuppliers.value && selectedChartSuppliers.value.length > 0) {
    trendData = trendData.filter(d => selectedChartSuppliers.value.includes(d.supplier))
  }

  if (trendData.length === 0) {
    lineChart.clear()
    lineChart.setOption({
      title: { text: '暂无符合条件的采购数据', left: 'center', top: 'center', textStyle: { color: '#ccc', fontSize: 14, fontWeight: 'normal' } }
    })
    return
  }

  const suppliers = Array.from(new Set(trendData.map(d => d.supplier)))
  let series = []
  let tooltipFormatter = null
  
  if (chartMode.value === 'average') {
    series = suppliers.map(sup => {
      const supData = trendData.filter(d => d.supplier === sup)
      const dateMap = {}
      supData.forEach(d => {
        if (!dateMap[d.date]) dateMap[d.date] = { sum: 0, count: 0 }
        dateMap[d.date].sum += d.price
        dateMap[d.date].count += 1
      })
      const avgData = Object.keys(dateMap).sort().map(date => [date, dateMap[date].sum / dateMap[date].count])
      
      return {
        name: sup,
        type: 'line',
        smooth: true,
        symbolSize: 6,
        data: avgData
      }
    })
    tooltipFormatter = function (params) {
      return `${params.seriesName}<br/>日期: ${params.value[0]}<br/>日均净价: ¥${params.value[1].toFixed(2)}`
    }
  } else {
    series = suppliers.map(sup => {
      return {
        name: sup,
        type: 'scatter',
        symbolSize: 10,
        data: trendData.filter(d => d.supplier === sup).map(d => [d.date, d.price, d.bill_no])
      }
    })
    tooltipFormatter = function (params) {
      const billNo = params.value[2] ? `<br/>订单号: ${params.value[2]}` : ''
      return `${params.seriesName}<br/>日期: ${params.value[0]}${billNo}<br/>净价: ¥${params.value[1]}`
    }
  }

  lineChart.setOption({
    title: { show: false },
    tooltip: { trigger: 'item', formatter: tooltipFormatter },
    legend: { type: 'scroll', data: suppliers, top: 0, padding: [5, 20] },
    grid: { left: '3%', right: '4%', bottom: '3%', top: '15%', containLabel: true },
    xAxis: {
      type: 'time',
      name: '订单日期',
      splitLine: { show: false },
      axisLabel: {
        formatter: function (value) {
          const date = new Date(value);
          return `${date.getMonth() + 1}月${date.getDate()}日`;
        }
      }
    },
    yAxis: { type: 'value', name: '采购含税净价 (元)' },
    series: series
  }, true)
}

const renderPieChart = () => {
  if (!pieChartRef.value) return
  if (!pieChart) pieChart = echarts.init(pieChartRef.value)
  
  const pieData = analysisData.value.supplier_share
  if (pieData.length === 0) {
    pieChart.clear()
    pieChart.setOption({
      title: { text: '暂无数据', left: 'center', top: 'center', textStyle: { color: '#ccc', fontSize: 14, fontWeight: 'normal' } }
    })
    return
  }
  
  pieChart.setOption({
    tooltip: {
      trigger: 'item',
      formatter: '{a} <br/>{b} : ¥{c} ({d}%)'
    },
    legend: {
      type: 'scroll',
      orient: 'vertical',
      right: 10,
      top: 20,
      bottom: 20
    },
    series: [
      {
        name: '采购份额',
        type: 'pie',
        radius: ['40%', '70%'],
        center: ['35%', '50%'],
        avoidLabelOverlap: false,
        itemStyle: {
          borderRadius: 5,
          borderColor: '#fff',
          borderWidth: 2
        },
        label: { show: false },
        emphasis: {
          label: { show: false }
        },
        labelLine: { show: false },
        data: pieData
      }
    ]
  }, true)
}

const handleResize = () => {
  lineChart?.resize()
  pieChart?.resize()
}

onMounted(() => {
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  lineChart?.dispose()
  pieChart?.dispose()
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
}

/* KPI Cards */
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

.kpi-prefix, .kpi-suffix {
  font-size: 14px;
  font-weight: normal;
  color: var(--el-text-color-regular);
}

.kpi-desc {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-top: 4px;
  height: 17px;
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

.kpi-card.primary .kpi-icon { color: var(--el-color-primary); }
.kpi-card.success .kpi-icon { color: var(--el-color-success); }
.kpi-card.warning .kpi-icon { color: var(--el-color-warning); }
.kpi-card.danger .kpi-icon { color: var(--el-color-danger); }

/* Charts */
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

/* Table */
.table-wrapper {
  flex: 1;
  min-height: 300px;
}

.table-card {
  height: 100%;
  display: flex;
  flex-direction: column;
  border: none;
  border-radius: 8px;
}

.table-card :deep(.el-card__body) {
  flex: 1;
  padding: 0;
  overflow: hidden;
}

.table-inner {
  height: 100%;
  padding: 16px;
}

.money-text {
  font-family: 'Courier New', Courier, monospace;
}
</style>
