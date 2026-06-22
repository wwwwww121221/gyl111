<template>
  <div class="analysis-container">
    <div class="page-header">
      <div class="header-left">
        <el-select
          v-model="selectedSupplierId"
          placeholder="请选择要分析的供应商 (支持名称、简称、编码搜索)"
          class="supplier-selector"
          @change="handleSupplierChange"
          filterable
          :filter-method="filterSupplierMethod"
          size="large"
        >
          <el-option
            v-for="item in filteredSupplierList"
            :key="item.id"
            :label="item.name"
            :value="item.id"
          >
            <span style="float: left">{{ item.name }}</span>
            <span v-if="item.grade" style="float: right; color: var(--el-text-color-secondary); font-size: 13px">
              {{ item.grade }}
            </span>
          </el-option>
        </el-select>
      </div>
      <el-button type="primary" :icon="RefreshRight" @click="refreshData" :disabled="!selectedSupplierId">刷新数据</el-button>
    </div>

    <!-- 空状态 -->
    <div v-if="!selectedSupplierId" class="empty-state">
      <el-empty description="请在上方选择一个供应商以查看其画像数据" />
    </div>

    <div v-else class="content-wrapper">
      <!-- 核心指标卡片 -->
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

      <!-- 图表区域 -->
      <div class="charts-wrapper">
        <el-row :gutter="20" class="charts-row">
          <el-col :span="24">
            <el-card shadow="hover" class="chart-card">
              <template #header>
                <div class="card-header" style="display: flex; justify-content: space-between; align-items: center;">
                  <span>近六个月物料含税净价走势</span>
                  <div style="display: flex; align-items: center; gap: 15px;">
                    <el-radio-group v-model="chartMode" size="small" @change="updateChart">
                      <el-radio-button label="detail">明细版</el-radio-button>
                      <el-radio-button label="average">曲线版</el-radio-button>
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

      <!-- 供应商近期成交明细 -->
      <div class="table-wrapper">
        <el-card shadow="hover" class="table-card">
          <template #header>
            <div class="card-header" style="display: flex; justify-content: space-between; align-items: center;">
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
                @change="filterTableData"
                style="width: 200px;"
              />
            </div>
          </template>
          <div class="table-inner">
            <el-table :data="filteredTableData" style="width: 100%" height="100%" stripe size="small" row-key="bill_no" :expand-row-keys="expandedRowKeys" @expand-change="handleExpand" border>
              <el-table-column type="expand">
                <template #default="props">
                  <div style="padding: 10px 20px;">
                    <el-table :data="props.row.items" size="small" border>
                      <el-table-column prop="material" label="物料名称" show-overflow-tooltip />
                      <el-table-column prop="quantity" label="采购数量" align="right" width="100" />
                      <el-table-column prop="price" label="单价(不含税)" align="right" width="120">
                        <template #default="scope">
                          <span class="money-text">¥ {{ scope.row.price.toLocaleString() }}</span>
                        </template>
                      </el-table-column>
                      <el-table-column prop="taxNetPrice" label="含税净价" align="right" width="120">
                        <template #default="scope">
                          <span class="money-text" style="color: #ff4d4f; font-weight: bold;">¥ {{ scope.row.taxNetPrice.toLocaleString() }}</span>
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
                  <span class="money-text" style="color: #ff4d4f; font-weight: bold;">¥ {{ scope.row.total_amount.toLocaleString() }}</span>
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
import { ref, onMounted, nextTick } from 'vue'
import { Money, TrendCharts, Trophy, RefreshRight, DocumentChecked, Timer, Connection } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import api from '../../api/index'
import { ElMessage } from 'element-plus'

const supplierList = ref([])
const filteredSupplierList = ref([])
const selectedSupplierId = ref('')

const filterSupplierMethod = (query) => {
  if (query) {
    const q = query.toLowerCase()
    filteredSupplierList.value = supplierList.value.filter(item => {
      return (item.name && item.name.toLowerCase().includes(q)) ||
             (item.short_name && item.short_name.toLowerCase().includes(q)) ||
             (item.code && item.code.toLowerCase().includes(q))
    })
  } else {
    filteredSupplierList.value = supplierList.value
  }
}

const lineChartRef = ref(null)
const radarChartRef = ref(null)

