<template>
  <div class="intelligent-compare-container">
    <div class="main-content" v-if="materialsData.length > 0 && activeMaterial">
      <!-- Left Panel: Material List -->
      <div class="material-list-panel">
        <el-card shadow="never" class="list-card" body-style="padding: 0;">
          <div class="card-header-search">
            <el-input placeholder="请输入物料名称" size="small" prefix-icon="Search" class="material-search" clearable></el-input>
          </div>
          <el-menu :default-active="activeIndex.toString()" class="material-menu" @select="handleMaterialSelect">
            <el-menu-item v-for="(item, index) in materialsData" :key="item.reqId" :index="index.toString()">
              <span class="text-truncate" :title="item.materialName">{{ item.materialName }}</span>
            </el-menu-item>
          </el-menu>
        </el-card>
      </div>

      <!-- Right Panel: Wide Display Area -->
      <div class="right-panel">
        <el-card shadow="never" class="result-card mb-3" body-style="padding: 16px 20px;">
          
          <div class="page-header">
            <h2 class="page-main-title">智能比价看板 - {{ activeMaterial.materialName }}</h2>
          </div>
          <el-divider class="header-divider" />

          <!-- 1. 历史价格 (放在最前) -->
          <div class="section-header">
            <h3 class="section-title">历史价格</h3>
          </div>
          <el-table :data="activeMaterial.historyStats" style="width: 100%" class="custom-table mb-4" v-loading="historyLoading">
            <el-table-column type="index" label="#" width="50" align="center" />
            <el-table-column prop="supplier_name" label="供应商名称" min-width="180" />
            <el-table-column label="含税单价" width="140" align="center">
              <template #default="scope">
                <span class="table-text-value">{{ scope.row.latest_price ? scope.row.latest_price.toFixed(2) : '-' }}</span>
              </template>
            </el-table-column>
            <el-table-column label="不含税单价" width="140" align="center">
              <template #default="scope">
                <span class="table-text-value">{{ scope.row.latest_price ? (scope.row.latest_price / 1.13).toFixed(2) : '-' }}</span>
              </template>
            </el-table-column>
            <el-table-column label="价格日期" min-width="160" align="center">
              <template #default="scope">
                <span class="table-text-value">{{ scope.row.latest_date || '-' }}</span>
              </template>
            </el-table-column>
          </el-table>

          <!-- 2. 本次报价明细 -->
          <div class="section-header mt-4">
            <h3 class="section-title">本次报价明细</h3>
          </div>
          <el-table :data="currentComparison" style="width: 100%" class="custom-table mb-4">
            <el-table-column type="index" label="#" width="50" align="center" />
            <el-table-column prop="name" label="供应商名称" min-width="240">
              <template #default="scope">
                <div class="supplier-name-cell">
                  <span>{{ scope.row.name }}</span>
                  <el-tag
                    v-for="tag in getSupplierIdentityTags(scope.row)"
                    :key="tag.label"
                    :type="tag.type"
                    size="small"
                    effect="dark"
                  >
                    {{ tag.label }}
                  </el-tag>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="含税单价" width="140" align="center">
              <template #default="scope">
                <span class="table-text-value price-highlight">{{ scope.row.tax_net_price ? scope.row.tax_net_price.toFixed(2) : '-' }}</span>
              </template>
            </el-table-column>
            <el-table-column label="不含税单价" width="140" align="center">
              <template #default="scope">
                <span class="table-text-value">{{ scope.row.price ? scope.row.price.toFixed(2) : '-' }}</span>
              </template>
            </el-table-column>
            <el-table-column label="报价优势" min-width="160">
              <template #default="scope">
                <div v-if="scope.row.tax_net_price > 0" class="advantage-cell">
                  <span v-if="scope.row.is_lowest" class="text-success">当前最低价</span>
                  <span v-else-if="scope.row.diff_percent > 0" class="text-danger">
                    价格偏高，比均价高 {{ scope.row.diff_percent.toFixed(2) }}%
                  </span>
                  <span v-else class="text-muted">比均价低 {{ Math.abs(scope.row.diff_percent).toFixed(2) }}%</span>
                </div>
                <span v-else class="text-muted">-</span>
              </template>
            </el-table-column>
            <el-table-column label="评级" width="120" align="center">
              <template #default="scope">
                <el-rate :model-value="getGradeStars(scope.row.grade)" disabled text-color="#ff9900" disabled-void-color="#c6d1de"></el-rate>
              </template>
            </el-table-column>
          </el-table>

          <!-- 3. 智能分析结论 (Purple Gradient Box) -->
          <div class="ai-analysis-box" v-loading="activeMaterial.loadingAnalysis">
            <div class="ai-box-header">
              <el-icon class="ai-icon"><Opportunity /></el-icon>
              <span>智能分析结论</span>
              <el-button type="primary" link size="small" class="refresh-btn" @click="() => generateAnalysis(false)" :disabled="activeMaterial.suppliers.length < 2">
                <el-icon><Refresh /></el-icon> 重新分析
              </el-button>
            </div>
            <div class="ai-box-content">
              <div v-if="activeMaterial.aiAnalysisResult" class="markdown-body" v-html="formattedAnalysis"></div>
              <div v-else class="empty-ai-text">请确保上方有至少两家供应商含税报价，系统将自动进行智能比价分析。</div>
            </div>
          </div>

          <!-- 4. 谈判话术 -->
          <div class="wechat-box mt-4" v-if="activeMaterial?.aiAnalysisResult">
            <div class="wechat-box-header">
              <el-icon><ChatDotRound /></el-icon> 一键生成谈判话术 (微信)
            </div>
            <div class="wechat-box-actions">
              <el-select v-model="wechatTargetSupplier" placeholder="选择目标供应商" size="small" style="width: 150px; margin-right: 10px;">
                <el-option v-for="s in activeMaterial.suppliers" :key="s.code" :label="s.name" :value="s.name"></el-option>
              </el-select>
              <el-input-number v-model="wechatTargetPrice" size="small" placeholder="期望压价到" style="width: 130px; margin-right: 10px;" :controls="false"></el-input-number>
              <el-button type="primary" size="small" @click="generateWechatScript" :loading="wechatLoading" :disabled="!wechatTargetSupplier || !wechatTargetPrice">生成</el-button>
            </div>
            <div class="wechat-box-content" v-loading="wechatLoading">
              <el-input v-if="wechatScriptResult" type="textarea" :rows="3" v-model="wechatScriptResult" readonly></el-input>
            </div>
          </div>

          <el-card shadow="never" class="allocation-card mt-4" v-if="activeMaterial">
            <template #header>
              <div class="allocation-card-header">
                <span>采购份额分配策略</span>
                <span class="allocation-card-subtitle">支持一键策略与手工微调，分配总和需为 100%</span>
              </div>
            </template>

            <div class="allocation-strategy-toolbar">
              <el-button @click="applyStrategy('common')">全额给常用 (100%)</el-button>

              <div class="pressure-strategy-group">
                <el-button type="warning" @click="applyStrategy('pressure')">价格压迫策略</el-button>
                <div class="pressure-ratio-group">
                  <span class="pressure-ratio-label">常用占%</span>
                  <el-input-number
                    v-model="pressureCommonRatio"
                    size="small"
                    :min="0"
                    :max="100"
                    :controls="false"
                  />
                  <span class="pressure-ratio-label">最低价占%</span>
                  <el-input-number
                    v-model="pressureLowestRatio"
                    size="small"
                    :min="0"
                    :max="100"
                    :controls="false"
                  />
                </div>
              </div>

              <el-button type="success" @click="applyStrategy('lowest')">价低者得 (100%)</el-button>
            </div>

            <el-table :data="currentComparison" class="custom-table allocation-table" style="width: 100%">
              <el-table-column prop="name" label="供应商名称" min-width="180" />
              <el-table-column label="业务标签" min-width="220">
                <template #default="scope">
                  <div class="supplier-tags">
                    <el-tag
                      v-for="tag in getSupplierIdentityTags(scope.row)"
                      :key="tag.label"
                      :type="tag.type"
                      size="small"
                      effect="dark"
                    >
                      {{ tag.label }}
                    </el-tag>
                    <span v-if="getSupplierIdentityTags(scope.row).length === 0" class="text-muted">-</span>
                  </div>
                </template>
              </el-table-column>
              <el-table-column label="含税单价" width="140" align="center">
                <template #default="scope">
                  <span class="table-text-value">{{ scope.row.tax_net_price ? scope.row.tax_net_price.toFixed(2) : '-' }}</span>
                </template>
              </el-table-column>
              <el-table-column label="不含税单价" width="140" align="center">
                <template #default="scope">
                  <span class="table-text-value">{{ scope.row.price ? scope.row.price.toFixed(2) : '-' }}</span>
                </template>
              </el-table-column>
              <el-table-column label="分配比例 (%)" width="180" align="center">
                <template #default="scope">
                  <el-input-number
                    v-model="allocations[getAllocationKey(scope.row)]"
                    size="small"
                    :min="0"
                    :max="100"
                    :precision="0"
                    :step="5"
                    controls-position="right"
                  />
                </template>
              </el-table-column>
            </el-table>

            <div class="allocation-footer">
              <div class="allocation-summary">
                <span class="allocation-sum-text">当前分配总和：{{ allocationSum }} %</span>
                <span v-if="allocationSum !== 100" class="allocation-warning">分配比例总和必须等于 100%</span>
              </div>
              <el-button type="primary" :disabled="!canSubmit" :loading="isSubmittingAllocation" @click="submitAllocation">确认并生成合同</el-button>
            </div>
          </el-card>
          
        </el-card>
      </div>
    </div>
    
    <div v-else class="empty-state">
      <el-empty description="暂无比价物料，请从询价池选择" :image-size="200">
        <el-button type="primary" @click="router.push('/inquiries/requests')">前往询价池</el-button>
      </el-empty>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { DataAnalysis, MagicStick, Histogram, TrendCharts, Opportunity, Menu, Goods, ChatDotRound, Check, Share, Printer, User, Search, Refresh } from '@element-plus/icons-vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '../../api/index'
