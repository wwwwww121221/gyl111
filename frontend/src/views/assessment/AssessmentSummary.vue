<template>
  <div class="page-container">
    <div class="content-card">
      <div class="toolbar">
        <el-select v-model="selectedTaskId" placeholder="选择考核任务" style="width: 300px" @change="fetchSummary" clearable>
          <el-option v-for="t in allTasks" :key="t.id" :label="t.name" :value="t.id">
            <span>{{ t.name }}</span>
            <el-tag size="small" :type="typeTagMap[t.assessment_type]" style="margin-left:8px">{{ typeLabelMap[t.assessment_type] }}</el-tag>
          </el-option>
        </el-select>
      </div>

      <div v-if="!selectedTaskId" class="empty-state">
        <el-empty description="请选择一个考核任务查看汇总结果" />
      </div>

      <div v-else v-loading="loading">
        <div class="summary-header">
          <div class="summary-info">
            <span class="summary-name">{{ summary.name }}</span>
            <el-tag :type="typeTagMap[summary.assessment_type]">{{ typeLabelMap[summary.assessment_type] }}</el-tag>
            <el-tag :type="statusTagMap[summary.status]">{{ statusLabelMap[summary.status] }}</el-tag>
          </div>
          <div class="summary-meta">
            <span>打分时间：{{ summary.scoring_start }} ~ {{ summary.scoring_end }}</span>
          </div>
        </div>

        <div v-if="(summary.suppliers || []).length === 0" class="empty-state">
          <el-empty description="暂无考核数据" />
        </div>

        <template v-else>
          <div class="grade-summary">
            <div class="grade-card grade-a">
              <div class="grade-count">{{ gradeStats.A }}</div>
              <div class="grade-label">A级供应商</div>
            </div>
            <div class="grade-card grade-b">
              <div class="grade-count">{{ gradeStats.B }}</div>
              <div class="grade-label">B级供应商</div>
            </div>
            <div class="grade-card grade-c">
              <div class="grade-count">{{ gradeStats.C }}</div>
              <div class="grade-label">C级供应商</div>
            </div>
            <div class="grade-card grade-d">
              <div class="grade-count">{{ gradeStats.other }}</div>
              <div class="grade-label">一般供应商</div>
            </div>
          </div>

          <el-table :data="summary.suppliers || []" style="width: 100%; margin-top: 16px" border>
            <el-table-column type="index" label="排名" width="60" />
            <el-table-column prop="supplier_name" label="供应商" min-width="160" />
            <el-table-column prop="supplier_code" label="编码" width="100" />
            <el-table-column label="质量表现(30%)" width="120" align="center">
              <template #default="{ row }">
                {{ getDimensionScore(row, '质量表现') }}
              </template>
            </el-table-column>
            <el-table-column label="交付表现(30%)" width="120" align="center">
              <template #default="{ row }">
                {{ getDimensionScore(row, '交付表现') }}
              </template>
            </el-table-column>
            <el-table-column label="技术服务与配合(20%)" width="140" align="center">
              <template #default="{ row }">
                {{ getDimensionScore(row, '技术服务与配合') }}
              </template>
            </el-table-column>
            <el-table-column label="成本与合作稳定性(20%)" width="150" align="center">
              <template #default="{ row }">
                {{ getDimensionScore(row, '成本与合作稳定性') }}
              </template>
            </el-table-column>
            <el-table-column prop="total_score" label="总分" width="90" align="center" sortable>
              <template #default="{ row }">
                <span style="font-weight:700;font-size:15px">{{ row.total_score }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="grade" label="等级" width="80" align="center">
              <template #default="{ row }">
                <el-tag :type="row.grade === 'A级' ? 'success' : (row.grade === 'B级' ? 'warning' : (row.grade === 'C级' ? 'danger' : 'info'))" effect="dark">
                  {{ row.grade }}
                </el-tag>
              </template>
            </el-table-column>
          </el-table>

          <div v-if="expandedSupplier" class="supplier-detail-panel">
            <div class="panel-header">
              <span>{{ expandedSupplier.supplier_name }} - 各维度评分明细</span>
              <el-button size="small" text @click="expandedSupplier = null">收起</el-button>
            </div>
            <div v-for="dim in expandedSupplier.dimensions" :key="dim.dimension" class="dimension-block">
              <div class="dimension-header">
                <span class="dim-name">{{ dim.dimension }}</span>
                <span class="dim-weight">权重 {{ (dim.weight * 100).toFixed(0) }}%</span>
                <span class="dim-score">得分 {{ dim.earned }}/{{ dim.max }} → 加权 {{ dim.weighted_score }}</span>
              </div>
              <el-table :data="dim.items" size="small" border style="margin-top:8px">
                <el-table-column prop="indicator" label="考核指标" min-width="280" />
                <el-table-column prop="max_score" label="满分" width="70" align="center" />
                <el-table-column prop="score" label="得分" width="70" align="center">
                  <template #default="{ row }">
                    <span :style="{ color: row.score !== null && row.score !== undefined ? 'var(--primary-color)' : 'var(--text-muted)' }">
                      {{ row.score !== null && row.score !== undefined ? row.score : '未打' }}
                    </span>
                  </template>
                </el-table-column>
                <el-table-column prop="remark" label="备注" min-width="120" />
                <el-table-column prop="scored_by" label="打分人" width="90" />
                <el-table-column prop="scored_at" label="打分时间" width="160" />
              </el-table>
            </div>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import api from '../../api/index'

const allTasks = ref([])
const selectedTaskId = ref(null)
const loading = ref(false)
const summary = ref({})
const expandedSupplier = ref(null)

const typeLabelMap = { annual: '年度复评', quarterly: '季度考核', special: '专项考核' }
const typeTagMap = { annual: '', quarterly: 'warning', special: 'danger' }
const statusLabelMap = { scoring: '打分中', summary: '汇总中', completed: '已完成' }
const statusTagMap = { scoring: 'warning', summary: '', completed: 'success' }

const gradeStats = computed(() => {
  const suppliers = summary.value.suppliers || []
  return {
    A: suppliers.filter(s => s.grade === 'A级').length,
    B: suppliers.filter(s => s.grade === 'B级').length,
    C: suppliers.filter(s => s.grade === 'C级').length,
    other: suppliers.filter(s => !['A级', 'B级', 'C级'].includes(s.grade)).length,
  }
})

const fetchTaskList = async () => {
  try {
    const res = await api.get('/assessment/tasks')
    allTasks.value = res.data || []
  } catch (e) {
    console.error(e)
  }
}

const fetchSummary = async () => {
  if (!selectedTaskId.value) {
    summary.value = {}
    return
  }
  loading.value = true
  expandedSupplier.value = null
  try {
    const res = await api.get(`/assessment/tasks/${selectedTaskId.value}`)
    summary.value = res.data || {}
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

const getDimensionScore = (row, dimName) => {
  const dim = (row.dimensions || []).find(d => d.dimension === dimName)
  if (!dim) return '-'
  return `${dim.earned}/${dim.max}`
}

onMounted(() => {
  fetchTaskList()
})
</script>

<style scoped>
.page-container {
  padding: var(--space-6);
}

.content-card {
  background: var(--bg-primary);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  padding: var(--space-6);
}

.toolbar {
  display: flex;
  gap: var(--space-3);
  margin-bottom: var(--space-4);
}

.empty-state {
  padding: var(--space-8) 0;
}

.summary-header {
  background: var(--bg-secondary);
  border-radius: var(--radius-md);
  padding: var(--space-4);
  margin-bottom: var(--space-4);
}

.summary-info {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.summary-name {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
}

.summary-meta {
  margin-top: var(--space-2);
  font-size: 13px;
  color: var(--text-tertiary);
}

.grade-summary {
  display: flex;
  gap: var(--space-4);
  margin-top: var(--space-4);
}

.grade-card {
  flex: 1;
  text-align: center;
  padding: var(--space-4);
  border-radius: var(--radius-md);
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
}

.grade-count {
  font-size: 28px;
  font-weight: 700;
}

.grade-label {
  font-size: 13px;
  color: var(--text-tertiary);
  margin-top: var(--space-1);
}

.grade-a .grade-count { color: var(--success-color); }
.grade-b .grade-count { color: var(--warning-color); }
.grade-c .grade-count { color: var(--danger-color); }
.grade-d .grade-count { color: var(--text-tertiary); }

.supplier-detail-panel {
  margin-top: 16px;
  background: var(--bg-secondary);
  border-radius: var(--radius-md);
  padding: var(--space-4);
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-weight: 600;
  font-size: 15px;
  color: var(--text-primary);
  margin-bottom: var(--space-3);
}

.dimension-block {
  margin-bottom: var(--space-4);
}

.dimension-header {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  font-size: 14px;
}

.dim-name {
  font-weight: 600;
  color: var(--primary-color);
}

.dim-weight {
  color: var(--text-tertiary);
}

.dim-score {
  color: var(--text-secondary);
  font-weight: 500;
}
</style>