// 单家供应商核心数据
const coreStats = ref([
  { title: '历史采购总额', value: '0', prefix: '¥ ', icon: 'Money', bgColor: '#e6f4ff', color: '#1677ff' },
  { title: '采购订单数', value: '0', suffix: ' 单', icon: 'DocumentChecked', bgColor: '#f6ffed', color: '#52c41a' },
  { title: '供应物料种类', value: '0', suffix: ' 种', icon: 'TrendCharts', bgColor: '#fff0f6', color: '#eb2f96' },
  { title: '平均含税单价', value: '0.0', prefix: '¥ ', icon: 'Trophy', bgColor: '#fffbe6', color: '#faad14' },
  { title: '最大单笔采购量', value: '0', suffix: ' 件', icon: 'Timer', bgColor: '#f0f5ff', color: '#2f54eb' },
  { title: '最近交易距今', value: '0', suffix: ' 天', icon: 'Connection', bgColor: '#fcffe6', color: '#ad8b00' }
])

const tableData = ref([])
const filteredTableData = ref([])
const tableDateRange = ref([])
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
const expandedRowKeys = ref([])

// Chart state
const chartAllMaterials = ref([])
const chartSelectedMaterials = ref([])
const trendDataStore = ref([])
const chartMode = ref('detail') // detail or average

const fetchSuppliers = async () => {
  try {
    const res = await api.get('/supplier/list')
    // 移除状态过滤，展示所有供应商以供分析
    supplierList.value = res.data.list || []
    filteredSupplierList.value = supplierList.value
    if (supplierList.value.length > 0) {
      // 默认选中第一个
      selectedSupplierId.value = supplierList.value[0].id
      handleSupplierChange()
    }
  } catch (error) {
    console.error(error)
    ElMessage.error('获取供应商列表失败')
  }
}

const handleSupplierChange = () => {
  if (!selectedSupplierId.value) return
  refreshData()
}

const filterTableData = () => {
  if (!tableDateRange.value || tableDateRange.value.length !== 2) {
    filteredTableData.value = [...tableData.value]
    return
  }
  const [start, end] = tableDateRange.value
  filteredTableData.value = tableData.value.filter(row => {
    return row.date >= start && row.date <= end
  })
}

const handleExpand = (row, expandedRows) => {
  expandedRowKeys.value = expandedRows.map(r => r.bill_no)
}

const updateChart = () => {
  nextTick(() => {
    if (trendDataStore.value && trendDataStore.value.length > 0) {
      initCharts(trendDataStore.value, [])
    } else {
      initCharts([], [])
    }
  })
}

const refreshData = async () => {
  if (!selectedSupplierId.value) return
  
  try {
    const res = await api.get(`/supplier/${selectedSupplierId.value}/analysis`)
    const data = res.data
    
    // 更新核心指标
    coreStats.value[0].value = data.coreStats.totalAmount.toLocaleString()
    coreStats.value[1].value = data.coreStats.orderCount
    coreStats.value[2].value = data.coreStats.materialCount
    coreStats.value[3].value = data.coreStats.avgTaxNetPrice
    coreStats.value[4].value = data.coreStats.maxQty
    coreStats.value[5].value = data.coreStats.daysSinceLastOrder
    
    // 更新表格并设置默认半年过滤
    tableData.value = data.tableData
    const today = new Date()
    const lastSixMonths = new Date(today)
    lastSixMonths.setMonth(today.getMonth() - 6)
    
    const formatDate = (date) => {
      const y = date.getFullYear()
      const m = String(date.getMonth() + 1).padStart(2, '0')
      const d = String(date.getDate()).padStart(2, '0')
      return `${y}-${m}-${d}`
    }
    
    tableDateRange.value = [formatDate(lastSixMonths), formatDate(today)]
    filterTableData()
    
    // 更新图表状态
    const trendInfo = data.trend || { data: [], topMaterials: [], allMaterials: [] }
    chartAllMaterials.value = trendInfo.allMaterials || []
    chartSelectedMaterials.value = trendInfo.topMaterials || []
    trendDataStore.value = trendInfo.data || []
    
    updateChart()
    
  } catch (error) {
    console.error(error)
    ElMessage.error('获取供应商画像数据失败')
  }
}