import { marked } from 'marked'

const route = useRoute()
const router = useRouter()

// State
const materialsData = ref([])
const activeIndex = ref(0)
const historicalSuppliers = ref([])
const otherSuppliers = ref([])
const historyLoading = ref(false)
const pressureCommonRatio = ref(80)
const pressureLowestRatio = ref(20)
const allocations = ref({})
const isSubmittingAllocation = ref(false)

const wechatTargetSupplier = ref('')
const wechatTargetPrice = ref(undefined)
const wechatLoading = ref(false)
const wechatScriptResult = ref('')

const activeMaterial = computed(() => materialsData.value[activeIndex.value] || null)
const allocationSum = computed(() => {
  return currentComparison.value.reduce((sum, supplier) => {
    const key = getAllocationKey(supplier)
    return sum + Number(allocations.value[key] || 0)
  }, 0)
})
const canSubmit = computed(() => allocationSum.value === 100)

let syncingPressureRatios = false

watch(pressureCommonRatio, (value) => {
  if (syncingPressureRatios) return
  syncingPressureRatios = true
  pressureLowestRatio.value = Math.max(0, 100 - Number(value || 0))
  syncingPressureRatios = false
})

watch(pressureLowestRatio, (value) => {
  if (syncingPressureRatios) return
  syncingPressureRatios = true
  pressureCommonRatio.value = Math.max(0, 100 - Number(value || 0))
  syncingPressureRatios = false
})

