<template>
  <div class="page-container">
    <div class="content-card">
      <div class="page-title">我的打分任务</div>
      <div class="dept-hint">
        <el-tag type="info" effect="plain">当前部门：{{ userDepartment }}</el-tag>
      </div>

      <div v-if="myTasks.length === 0 && !loading" class="empty-state">
        <el-empty description="暂无待打分的考核任务" />
      </div>

      <div v-for="task in myTasks" :key="task.task_id" class="task-card">
        <div class="task-card-header">
          <div class="task-info">
            <span class="task-name">{{ task.task_name }}</span>
            <el-tag :type="typeTagMap[task.assessment_type]" size="small">{{ typeLabelMap[task.assessment_type] }}</el-tag>
          </div>
          <div class="task-meta">
            <span>打分时间：{{ task.scoring_start }} ~ {{ task.scoring_end }}</span>
            <el-progress :percentage="task.progress" :stroke-width="8" style="width: 120px; margin-left: 16px" />
          </div>
        </div>
        <el-button type="primary" size="small" @click="openScoring(task)" style="margin-top: 12px">
          {{ task.progress >= 100 ? '查看/修改打分' : '开始打分' }}
        </el-button>
      </div>
    </div>

    <el-dialog v-model="scoringDialogVisible" :title="`打分 - ${currentTaskName}`" width="90%" top="4vh" draggable overflow destroy-on-close>
      <div v-loading="scoringLoading">
        <div v-if="!scoringData.can_score" class="scoring-closed-hint">
          <el-alert title="当前不在打分时间范围内，仅可查看" type="warning" :closable="false" show-icon />
        </div>

        <div v-for="supplier in scoringData.suppliers || []" :key="supplier.supplier_id" class="supplier-scoring-block">
          <div class="supplier-scoring-header">
            <span class="supplier-name">{{ supplier.supplier_name }}</span>
            <span v-if="supplier.supplier_code" class="supplier-code">({{ supplier.supplier_code }})</span>
          </div>

          <el-table :data="supplier.items" size="small" border style="margin-top: 8px">
            <el-table-column prop="dimension" label="大维度" width="140" />
            <el-table-column prop="indicator" label="考核指标" min-width="260" />
            <el-table-column prop="max_score" label="满分" width="70" align="center" />
            <el-table-column label="打分" width="160" align="center">
              <template #default="{ row }">
                <el-input-number
                  v-model="row.score"
                  :min="0"
                  :max="row.max_score"
                  :step="0.5"
                  :precision="1"
                  :disabled="!scoringData.can_score"
                  size="small"
                  style="width: 120px"
                />
              </template>
            </el-table-column>
            <el-table-column label="备注" min-width="160">
              <template #default="{ row }">
                <el-input v-model="row.remark" :disabled="!scoringData.can_score" size="small" placeholder="选填" />
              </template>
            </el-table-column>
          </el-table>
        </div>

        <div v-if="scoringData.can_score && (scoringData.suppliers || []).length > 0" class="scoring-footer">
          <el-button type="primary" @click="submitAllScores" :loading="submitLoading">
            提交所有打分
          </el-button>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import api from '../../api/index'
import { ElMessage } from 'element-plus'

const myTasks = ref([])
const loading = ref(false)

const scoringDialogVisible = ref(false)
const scoringLoading = ref(false)
const scoringData = ref({})
const currentTaskId = ref(null)
const currentTaskName = ref('')
const submitLoading = ref(false)

const userDepartment = computed(() => localStorage.getItem('department') || '未知部门')

const typeLabelMap = { annual: '年度复评', quarterly: '季度考核', special: '专项考核' }
const typeTagMap = { annual: '', quarterly: 'warning', special: 'danger' }

const fetchMyTasks = async () => {
  loading.value = true
  try {
    const res = await api.get('/assessment/my-scoring-tasks')
    myTasks.value = res.data || []
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

const openScoring = async (task) => {
  currentTaskId.value = task.task_id
  currentTaskName.value = task.task_name
  scoringDialogVisible.value = true
  scoringLoading.value = true
  try {
    const res = await api.get(`/assessment/my-scoring-tasks/${task.task_id}`)
    scoringData.value = res.data || {}
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '获取打分数据失败')
  } finally {
    scoringLoading.value = false
  }
}

const submitAllScores = async () => {
  submitLoading.value = true
  try {
    const suppliers = scoringData.value.suppliers || []
    for (const supplier of suppliers) {
      const scores = (supplier.items || []).map(item => ({
        item_id: item.item_id,
        score: item.score,
        remark: item.remark,
      }))
      if (scores.length > 0) {
        await api.post('/assessment/batch-submit-scores', {
          task_id: currentTaskId.value,
          supplier_id: supplier.supplier_id,
          scores,
        })
      }
    }
    ElMessage.success('所有打分已提交')
    scoringDialogVisible.value = false
    fetchMyTasks()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '提交失败')
  } finally {
    submitLoading.value = false
  }
}

onMounted(() => {
  fetchMyTasks()
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

.page-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: var(--space-3);
}

.dept-hint {
  margin-bottom: var(--space-4);
}

.empty-state {
  padding: var(--space-8) 0;
}

.task-card {
  background: var(--bg-secondary);
  border-radius: var(--radius-md);
  padding: var(--space-4);
  margin-bottom: var(--space-3);
  border: 1px solid var(--border-color);
}

.task-card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.task-info {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.task-name {
  font-weight: 600;
  font-size: 15px;
  color: var(--text-primary);
}

.task-meta {
  display: flex;
  align-items: center;
  font-size: 13px;
  color: var(--text-tertiary);
}

.supplier-scoring-block {
  margin-bottom: var(--space-5);
  background: var(--bg-secondary);
  border-radius: var(--radius-md);
  padding: var(--space-4);
}

.supplier-scoring-header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.supplier-name {
  font-weight: 600;
  font-size: 15px;
  color: var(--text-primary);
}

.supplier-code {
  color: var(--text-tertiary);
  font-size: 13px;
}

.scoring-closed-hint {
  margin-bottom: var(--space-4);
}

.scoring-footer {
  margin-top: var(--space-4);
  text-align: right;
}
</style>