const initCharts = (trendData, radarScores) => {
  if (lineChartRef.value) {
    const lineChart = echarts.init(lineChartRef.value)
    
    if (trendData.length === 0 || chartSelectedMaterials.value.length === 0) {
      lineChart.clear()
      lineChart.setOption({
        title: { text: '暂无历史采购数据或未选择物料', left: 'center', top: 'center', textStyle: { color: '#ccc', fontSize: 14, fontWeight: 'normal' } }
      })
    } else {
      // 过滤出选中的物料
      const filteredTrendData = trendData.filter(d => chartSelectedMaterials.value.includes(d.material))
      const materials = chartSelectedMaterials.value
      
      let series = []
      let tooltipFormatter = null
      
      if (chartMode.value === 'average') {
        series = materials.map(mat => {
          const matData = filteredTrendData.filter(d => d.material === mat)
          // 按日期聚合计算平均值
          const dateMap = {}
          matData.forEach(d => {
            if (!dateMap[d.date]) dateMap[d.date] = { sum: 0, count: 0 }
            dateMap[d.date].sum += d.price
            dateMap[d.date].count += 1
          })
          const avgData = Object.keys(dateMap).sort().map(date => [date, dateMap[date].sum / dateMap[date].count])
          
          return {
            name: mat,
            type: 'line', // 使用曲线图
            smooth: true,
            symbolSize: 6,
            data: avgData
          }
        })
        tooltipFormatter = function (params) {
          return `${params.seriesName}<br/>日期: ${params.value[0]}<br/>日均净价: ¥${params.value[1].toFixed(2)}`
        }
      } else {
        series = materials.map(mat => {
          return {
            name: mat,
            type: 'scatter', // 使用散点图展示不同日期的报价点
            symbolSize: 10,
            data: filteredTrendData.filter(d => d.material === mat).map(d => [d.date, d.price, d.bill_no])
          }
        })
        tooltipFormatter = function (params) {
          const billNo = params.value[2] ? `<br/>订单号: ${params.value[2]}` : ''
          return `${params.seriesName}<br/>日期: ${params.value[0]}${billNo}<br/>净价: ¥${params.value[1]}`
        }
      }

      lineChart.setOption({
        title: { show: false }, // 清除空数据提示
        tooltip: {
          trigger: 'item',
          formatter: tooltipFormatter
        },
        legend: {
          data: materials,
          top: 0
        },
        grid: {
          left: '3%',
          right: '4%',
          bottom: '3%',
          containLabel: true
        },
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
        yAxis: {
          type: 'value',
          name: '采购含税净价 (元)'
        },
        series: series
      }, true) // true 表示不合并旧的配置
    }
  }
}

const fetchAllSuppliersForAnalysis = async () => {
  try {
    const pageSize = 200
    let page = 1
    let total = 0
    let allSuppliers = []

    do {
      const res = await api.get('/supplier/list', {
        params: {
          page,
          page_size: pageSize
        }
      })
      const payload = res.data || {}
      const currentList = Array.isArray(payload.list) ? payload.list : []
      total = Number(payload.total || 0)
      allSuppliers = allSuppliers.concat(currentList)
      page += 1
    } while (allSuppliers.length < total)

    supplierList.value = allSuppliers
    filteredSupplierList.value = supplierList.value
    if (supplierList.value.length > 0) {
      selectedSupplierId.value = supplierList.value[0].id
      handleSupplierChange()
    }
  } catch (error) {
    console.error(error)
    ElMessage.error('获取供应商列表失败')
  }
}

onMounted(() => {
  fetchAllSuppliersForAnalysis()
  
  // 监听窗口大小变化以适配图表
  window.addEventListener('resize', () => {
    if (lineChartRef.value) echarts.getInstanceByDom(lineChartRef.value)?.resize()
  })
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
  overflow-y: auto; /* 允许整个内容区滚动，适应小屏幕 */
}

/* 核心指标区域 */
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
  margin-right: 0;
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
  overflow: visible;
  text-overflow: clip;
}

.stat-value {
  font-size: 20px;
  font-weight: bold;
  color: var(--text-primary);
  white-space: nowrap;
}

/* 图表区域 */
.charts-wrapper {
  flex-shrink: 0;
  height: 350px;
}

.charts-row {
  height: 100%;
}

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

/* 表格区域 */
.table-wrapper {
  flex: 1;
  min-height: 400px; /* 保证表格有足够的最小高度 */
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

.money-text {
  font-family: Monaco, Consolas, monospace;
  font-weight: 500;
  color: #f56c6c;
}
</style>