// Init from sessionStorage
onMounted(async () => {
  try {
    const allSuppRes = await api.get('/supplier/list')
    otherSuppliers.value = allSuppRes.data || []
  } catch(e) {
    console.error('Failed to load all suppliers', e)
  }

  if (route.query.taskId) {
    try {
      const taskRes = await api.get(`/inquiry/tasks/${route.query.taskId}/details`)
      const items = taskRes.data.items || []
      const links = taskRes.data.links || []
      
      const supplierCodes = links.map(link => link.supplier_code)
      materialsData.value = items.map(item => {
        const initSuppliers = links.map(link => {
          const round = link.current_round || 1;
          const quotesRound = link.quotes ? (link.quotes[round] || link.quotes['1'] || []) : [];
          const quote = quotesRound.find(q => q.item_id === item.id);
          const price = quote ? quote.price : undefined;
          const tax_net_price = price ? Number((price * 1.13).toFixed(2)) : undefined;
          return {
            link_id: link.link_id,
            code: link.supplier_code,
            name: link.supplier_name,
            grade: link.supplier_grade,
            tax_rate: 13,
            tax_net_price: tax_net_price,
            price: price,
            qty: quote ? quote.qty : (item.qty || 1)
          };
        });

        return {
          reqId: item.id,
          materialCode: item.material_code,
          materialName: item.material_name,
          qty: item.qty,
          billNo: taskRes.data.title,
          billType: taskRes.data.type === 'auto' ? '自动询价' : '手动询价',
          projectNumber: '',
          selectedSupplierCodes: [...supplierCodes],
          suppliers: initSuppliers,
          historyStats: [],
          aiAnalysisResult: '',
          loadingAnalysis: false
        };
      })
      
      if (materialsData.value.length > 0) {
        await loadSuppliersForMaterial(materialsData.value[0].materialCode)
        await fetchHistoryStats() // fetch history for the initial suppliers
        if (!activeMaterial.value.aiAnalysisResult) {
          generateAnalysis(true)
        }
      }
    } catch (e) {
      console.error('Failed to load task details', e)
      ElMessage.error('加载询价任务失败')
    }
  } else if (route.query.source === 'auto') {
    const stored = sessionStorage.getItem('compare_materials')
    if (stored) {
      try {
        const parsed = JSON.parse(stored)
        materialsData.value = parsed.map(item => ({
          ...item,
          selectedSupplierCodes: [],
          suppliers: [],
          historyStats: [],
          aiAnalysisResult: '',
          loadingAnalysis: false
        }))
        
        if (materialsData.value.length > 0) {
          loadSuppliersForMaterial(materialsData.value[0].materialCode)
        }
      } catch (e) {
        console.error('Failed to parse compare data', e)
      }
    }
  } else {
    // 直接通过侧边栏点击进入，清空数据展示空状态
    materialsData.value = []
  }
})

