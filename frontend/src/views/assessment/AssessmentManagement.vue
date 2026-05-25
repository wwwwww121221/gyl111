<template>
  <div class="page-container">
    <div class="content-card">
      <div class="toolbar">
        <el-select v-model="filterType" placeholder="考核类型" clearable style="width: 140px" @change="fetchTasks">
          <el-option label="年度复评" value="annual" />
          <el-option label="季度考核" value="quarterly" />
          <el-option label="专项考核" value="special" />
        </el-select>
        <el-select v-model="filterStatus" placeholder="状态" clearable style="width: 120px" @change="fetchTasks">
          <el-option label="打分中" value="scoring" />
          <el-option label="汇总中" value="summary" />
          <el-option label="已完成" value="completed" />
        </el-select>
        <el-button v-if="canCreate" type="primary" @click="openCreateDialog">创建考核任务</el-button>
      </div>

      <el-table :data="tasks" style="width: 100%" v-loading="loading" class="center-table" border>
        <el-table-column type="index" label="序号" width="55" align="center" />
        <el-table-column prop="name" label="考核名称" width="120" show-overflow-tooltip align="center" />
        <el-table-column prop="assessment_type" label="类型" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="typeTagMap[row.assessment_type]">{{ typeLabelMap[row.assessment_type] }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="statusTagMap[row.status]">{{ statusLabelMap[row.status] }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="supplier_count" label="供应商数" width="90" align="center" />
        <el-table-column label="进度" width="110" align="center">
          <template #default="{ row }">
            <el-progress :percentage="row.progress" :stroke-width="8" :format="() => `${row.progress}%`" />
          </template>
        </el-table-column>
        <el-table-column label="打分人员" min-width="280" align="center">
          <template #default="{ row }">
            <div v-if="row.scorers && Object.keys(row.scorers).length" class="scorers-tags">
              <el-tag v-for="(names, dept) in row.scorers" :key="dept" size="small" type="info" effect="plain">
                {{ dept }}: {{ names.join('/') }}
              </el-tag>
            </div>
            <span v-else class="text-muted">部门全员</span>
          </template>
        </el-table-column>
        <el-table-column prop="scoring_start" label="开始时间" width="155" align="center" />
        <el-table-column prop="scoring_end" label="截止时间" width="155" align="center" />
        <el-table-column label="操作" width="150" align="center">
          <template #default="{ row }">
            <div class="action-btns">
              <el-button size="small" type="primary" @click="viewDetail(row)">查看详情</el-button>
              <el-button
                v-if="canCreate && row.status === 'scoring' && row.progress >= 100"
                size="small"
                type="success"
                @click="completeTask(row)"
              >
                完成
              </el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog v-model="createDialogVisible" title="创建考核任务" width="720px" draggable overflow>
      <el-form ref="createFormRef" :model="createForm" :rules="createRules" label-width="110px">
        <el-form-item label="考核名称" prop="name">
          <el-input v-model="createForm.name" placeholder="如：2025年度供应商复评" />
        </el-form-item>
        <el-form-item label="考核类型" prop="assessment_type">
          <el-radio-group v-model="createForm.assessment_type">
            <el-radio value="annual">年度复评</el-radio>
            <el-radio value="quarterly">季度考核</el-radio>
            <el-radio value="special">专项考核</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="打分时间" prop="scoring_start">
          <el-date-picker
            v-model="scoringDateRange"
            type="datetimerange"
            range-separator="至"
            start-placeholder="开始时间"
            end-placeholder="截止时间"
            format="YYYY-MM-DD HH:mm"
            value-format="YYYY-MM-DDTHH:mm:ss"
          />
        </el-form-item>
        <el-form-item label="考核说明">
          <el-input v-model="createForm.description" type="textarea" :rows="3" placeholder="选填" />
        </el-form-item>
        <el-form-item label="指定打分人">
          <div class="scorers-hint">为每个考核部门指定具体打分人员，未指定的部门该部门所有人均可打分</div>
          <div v-for="(users, dept) in deptUsersMap" :key="dept" class="scorer-dept-block">
            <label class="dept-label">{{ dept }}</label>
            <el-select
              v-model="selectedScorers[dept]"
              multiple
              filterable
              collapse-tags
              collapse-tags-tooltip
              :max-collapse-tags="2"
              :placeholder="`选择${dept}的打分人`"
              style="width: 100%"
            >
              <el-option
                v-for="user in users"
                :key="user.id"
                :label="user.username"
                :value="user.id"
              />
            </el-select>
          </div>
        </el-form-item>
        <el-form-item label="选择供应商" prop="supplier_ids">
          <div class="supplier-actions">
            <el-button link type="primary" @click="selectAllSuppliers">全选</el-button>
            <el-button link @click="clearAllSuppliers">取消全选</el-button>
          </div>
          <el-select
            v-model="createForm.supplier_ids"
            multiple
            filterable
            collapse-tags
            collapse-tags-tooltip
            :max-collapse-tags="1"
            placeholder="搜索并选择供应商"
            style="width: 100%"
          >
            <el-option
              v-for="supplier in availableSuppliers"
              :key="supplier.id"
              :label="getSupplierOptionLabel(supplier)"
              :value="supplier.id"
            />
          </el-select>
          <div v-if="createForm.supplier_ids.length" class="supplier-summary">{{ supplierSelectionSummary }}</div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitCreate" :loading="submitLoading">确认创建</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="detailDialogVisible"
      title="考核详情"
      width="90%"
      top="4vh"
      draggable
      overflow
      destroy-on-close
    >
      <div v-loading="detailLoading">
        <div class="detail-header">
          <div class="detail-info-row">
            <span class="detail-label">考核名称：</span>
            <span>{{ detailData.name }}</span>
            <span class="detail-label detail-inline-label">类型：</span>
            <el-tag :type="typeTagMap[detailData.assessment_type]">{{ typeLabelMap[detailData.assessment_type] }}</el-tag>
            <span class="detail-label detail-inline-label">状态：</span>
            <el-tag :type="statusTagMap[detailData.status]">{{ statusLabelMap[detailData.status] }}</el-tag>
          </div>
          <div class="detail-info-row detail-info-spacing">
            <span class="detail-label">打分时间：</span>
            <span>{{ detailData.scoring_start }} ~ {{ detailData.scoring_end }}</span>
            <span class="detail-label detail-inline-label">创建人：</span>
            <span>{{ detailData.created_by }}</span>
          </div>
          <div v-if="detailData.description" class="detail-info-row detail-info-spacing">
            <span class="detail-label">说明：</span>
            <span>{{ detailData.description }}</span>
          </div>
          <div v-if="detailData.scorers && Object.keys(detailData.scorers).length" class="detail-info-row detail-info-spacing">
            <span class="detail-label">指定打分人：</span>
            <div class="detail-scorers-list">
              <div v-for="(users, dept) in detailData.scorers" :key="dept" class="detail-scorer-dept">
                <strong>{{ dept }}：</strong>
                <span v-for="(u, idx) in users" :key="u.id">
                  {{ u.username }}<template v-if="idx < users.length - 1">、</template>
                </span>
              </div>
            </div>
          </div>
        </div>

        <el-table :data="detailData.suppliers || []" style="width: 100%; margin-top: 16px" border row-key="supplier_id">
          <el-table-column type="expand">
            <template #default="{ row }">
              <div class="expand-content">
                <div v-for="dim in row.dimensions" :key="dim.dimension" class="dimension-block">
                  <div class="dimension-header">
                    <span class="dim-name">{{ dim.dimension }}</span>
                    <span class="dim-weight">权重 {{ (dim.weight * 100).toFixed(0) }}%</span>
                    <span class="dim-score">得分 {{ dim.earned }}/{{ dim.max }} -> 加权 {{ dim.weighted_score }}</span>
                  </div>
                  <el-table :data="dim.items" size="small" border style="margin-top: 8px">
                    <el-table-column prop="indicator" label="考核指标" min-width="280" />
                    <el-table-column prop="max_score" label="满分" width="70" align="center" />
                    <el-table-column prop="score" label="得分" width="70" align="center">
                      <template #default="{ row }">
                        <span :style="{ color: row.score !== null && row.score !== undefined ? 'var(--primary-color)' : 'var(--text-muted)' }">
                          {{ row.score !== null && row.score !== undefined ? row.score : '未打分' }}
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
          </el-table-column>
          <el-table-column type="index" label="排名" width="60" align="center" />
          <el-table-column prop="supplier_name" label="供应商" min-width="160" align="center" />
          <el-table-column prop="supplier_code" label="编码" width="100" align="center" />
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
          <el-table-column prop="total_score" label="总分" width="90" align="center">
            <template #default="{ row }">
              <span class="total-score">{{ row.total_score }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="grade" label="等级" width="80" align="center">
            <template #default="{ row }">
              <el-tag :type="getGradeTagType(row.grade)" effect="dark">
                {{ row.grade }}
              </el-tag>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../../api/index'

const tasks = ref([])
const loading = ref(false)
const filterType = ref('')
const filterStatus = ref('')

const createDialogVisible = ref(false)
const submitLoading = ref(false)
const createFormRef = ref(null)
const availableSuppliers = ref([])
const deptUsersMap = ref({})
const selectedScorers = reactive({})

const detailDialogVisible = ref(false)
const detailLoading = ref(false)
const detailData = ref({})

const userRole = computed(() => localStorage.getItem('role') || '')
const canCreate = computed(() => ['admin', 'buyer_manager'].includes(userRole.value))

const typeLabelMap = { annual: '年度复评', quarterly: '季度考核', special: '专项考核' }
const typeTagMap = { annual: '', quarterly: 'warning', special: 'danger' }
const statusLabelMap = { scoring: '打分中', summary: '汇总中', completed: '已完成' }
const statusTagMap = { scoring: 'warning', summary: '', completed: 'success' }

const scoringDateRange = ref([])

const createForm = ref({
  name: '',
  assessment_type: 'annual',
  supplier_ids: [],
  scoring_start: '',
  scoring_end: '',
  description: '',
})

const createRules = {
  name: [{ required: true, message: '请输入考核名称', trigger: 'blur' }],
  assessment_type: [{ required: true, message: '请选择考核类型', trigger: 'change' }],
  supplier_ids: [{ required: true, type: 'array', min: 1, message: '请至少选择一个供应商', trigger: 'change' }],
}

const supplierSelectionSummary = computed(() => {
  const selectedCount = createForm.value.supplier_ids.length
  const totalCount = availableSuppliers.value.length
  if (!selectedCount) return ''
  if (totalCount && selectedCount === totalCount) return `已选全部供应商，共 ${totalCount} 家`
  return `已选 ${selectedCount} 家供应商`
})

const getSupplierOptionLabel = (supplier) => {
  return supplier.code ? `${supplier.name} (${supplier.code})` : supplier.name
}

const selectAllSuppliers = () => {
  createForm.value.supplier_ids = availableSuppliers.value.map((supplier) => supplier.id)
}

const clearAllSuppliers = () => {
  createForm.value.supplier_ids = []
}

const getGradeTagType = (grade) => {
  if (grade === 'A级') return 'success'
  if (grade === 'B级') return 'warning'
  if (grade === 'C级') return 'danger'
  return 'info'
}

const fetchTasks = async () => {
  loading.value = true
  try {
    const params = {}
    if (filterType.value) params.assessment_type = filterType.value
    if (filterStatus.value) params.status_filter = filterStatus.value
    const res = await api.get('/assessment/tasks', { params })
    tasks.value = res.data || []
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

const openCreateDialog = async () => {
  scoringDateRange.value = []
  Object.keys(selectedScorers).forEach(k => delete selectedScorers[k])
  try {
    const [supRes, userRes] = await Promise.all([
      api.get('/assessment/suppliers-for-task'),
      api.get('/assessment/users-by-department'),
    ])
    availableSuppliers.value = supRes.data || []
    deptUsersMap.value = userRes.data || {}
    for (const dept of Object.keys(deptUsersMap.value)) {
      selectedScorers[dept] = []
    }
    const allIds = availableSuppliers.value.map((supplier) => supplier.id)
    createForm.value = {
      name: '',
      assessment_type: 'annual',
      supplier_ids: allIds,
      scoring_start: '',
      scoring_end: '',
      description: '',
    }
  } catch (e) {
    console.error(e)
    deptUsersMap.value = {}
    createForm.value = {
      name: '',
      assessment_type: 'annual',
      supplier_ids: [],
      scoring_start: '',
      scoring_end: '',
      description: '',
    }
  }
  createDialogVisible.value = true
}

const buildScorersPayload = () => {
  const result = {}
  let hasSelection = false
  for (const [dept, uids] of Object.entries(selectedScorers)) {
    if (uids && uids.length > 0) {
      result[dept] = [...new Set(uids)]
      hasSelection = true
    }
  }
  return hasSelection ? result : null
}

const submitCreate = async () => {
  if (!createFormRef.value) return
  await createFormRef.value.validate(async (valid) => {
    if (!valid) return
    if (!scoringDateRange.value || scoringDateRange.value.length < 2) {
      ElMessage.warning('请选择打分时间范围')
      return
    }
    submitLoading.value = true
    try {
      const payload = {
        ...createForm.value,
        scoring_start: scoringDateRange.value[0],
        scoring_end: scoringDateRange.value[1],
        scorers: buildScorersPayload(),
      }
      await api.post('/assessment/tasks', payload)
      ElMessage.success('考核任务创建成功')
      createDialogVisible.value = false
      fetchTasks()
    } catch (e) {
      ElMessage.error(e.response?.data?.detail || '创建失败')
    } finally {
      submitLoading.value = false
    }
  })
}

const viewDetail = async (row) => {
  detailDialogVisible.value = true
  detailLoading.value = true
  try {
    const res = await api.get(`/assessment/tasks/${row.id}`)
    detailData.value = res.data || {}
  } catch (e) {
    ElMessage.error('获取详情失败')
  } finally {
    detailLoading.value = false
  }
}

const getDimensionScore = (row, dimName) => {
  const dim = (row.dimensions || []).find((item) => item.dimension === dimName)
  if (!dim) return '-'
  return `${dim.earned}/${dim.max}`
}

const completeTask = async (row) => {
  try {
    await ElMessageBox.confirm(
      '确认完成此考核任务？完成后将自动更新供应商等级，此操作不可撤销。',
      '确认完成考核',
      { confirmButtonText: '确认完成', cancelButtonText: '取消', type: 'warning' },
    )
  } catch {
    return
  }
  try {
    await api.post(`/assessment/tasks/${row.id}/complete`)
    ElMessage.success('考核已完成，供应商等级已更新')
    fetchTasks()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '操作失败')
  }
}

onMounted(() => {
  fetchTasks()
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
  flex-wrap: wrap;
}

:deep(.el-form-item__content) {
  flex-wrap: wrap;
}

.detail-header {
  background: var(--bg-secondary);
  border-radius: var(--radius-md);
  padding: var(--space-4);
}

.detail-info-row {
  display: flex;
  align-items: center;
  font-size: 14px;
  color: var(--text-primary);
}

.detail-info-spacing {
  margin-top: 8px;
}

.detail-label {
  color: var(--text-tertiary);
  font-weight: 500;
}

.detail-inline-label {
  margin-left: 24px;
}

.total-score {
  font-weight: 700;
  font-size: 15px;
}

.expand-content {
  padding: 16px 24px;
}

.dimension-block {
  margin-bottom: var(--space-4);
}

.supplier-summary {
  margin-top: 8px;
  font-size: 12px;
  line-height: 1.4;
  color: var(--text-tertiary);
}

.supplier-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-bottom: 6px;
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

.scorers-hint {
  width: 100%;
  font-size: 12px;
  color: var(--text-tertiary);
  margin-bottom: 12px;
  line-height: 1.5;
}

.scorer-dept-block {
  box-sizing: border-box;
  width: calc(50% - 8px);
  min-width: 240px;
  margin: 0 12px 12px 0;
  padding: 12px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  background: var(--bg-secondary);
}

.dept-label {
  display: block;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 8px;
  line-height: 1.4;
}

.dept-scorer-select {
  width: 100%;
}

@media (max-width: 900px) {
  .scorer-dept-block {
    width: 100%;
    margin-right: 0;
  }
}

.scorers-cell {
  font-size: 12px;
}

.scorer-dept-row {
  display: flex;
  gap: 4px;
  margin-bottom: 2px;
}

.dept-name {
  color: var(--text-tertiary);
  white-space: nowrap;
}

.scorer-names {
  color: var(--text-secondary);
}

.no-scorers {
  font-size: 12px;
  color: var(--text-muted);
}

.scorers-tags {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 4px;
}

.detail-scorers-list {
  font-size: 13px;
}

.detail-scorer-dept {
  margin-bottom: 4px;
}

.action-btns {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 6px;
}
</style>