const handleMaterialSelect = async (indexStr) => {
  activeIndex.value = parseInt(indexStr)
  if (activeMaterial.value) {
    await loadSuppliersForMaterial(activeMaterial.value.materialCode)
    await fetchHistoryStats()
    if (!activeMaterial.value.aiAnalysisResult) {
      generateAnalysis(true)
    }
  }
}

const loadSuppliersForMaterial = async (code) => {
  try {
    const res = await api.get(`/compare/suppliers/${code}`)
    historicalSuppliers.value = res.data || []
  } catch (e) {
    console.error(e)
    ElMessage.error('加载物料历史供应商失败')
  }
}

const calculatePrice = (supplier) => {
  if (supplier.tax_net_price != null && supplier.tax_rate != null) {
    supplier.price = Number((supplier.tax_net_price / (1 + supplier.tax_rate / 100)).toFixed(2))
  }
}

const getGradeStars = (grade) => {
  if (grade === 'A级' || grade === 'core') return 5;
  if (grade === 'B级') return 4;
  if (grade === 'C级') return 3;
  return 2; // 一般
}

const getAllocationKey = (supplier) => {
  return String(supplier?.link_id ?? supplier?.code ?? supplier?.name ?? '')
}

const initializeAllocations = () => {
  const nextAllocations = {}
  const suppliers = activeMaterial.value?.suppliers || []
  suppliers.forEach((supplier) => {
    const key = getAllocationKey(supplier)
    if (key) {
      nextAllocations[key] = 0
    }
  })
  allocations.value = nextAllocations
}

const getSupplierIdentityTags = (supplier) => {
  const tags = []
  if (supplier?.is_common) {
    tags.push({ label: '常用供应商', type: 'primary' })
  }
  if (supplier?.is_lowest) {
    tags.push({ label: '最低价', type: 'success' })
  }
  if (supplier?.is_highest) {
    tags.push({ label: '最高价', type: 'danger' })
  }
  return tags
}

watch(
  () => ({
    reqId: activeMaterial.value?.reqId,
    supplierKeys: (activeMaterial.value?.suppliers || []).map(getAllocationKey).join('|')
  }),
  () => {
    initializeAllocations()
  },
  { immediate: true }
)

const fetchHistoryStats = async () => {
  if (!activeMaterial.value) return
  historyLoading.value = true
  try {
    // Combine currently selected suppliers and historical suppliers to get full history
    const allSuppliersMap = new Map()
    activeMaterial.value.suppliers.forEach(s => {
      if (s.code) allSuppliersMap.set(s.code, { code: s.code, name: s.name })
    })
    historicalSuppliers.value.forEach(s => {
      if (s.code) allSuppliersMap.set(s.code, { code: s.code, name: s.name })
    })
    const mergedSuppliers = Array.from(allSuppliersMap.values())

    const payload = {
      material_code: activeMaterial.value.materialCode,
      material_name: activeMaterial.value.materialName,
      suppliers: mergedSuppliers.length > 0 ? mergedSuppliers : activeMaterial.value.suppliers
    }
    const res = await api.post('/compare/history', payload)
    // Filter out suppliers that have no history at all to keep the table clean
    activeMaterial.value.historyStats = res.data.filter(item => item.latest_price > 0)
  } catch (error) {
    console.error(error)
    ElMessage.error('获取历史价格失败')
  } finally {
    historyLoading.value = false
  }
}

// Compute current comparison logic
const currentComparison = computed(() => {
  if (!activeMaterial.value) return []
  const suppliersList = activeMaterial.value.suppliers || []
  const rankedHistoricalSuppliers = historicalSuppliers.value || []
  const commonSupplier = rankedHistoricalSuppliers.length > 0 ? rankedHistoricalSuppliers[0] : null
  const commonSupplierCode = commonSupplier?.code || null
  const commonSupplierName = commonSupplier?.name || commonSupplier?.supplier_name || null
  
  const validSuppliers = suppliersList.filter(s => s.tax_net_price > 0)
  if (validSuppliers.length === 0) {
    return suppliersList.map(s => ({
      ...s,
      diff_percent: 0,
      is_lowest: false,
      is_highest: false,
      is_common: Boolean(
        (commonSupplierCode && s.code === commonSupplierCode) ||
        (commonSupplierName && s.name === commonSupplierName)
      )
    }))
  }
  
  const sum = validSuppliers.reduce((acc, s) => acc + s.tax_net_price, 0)
  const avg = sum / validSuppliers.length
  const minPrice = Math.min(...validSuppliers.map(s => s.tax_net_price))
  const maxPrice = Math.max(...validSuppliers.map(s => s.tax_net_price))
  
  return suppliersList.map(s => {
    const isCommon = Boolean(
      (commonSupplierCode && s.code === commonSupplierCode) ||
      (commonSupplierName && s.name === commonSupplierName)
    )
    if (!s.tax_net_price) {
      return {
        ...s,
        diff_percent: 0,
        is_lowest: false,
        is_highest: false,
        is_common: isCommon
      }
    }
    const diff_percent = ((s.tax_net_price - avg) / avg) * 100
    return {
      ...s,
      diff_percent,
      is_lowest: s.tax_net_price === minPrice,
      is_highest: s.tax_net_price === maxPrice,
      is_common: isCommon
    }
  })
})

const applyStrategy = (type) => {
  if (!currentComparison.value.length) {
    ElMessage.warning('当前暂无可分配的供应商')
    return
  }

  initializeAllocations()

  const commonSupplier = currentComparison.value.find(item => item.is_common)
  const lowestSupplier = currentComparison.value.find(item => item.is_lowest)

  const setAllocation = (supplier, ratio) => {
    if (!supplier) return
    const key = getAllocationKey(supplier)
    if (!key) return
    allocations.value[key] = Number(ratio || 0)
  }

  if (type === 'common') {
    if (!commonSupplier) {
      ElMessage.warning('未识别到常用供应商')
      return
    }
    setAllocation(commonSupplier, 100)
    return
  }

  if (type === 'lowest') {
    if (!lowestSupplier) {
      ElMessage.warning('未识别到最低价供应商')
      return
    }
    setAllocation(lowestSupplier, 100)
    return
  }

  if (type === 'pressure') {
    if (!commonSupplier && !lowestSupplier) {
      ElMessage.warning('未识别到常用供应商或最低价供应商')
      return
    }

    const commonKey = commonSupplier ? getAllocationKey(commonSupplier) : null
    const lowestKey = lowestSupplier ? getAllocationKey(lowestSupplier) : null

    if (commonKey && lowestKey && commonKey === lowestKey) {
      setAllocation(commonSupplier, 100)
      return
    }

    if (commonSupplier && lowestSupplier) {
      setAllocation(commonSupplier, pressureCommonRatio.value)
      setAllocation(lowestSupplier, pressureLowestRatio.value)
      return
    }

    setAllocation(commonSupplier || lowestSupplier, 100)
  }
}

const submitAllocation = async () => {
  if (!route.query.taskId) {
    ElMessage.error('当前缺少询价任务ID，无法提交定标')
    return
  }
  if (!canSubmit.value) {
    ElMessage.warning('分配比例总和必须等于 100%')
    return
  }

  const selectedSuppliers = currentComparison.value
    .map((supplier) => ({
      supplier,
      ratio: Number(allocations.value[getAllocationKey(supplier)] || 0)
    }))
    .filter(item => item.ratio > 0)

  if (selectedSuppliers.length === 0) {
    ElMessage.warning('请至少为一个供应商分配份额')
    return
  }

  const missingLinkSupplier = selectedSuppliers.find(item => !item.supplier.link_id)
  if (missingLinkSupplier) {
    ElMessage.error(`供应商 ${missingLinkSupplier.supplier.name} 缺少关联ID，无法提交定标`)
    return
  }

  const payload = {
    allocations: selectedSuppliers.map(item => ({
      link_id: item.supplier.link_id,
      allocated_ratio: item.ratio
    }))
  }

  isSubmittingAllocation.value = true
  try {
    await api.post(`/inquiry/tasks/${route.query.taskId}/close`, payload)
    ElMessage.success('定标成功，合同生成流程已触发')
    router.push({ name: 'InquiryTasks' })
  } catch (error) {
    console.error(error)
  } finally {
    isSubmittingAllocation.value = false
  }
}

// Generate Analysis
const generateAnalysis = async (isAuto = false) => {
  if (!activeMaterial.value) return
  const validSuppliers = activeMaterial.value.suppliers.filter(s => s.tax_net_price > 0)
  if (validSuppliers.length < 2) {
    if (!isAuto) {
      ElMessage.warning('至少需要填写两家供应商的报价才能进行比价分析')
    }
    return
  }
  
  activeMaterial.value.loadingAnalysis = true
  activeMaterial.value.aiAnalysisResult = ''
  
  try {
    const payload = {
      material_code: activeMaterial.value.materialCode,
      material_name: activeMaterial.value.materialName,
      suppliers: validSuppliers
    }
    const res = await api.post('/compare/ai-analysis', payload)
    activeMaterial.value.aiAnalysisResult = res.data.analysis
  } catch (error) {
    console.error(error)
    ElMessage.error('生成AI分析失败')
  } finally {
    activeMaterial.value.loadingAnalysis = false
  }
}

const formattedAnalysis = computed(() => {
  return activeMaterial.value?.aiAnalysisResult ? marked(activeMaterial.value.aiAnalysisResult) : ''
})

const generateWechatScript = async () => {
  if (!activeMaterial.value || !activeMaterial.value.aiAnalysisResult) return
  wechatLoading.value = true
  wechatScriptResult.value = ''
  try {
    const payload = {
      material_name: activeMaterial.value.materialName,
      target_supplier: wechatTargetSupplier.value,
      target_price: wechatTargetPrice.value,
      analysis_text: activeMaterial.value.aiAnalysisResult
    }
    const res = await api.post('/compare/wechat-script', payload)
    wechatScriptResult.value = res.data.script
  } catch (error) {
    console.error(error)
    ElMessage.error('生成微信话术失败')
  } finally {
    wechatLoading.value = false
  }
}
</script>

<style scoped>
.text-success { color: #67c23a; }
.text-danger { color: #f56c6c; }
.text-muted { color: #909399; }
.text-small { font-size: 12px; }
.font-weight-bold { font-weight: bold; }

.intelligent-compare-container {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding-bottom: 20px;
}

/* ====== Screenshot-based Custom Styles ====== */

.header-card {
  border-radius: 4px;
  margin-bottom: 10px;
  background-color: #fff;
}

.page-main-title {
  font-size: 16px;
  font-weight: bold;
  color: #303133;
  margin: 0;
}

.header-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-divider {
  margin: 12px 0;
}

.basic-info-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px 24px;
  margin-bottom: 20px;
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.info-label {
  font-size: 12px;
  color: #909399;
}

.info-value {
  font-size: 13px;
  color: #303133;
}

.text-bold {
  font-weight: bold;
}

.user-tag {
  color: #409EFF;
  background-color: #ecf5ff;
  border-color: #d9ecff;
}

.fake-tabs {
  display: flex;
  border-bottom: 1px solid #ebeef5;
  margin-top: 10px;
}

.tab-item {
  padding: 10px 30px;
  font-size: 14px;
  color: #606266;
  cursor: pointer;
  position: relative;
}

.tab-item.active {
  color: #409EFF;
  font-weight: bold;
  background-color: #f0f7ff;
  border-top-left-radius: 4px;
  border-top-right-radius: 4px;
}

.tab-item.active::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: 0;
  width: 100%;
  height: 2px;
  background-color: #409EFF;
}

.card-header-search {
  padding: 10px;
  border-bottom: 1px solid #ebeef5;
}

.section-title-wrapper {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.section-title {
  font-size: 15px;
  font-weight: bold;
  color: #303133;
  margin: 0;
}

.section-actions {
  display: flex;
  align-items: center;
}

.custom-table {
  border: 1px solid #ebeef5;
  border-bottom: none;
}

.custom-table th.el-table__cell {
  background-color: #f8f9fa !important;
  color: #606266;
  font-weight: normal;
}

.table-text-value {
  font-family: 'Courier New', Courier, monospace;
  font-size: 13px;
  color: #303133;
}

.advantage-cell {
  display: flex;
  align-items: center;
  font-size: 12px;
}

.supplier-name-cell {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.supplier-tags {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.allocation-card {
  border-radius: 8px;
}

.allocation-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  font-weight: bold;
  color: #303133;
}

.allocation-card-subtitle {
  font-size: 12px;
  font-weight: normal;
  color: #909399;
}

.allocation-strategy-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 16px;
}

.pressure-strategy-group {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  padding: 10px 12px;
  border: 1px solid #f3d19e;
  background: #fff8eb;
  border-radius: 8px;
}

.pressure-ratio-group {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.pressure-ratio-label {
  font-size: 12px;
  color: #606266;
  white-space: nowrap;
}

.allocation-table {
  margin-bottom: 16px;
}

.allocation-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.allocation-summary {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.allocation-sum-text {
  font-size: 14px;
  color: #303133;
  font-weight: 500;
}

.allocation-warning {
  font-size: 13px;
  color: #f56c6c;
}

/* AI Box Custom Styling */
.ai-analysis-box {
  background: linear-gradient(135deg, #fdf6f7 0%, #f4f6fd 100%);
  border: 1px solid #e9d5eb;
  border-radius: 8px;
  padding: 16px;
  margin-top: 20px;
  box-shadow: 0 2px 10px rgba(0,0,0,0.02);
}

.ai-box-header {
  display: flex;
  align-items: center;
  margin-bottom: 12px;
  font-size: 15px;
  font-weight: bold;
  color: #8c3a99;
}

.ai-icon {
  font-size: 18px;
  margin-right: 8px;
}

.refresh-btn {
  margin-left: auto;
}

.ai-box-content {
  font-size: 13px;
  color: #303133;
  line-height: 1.6;
}

.empty-ai-text {
  color: #909399;
  font-style: italic;
}

/* Wechat Box Custom Styling */
.wechat-box {
  background-color: #f6ffed;
  border: 1px solid #c2e7b0;
  border-radius: 8px;
  padding: 16px;
}

.wechat-box-header {
  font-size: 14px;
  font-weight: bold;
  color: #67c23a;
  margin-bottom: 12px;
  display: flex;
  align-items: center;
}

.wechat-box-header .el-icon {
  margin-right: 6px;
}

.wechat-box-actions {
  display: flex;
  align-items: center;
  margin-bottom: 12px;
}

/* Rest of general styles */

.main-content {
  display: flex;
  gap: 12px;
  flex: 1;
  /* Remove min-height: 0 to allow natural expansion */
  flex-wrap: wrap;
}

.material-list-panel {
  width: 160px;
  flex-shrink: 0;
}

.list-card {
  border-radius: 6px;
}

.material-menu {
  border-right: none;
}

.text-truncate {
  display: inline-block;
  max-width: 90px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  vertical-align: middle;
  font-size: 13px;
}

.left-panel {
  width: 320px;
  flex-shrink: 0;
}

.right-panel {
  flex: 1;
  min-width: 400px;
  display: flex;
  flex-direction: column;
}

.input-card {
  border-radius: 6px;
}

.suppliers-list {
  padding-right: 4px;
}

.supplier-item {
  background-color: #f8f9fa;
  border-radius: 4px;
  padding: 8px 10px;
  margin-bottom: 8px;
  border: 1px solid #ebeef5;
}

.supplier-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  font-size: 13px;
}

.action-footer {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid #ebeef5;
}

.w-100 {
  width: 100%;
}

.result-card {
  border-radius: 6px;
  margin-bottom: 12px;
}

.ai-card {
  display: flex;
  flex-direction: column;
}

.ai-content {
  padding: 12px;
  background-color: #f8f9fa;
  border-radius: 4px;
  min-height: 150px;
}

.price-text {
  font-family: 'Courier New', Courier, monospace;
  font-weight: bold;
  font-size: 13px;
}

.date-text {
  font-size: 11px;
  color: #909399;
}

.text-success { color: #67c23a; }
.text-danger { color: #f56c6c; }
.text-muted { color: #909399; }
.text-small { font-size: 11px; }
.mr-1 { margin-right: 6px; }
.mb-3 { margin-bottom: 12px; }

.empty-state {
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 40px;
  background: white;
  border-radius: 6px;
}

:deep(.markdown-body) {
  font-size: 13px;
  line-height: 1.5;
}
:deep(.markdown-body h1), :deep(.markdown-body h2), :deep(.markdown-body h3) {
  margin-top: 12px;
  margin-bottom: 6px;
  font-size: 14px;
}
:deep(.markdown-body p) {
  margin-bottom: 8px;
}
</style>
