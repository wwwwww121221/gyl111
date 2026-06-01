<template>
  <div class="page-container">
    <div class="content-card">
      <div class="toolbar">
        <div class="toolbar-left">
          <el-input
            v-model="searchQuery"
            class="modern-search-input search-input"
            placeholder="搜索询价单标题..."
            :prefix-icon="Search"
            clearable
          />
          <el-select v-model="statusFilter" class="status-select" placeholder="状态筛选" clearable>
            <el-option label="未确认" value="unconfirmed" />
            <el-option label="已确认" value="confirmed" />
            <el-option label="已锁定" value="locked" />
            <el-option label="已成交" value="deal" />
            <el-option label="已取消" value="cancelled" />
          </el-select>
        </div>
        <div class="toolbar-right">
          <span class="result-count">共 {{ filteredInquiries.length }} 条</span>
          <el-button v-if="searchQuery || statusFilter" @click="handleClearFilters" plain>清空筛选</el-button>
          <el-tooltip content="修改密码" placement="top">
            <el-button type="warning" @click="showChangePasswordDialog = true">修改密码</el-button>
          </el-tooltip>
          <el-tooltip content="刷新列表" placement="top">
            <el-button type="primary" @click="fetchInquiries" :icon="Refresh" circle />
          </el-tooltip>
        </div>
      </div>

      <div v-if="!isMobile" class="table-container">
        <el-table
          :data="filteredInquiries"
          style="width: 100%"
          v-loading="loading"
          empty-text="暂无询价数据"
          border
          stripe
          highlight-current-row
          fit
        >
          <el-table-column type="index" label="序号" width="80" align="center" />
          <el-table-column prop="task_title" label="询价单标题" min-width="160" show-overflow-tooltip />
          <el-table-column prop="contract_no" label="合同编号" width="110" align="center">
            <template #default="{ row }">
              <span v-if="row.contract_no">{{ row.contract_no }}</span>
              <span v-else style="color: #c0c4cc;">-</span>
            </template>
          </el-table-column>
          <el-table-column prop="created_at" label="发布时间" :formatter="formatDate" width="150" align="center" />
          <el-table-column prop="current_round" label="当前轮次" width="100" align="center" />
          <el-table-column prop="status" label="状态" width="120" align="center">
            <template #default="{ row }">
              <el-tag :type="getNewStatusType(row)" effect="light">{{ getNewStatusText(row) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="300" align="left">
            <template #default="{ row }">
              <div class="table-action-group">
                <el-button size="small" type="primary" class="action-primary-btn" @click="handleDetail(row)">查看详情 / 报价</el-button>
                <el-button
                  v-if="canFillContract(row)"
                  size="small"
                  plain
                  class="action-secondary-btn"
                  @click="handleOpenContractForm(row)"
                >
                  填写合同信息
                </el-button>
                <el-button
                  v-else-if="canViewContract(row)"
                  size="small"
                  plain
                  class="action-secondary-btn"
                  @click="handleViewContract(row)"
                >
                  下载/查看合同
                </el-button>
                <el-button
                  v-else-if="isContractGenerating(row)"
                  size="small"
                  plain
                  class="action-secondary-btn"
                  disabled
                >
                  合同生成中
                </el-button>
              </div>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <div v-else class="mobile-card-list">
        <el-empty v-if="filteredInquiries.length === 0" description="暂无询价数据" />
        <el-card
          v-for="row in filteredInquiries"
          :key="row.inquiry_supplier_id"
          class="mobile-inquiry-card"
          shadow="never"
        >
          <div class="mobile-card-header">
            <div class="mobile-card-title">{{ row.task_title }}</div>
            <el-tag :type="getNewStatusType(row)" effect="light">{{ getNewStatusText(row) }}</el-tag>
          </div>
          <div class="mobile-card-meta">合同编号：{{ row.contract_no || '-' }}</div>
          <div class="mobile-card-meta">发布时间：{{ formatDate(null, null, row.created_at) }}</div>
          <div class="mobile-card-meta">当前轮次：第 {{ row.current_round || 0 }} 轮</div>
          <div class="mobile-card-actions">
            <el-button size="small" type="primary" @click="handleDetail(row)">查看详情 / 报价</el-button>
            <el-button
              v-if="canFillContract(row)"
              size="small"
              plain
              @click="handleOpenContractForm(row)"
            >
              填写合同信息
            </el-button>
            <el-button
              v-else-if="canViewContract(row)"
              size="small"
              plain
              @click="handleViewContract(row)"
            >
              下载/查看合同
            </el-button>
            <el-button
              v-else-if="isContractGenerating(row)"
              size="small"
              plain
              disabled
            >
              合同生成中
            </el-button>
          </div>
        </el-card>
      </div>
    </div>

    <el-dialog
      v-model="dialogVisible"
      title="询价单详情与报价"
      :width="isMobile ? '96%' : '850px'"
      top="5vh"
      class="custom-dialog"
      draggable
      overflow
    >
      <div v-if="currentInquiry" class="dialog-content">
        <el-card shadow="never" class="info-card">
          <template #header>
            <div class="card-header">
              <span class="task-title">{{ currentInquiry.task_title }}</span>
              <el-tag :type="getNewStatusType(currentInquiry)" effect="dark">{{ getNewStatusText(currentInquiry) }}</el-tag>
            </div>
          </template>
          <el-descriptions :column="isMobile ? 1 : 2" border size="small">
            <el-descriptions-item label="当前轮次">
              <el-tag type="info" size="small">第 {{ currentInquiry.round }} 轮</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="操作提示">
              <span v-if="canQuote" style="color: #e6a23c; font-weight: bold;">请在下方填写报价并提交</span>
              <span v-else-if="isDeadlinePassed" style="color: #f56c6c; font-weight: bold;">当前询价已截止，无法报价</span>
              <span v-else style="color: #909399;">当前状态不可报价</span>
            </el-descriptions-item>
          </el-descriptions>
          <div class="deadline-countdown">
            <span class="countdown-label">报价截止倒计时：</span>
            <span :class="['countdown-value', { 'countdown-urgent': isDeadlineUrgent }]">{{ deadlineCountdownText }}</span>
          </div>
        </el-card>

        <div v-if="currentInquiry.latest_ai_feedback" class="feedback-box">
          <div class="feedback-title"><el-icon><ChatLineRound /></el-icon> 采购方/系统反馈</div>
          <div class="feedback-content">
            <div
              v-for="(line, index) in feedbackLines"
              :key="`${index}-${line}`"
              class="feedback-line"
            >
              {{ line }}
            </div>
          </div>
        </div>

        <div v-if="currentInquiry.attachments?.length" class="feedback-box">
          <div class="feedback-title">询价附件</div>
          <div class="attachment-list">
            <div
              v-for="(attachment, index) in currentInquiry.attachments"
              :key="`${attachment.file_path || 'attachment'}_${index}`"
              class="attachment-item"
            >
              <a
                href="#"
                class="attachment-link"
                @click.prevent="previewAttachment(attachment)"
              >
                {{ attachment.name }}
              </a>
              <span class="attachment-meta">{{ formatFileSize(attachment.size) }}</span>
              <el-button type="primary" link @click="previewAttachment(attachment)">预览</el-button>
              <el-button type="primary" link @click="openAttachmentInNewTab(attachment)">新窗口打开</el-button>
            </div>
          </div>
        </div>

        <div class="table-section-title"><span class="title-text">物料明细及报价</span></div>
        <div class="detail-table-wrap">
          <el-table :data="currentInquiry.items" style="width: 100%" border stripe size="small">
            <el-table-column prop="material_name" label="物料名称" />
            <el-table-column prop="material_code" label="物料编码" />
            <el-table-column prop="material_model" label="规格型号" min-width="140" show-overflow-tooltip />
            <el-table-column prop="qty" label="采购数量" width="100" />
            <el-table-column prop="price_unit_name" label="计价单位" width="100">
              <template #default="{ row }">{{ row.price_unit_name || '-' }}</template>
            </el-table-column>
            <el-table-column prop="target_delivery_date" label="期望交期" :formatter="formatDate" />
            <el-table-column label="您的可供数量" width="130">
              <template #default="{ row }">
                <el-input-number v-model="quoteForm[row.request_id].qty" :min="0.0001" :step="0.01" size="small" :disabled="!canQuote" />
              </template>
            </el-table-column>
            <el-table-column label="您的承诺交期" width="150">
              <template #default="{ row }">
                <el-date-picker
                  v-model="quoteForm[row.request_id].delivery_date"
                  type="date"
                  placeholder="选择交期"
                  size="small"
                  style="width: 100%"
                  value-format="YYYY-MM-DD"
                  :disabled="!canQuote"
                />
              </template>
            </el-table-column>
            <el-table-column label="您的报价(元)" width="150">
              <template #default="{ row }">
                <el-input-number
                  v-model="quoteForm[row.request_id].price"
                  :min="0"
                  :precision="2"
                  :step="0.1"
                  size="small"
                  :disabled="!canQuote"
                />
              </template>
            </el-table-column>
            <el-table-column label="备注">
              <template #default="{ row }">
                <el-input v-model="quoteForm[row.request_id].remark" size="small" placeholder="其他备注" :disabled="!canQuote" />
              </template>
            </el-table-column>
          </el-table>
        </div>
      </div>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="dialogVisible = false">关闭</el-button>
          <el-button type="primary" @click="submitQuote" :loading="submitLoading" :disabled="!canQuote">{{ quoteButtonText }}</el-button>
        </span>
      </template>
    </el-dialog>

    <el-dialog
      v-model="contractDialogVisible"
      title="填写合同信息"
      :width="isMobile ? '96%' : '620px'"
      destroy-on-close
      draggable
      overflow
    >
      <el-form ref="contractFormRef" :model="contractForm" :rules="contractFormRules" label-width="110px">
        <el-form-item label="地址" prop="address"><el-input v-model="contractForm.address" placeholder="请输入地址" /></el-form-item>
        <el-form-item label="法定代表人" prop="legal_representative"><el-input v-model="contractForm.legal_representative" placeholder="请输入法定代表人" /></el-form-item>
        <el-form-item label="委托代理人" prop="agent"><el-input v-model="contractForm.agent" placeholder="请输入委托代理人（选填）" /></el-form-item>
        <el-form-item label="联系电话" prop="contact_phone"><el-input v-model="contractForm.contact_phone" placeholder="请输入联系电话" /></el-form-item>
        <el-form-item label="开户银行" prop="bank_name"><el-input v-model="contractForm.bank_name" placeholder="请输入开户银行" /></el-form-item>
        <el-form-item label="账号" prop="bank_account"><el-input v-model="contractForm.bank_account" placeholder="请输入账号" /></el-form-item>
        <el-form-item label="税号" prop="tax_id"><el-input v-model="contractForm.tax_id" placeholder="请输入税号" /></el-form-item>
        <el-form-item label="传真" prop="fax"><el-input v-model="contractForm.fax" placeholder="请输入传真" /></el-form-item>
        <el-form-item label="邮编" prop="postal_code"><el-input v-model="contractForm.postal_code" placeholder="请输入邮编" /></el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="contractDialogVisible = false">取消</el-button>
          <el-button type="primary" :loading="contractSubmitLoading" @click="submitContractInfo">提交</el-button>
        </span>
      </template>
    </el-dialog>

    <el-dialog
      v-model="attachmentPreviewVisible"
      title="附件预览"
      :width="isMobile ? '96%' : '70%'"
      top="6vh"
      destroy-on-close
      draggable
      overflow
    >
      <div v-if="previewingAttachment" class="attachment-preview-container">
        <div class="attachment-preview-toolbar">
          <span class="attachment-preview-name">{{ previewingAttachment.name }}</span>
          <el-button type="primary" link @click="openAttachmentInNewTab(previewingAttachment)">新窗口打开</el-button>
        </div>
        <img
          v-if="getAttachmentPreviewType(previewingAttachment) === 'image'"
          :src="getAttachmentPreviewUrl(previewingAttachment)"
          class="attachment-preview-image"
        />
        <iframe
          v-else-if="getAttachmentPreviewType(previewingAttachment) === 'iframe'"
          :src="getAttachmentPreviewUrl(previewingAttachment)"
          class="attachment-preview-frame"
        />
        <el-empty
          v-else
          description="当前文件类型暂不支持直接在线预览，请使用“新窗口打开”查看或下载。"
        />
      </div>
    </el-dialog>

    <el-dialog
      v-model="showChangePasswordDialog"
      title="修改登录密码"
      width="450px"
      destroy-on-close
      draggable
      overflow
    >
      <el-form ref="passwordFormRef" :model="passwordForm" :rules="passwordRules" label-width="100px">
        <el-form-item label="当前密码" prop="old_password">
          <el-input v-model="passwordForm.old_password" type="password" show-password placeholder="请输入当前密码" />
        </el-form-item>
        <el-form-item label="新密码" prop="new_password">
          <el-input v-model="passwordForm.new_password" type="password" show-password placeholder="请输入新密码（至少6位）" />
        </el-form-item>
        <el-form-item label="确认新密码" prop="confirm_password">
          <el-input v-model="passwordForm.confirm_password" type="password" show-password placeholder="请再次输入新密码" />
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="showChangePasswordDialog = false">取消</el-button>
          <el-button type="primary" @click="handleChangePassword" :loading="changePasswordLoading">确认修改</el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, computed, watch } from 'vue'
import api, { getApiOrigin } from '../../api/index'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh, Search, ChatLineRound } from '@element-plus/icons-vue'

const inquiries = ref([])
const loading = ref(false)
const searchQuery = ref('')
const statusFilter = ref('')
const isMobile = ref(window.innerWidth <= 768)

const getDisplayStatus = (row) => {
  if (row.status === 'deal') return 'deal'
  if (row.status === 'locked') return 'locked'
  if (row.status === 'reject') return 'cancelled'
  if (row.task_status === 'closed' || row.task_status === 'cancelled') return 'cancelled'
  if (row.task_status === 'awaiting_award') return 'confirmed'
  if (row.status === 'sent') return 'unconfirmed'
  return 'confirmed'
}

const filteredInquiries = computed(() => {
  let result = inquiries.value
  if (searchQuery.value) {
    const q = searchQuery.value.toLowerCase()
    result = result.filter((task) => {
      const title = task.task_title?.toLowerCase?.() || ''
      const contractNo = task.contract_no?.toLowerCase?.() || ''
      return title.includes(q) || contractNo.includes(q)
    })
  }
  if (statusFilter.value) {
    result = result.filter((task) => getDisplayStatus(task) === statusFilter.value)
  }
  return result
})

const dialogVisible = ref(false)
const currentInquiry = ref(null)
const attachmentPreviewVisible = ref(false)
const previewingAttachment = ref(null)
const quoteForm = ref({})
const submitLoading = ref(false)
const currentLinkId = ref(null)
const confirmInquiryId = ref(null)
const contractDialogVisible = ref(false)
const contractSubmitLoading = ref(false)
const contractFormRef = ref()
const showChangePasswordDialog = ref(false)
const changePasswordLoading = ref(false)
const passwordFormRef = ref()
const passwordForm = ref({
  old_password: '',
  new_password: '',
  confirm_password: ''
})
const passwordRules = {
  old_password: [{ required: true, message: '请输入当前密码', trigger: 'blur' }],
  new_password: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 6, message: '密码长度至少6位', trigger: 'blur' }
  ],
  confirm_password: [
    { required: true, message: '请确认新密码', trigger: 'blur' },
    {
      validator: (rule, value, callback) => {
        if (value !== passwordForm.value.new_password) {
          callback(new Error('两次输入的密码不一致'))
        } else {
          callback()
        }
      },
      trigger: 'blur'
    }
  ]
}
const contractForm = ref({
  address: '',
  legal_representative: '',
  agent: '',
  contact_phone: '',
  bank_name: '',
  bank_account: '',
  tax_id: '',
  fax: '',
  postal_code: ''
})
const contractFormRules = {
  address: [{ required: true, message: '请输入地址', trigger: 'blur' }],
  legal_representative: [{ required: true, message: '请输入法定代表人', trigger: 'blur' }],
  contact_phone: [{ required: true, message: '请输入联系电话', trigger: 'blur' }],
  bank_name: [{ required: true, message: '请输入开户银行', trigger: 'blur' }],
  bank_account: [{ required: true, message: '请输入账号', trigger: 'blur' }],
  tax_id: [{ required: true, message: '请输入税号', trigger: 'blur' }],
  fax: [{ required: true, message: '请输入传真', trigger: 'blur' }],
  postal_code: [{ required: true, message: '请输入邮编', trigger: 'blur' }]
}
const nowTs = ref(Date.now())
let timerId = null

const handleResize = () => {
  isMobile.value = window.innerWidth <= 768
}

const startDeadlineTimer = () => {
  if (timerId) return
  timerId = window.setInterval(() => {
    nowTs.value = Date.now()
  }, 1000)
}

const stopDeadlineTimer = () => {
  if (timerId) {
    window.clearInterval(timerId)
    timerId = null
  }
}

const fetchInquiries = async () => {
  loading.value = true
  try {
    const res = await api.get('/supplier/my-inquiries')
    inquiries.value = res.data
  } catch (error) {
    console.error(error)
    ElMessage.error(error.response?.data?.detail || '获取询价列表失败')
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchInquiries()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  stopDeadlineTimer()
  window.removeEventListener('resize', handleResize)
})

watch(dialogVisible, (visible) => {
  if (visible) startDeadlineTimer()
  else stopDeadlineTimer()
})

const getNewStatusText = (row) => {
  const status = getDisplayStatus(row)
  const map = { unconfirmed: '未确认', confirmed: '已确认', locked: '已锁定', cancelled: '已取消', deal: '已成交' }
  return map[status]
}

const getNewStatusType = (row) => {
  const status = getDisplayStatus(row)
  const map = { unconfirmed: 'info', confirmed: 'primary', locked: 'success', cancelled: 'danger', deal: 'success' }
  return map[status]
}

const getContractPath = (row) => row.contract_pdf || row.contract_pdf_path || ''
const canViewContract = (row) => getDisplayStatus(row) === 'deal' && !!getContractPath(row)
const isContractGenerating = (row) => getDisplayStatus(row) === 'deal' && !getContractPath(row) && row.contract_status === 'generating'

const canFillContract = (row) => {
  if (getDisplayStatus(row) !== 'deal' || getContractPath(row)) return false
  const status = row.contract_status
  return !status || ['failed', 'pending', '待供应商填写'].includes(status)
}

const handleClearFilters = () => {
  searchQuery.value = ''
  statusFilter.value = ''
}

const handleViewContract = (row) => {
  const contractPath = getContractPath(row)
  if (!contractPath) {
    ElMessage.warning('合同文件尚未生成，请稍后重试')
    return
  }
  const baseUrl = getAttachmentBaseUrl()
  const contractUrl = contractPath.startsWith('http') ? contractPath : `${baseUrl}${contractPath}`
  const cacheBypass = contractUrl.includes('?') ? '&_t=' : '?_t='
  window.open(`${contractUrl}${cacheBypass}${Date.now()}`, '_blank')
}

const resetContractForm = () => {
  contractForm.value = {
    address: '',
    legal_representative: '',
    agent: '',
    contact_phone: '',
    bank_name: '',
    bank_account: '',
    tax_id: '',
    fax: '',
    postal_code: ''
  }
}

const handleOpenContractForm = async (row) => {
  confirmInquiryId.value = row.inquiry_supplier_id
  resetContractForm()
  try {
    const res = await api.get('/supplier/last-contract-info')
    if (res.data && Object.keys(res.data).length > 0) {
      contractForm.value = { ...contractForm.value, ...res.data }
    }
  } catch (error) {
    console.error('获取上次合同信息失败', error)
  }
  contractDialogVisible.value = true
}

const submitContractInfo = async () => {
  if (!confirmInquiryId.value) {
    ElMessage.warning('未找到询价记录，请刷新后重试')
    return
  }
  try {
    await contractFormRef.value.validate()
  } catch {
    ElMessage.warning('请先完善必填合同信息')
    return
  }
  contractSubmitLoading.value = true
  try {
    await api.post(`/supplier/inquiries/${confirmInquiryId.value}/confirm-contract`, contractForm.value)
    contractDialogVisible.value = false
    ElMessage.success('合同正在生成中')
    await fetchInquiries()
  } catch (error) {
    console.error(error)
    ElMessage.error(error.response?.data?.detail || '提交失败')
  } finally {
    contractSubmitLoading.value = false
  }
}

const handleChangePassword = async () => {
  if (!passwordFormRef.value) return
  try {
    await passwordFormRef.value.validate()
  } catch {
    ElMessage.warning('请先完善表单信息')
    return
  }
  changePasswordLoading.value = true
  try {
    await api.put('/supplier/change-password', {
      old_password: passwordForm.value.old_password,
      new_password: passwordForm.value.new_password
    })
    showChangePasswordDialog.value = false
    ElMessage.success('密码修改成功，下次登录请使用新密码')
    passwordForm.value = { old_password: '', new_password: '', confirm_password: '' }
  } catch (error) {
    console.error(error)
    ElMessage.error(error.response?.data?.detail || '密码修改失败')
  } finally {
    changePasswordLoading.value = false
  }
}

const formatDate = (row, column, cellValue) => {
  if (!cellValue) return '-'
  const date = new Date(cellValue)
  if (Number.isNaN(date.getTime())) return '-'
  return date.toLocaleString('zh-CN', { hour12: false })
}

const getAttachmentBaseUrl = () => {
  if (typeof window === 'undefined') return ''
  if (import.meta.env.DEV) {
    return `${window.location.protocol}//${window.location.hostname}:8000`
  }
  return ''
}

const normalizeAttachmentUrl = (filePath) => {
  const normalized = String(filePath || '').trim()
  if (!normalized) return '#'
  if (normalized.startsWith('http://') || normalized.startsWith('https://')) return normalized
  const normalizedPath = normalized.startsWith('/') ? normalized : `/${normalized}`
  return `${getAttachmentBaseUrl()}${normalizedPath}`
}

const getAttachmentPreviewUrl = (attachment) => {
  return normalizeAttachmentUrl(attachment?.preview_file_path || attachment?.file_path)
}

const formatFileSize = (size) => {
  const numericSize = Number(size || 0)
  if (!numericSize) return '-'
  if (numericSize < 1024) return `${numericSize} B`
  if (numericSize < 1024 * 1024) return `${(numericSize / 1024).toFixed(1)} KB`
  return `${(numericSize / (1024 * 1024)).toFixed(1)} MB`
}

const getAttachmentExtension = (attachment) => {
  const fileName = String(attachment?.name || attachment?.file_path || '').toLowerCase()
  const matched = fileName.match(/\.([a-z0-9]+)(?:\?|$)/)
  return matched ? matched[1] : ''
}

const getAttachmentPreviewType = (attachment) => {
  if (attachment?.preview_file_path) return 'iframe'
  const ext = getAttachmentExtension(attachment)
  if (['png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp', 'svg'].includes(ext)) return 'image'
  if (['pdf', 'txt', 'md', 'csv', 'json', 'log'].includes(ext)) return 'iframe'
  return 'unsupported'
}

const previewAttachment = (attachment) => {
  previewingAttachment.value = attachment
  attachmentPreviewVisible.value = true
}

const openAttachmentInNewTab = (attachment) => {
  const url = normalizeAttachmentUrl(attachment?.file_path)
  if (url && url !== '#') {
    window.open(url, '_blank', 'noopener,noreferrer')
  }
}

const handleDetail = async (row) => {
  currentLinkId.value = row.inquiry_supplier_id
  try {
    const res = await api.get(`/supplier/inquiry/${currentLinkId.value}`)
    currentInquiry.value = res.data
    const form = {}
    res.data.items.forEach((item) => {
      form[item.request_id] = {
        qty: item.qty,
        price: item.price ?? 0,
        delivery_date: item.delivery_date ? String(item.delivery_date).substring(0, 10) : '',
        remark: item.remark || ''
      }
    })
    quoteForm.value = form
    dialogVisible.value = true
  } catch (error) {
    console.error(error)
    ElMessage.error(error.response?.data?.detail || '获取询价详情失败')
  }
}

const getDeadlineMeta = (deadline) => {
  if (!deadline) return { passed: false, text: '未设置截止时间', urgent: false }
  const deadlineMs = new Date(deadline).getTime()
  if (Number.isNaN(deadlineMs)) return { passed: false, text: '截止时间无效', urgent: false }
  const diffMs = deadlineMs - nowTs.value
  if (diffMs <= 0) return { passed: true, text: '已截止报价', urgent: true }
  const totalSeconds = Math.floor(diffMs / 1000)
  const days = Math.floor(totalSeconds / 86400)
  const hours = Math.floor((totalSeconds % 86400) / 3600)
  const minutes = Math.floor((totalSeconds % 3600) / 60)
  const seconds = totalSeconds % 60
  const text = days > 0 ? `${days}天 ${hours}时 ${minutes}分 ${seconds}秒` : `${hours}时 ${minutes}分 ${seconds}秒`
  return { passed: false, text, urgent: diffMs < 2 * 3600 * 1000 }
}

const deadlineMeta = computed(() => getDeadlineMeta(currentInquiry.value?.deadline))
const deadlineCountdownText = computed(() => deadlineMeta.value.text)
const isDeadlineUrgent = computed(() => deadlineMeta.value.urgent)
const isDeadlinePassed = computed(() => deadlineMeta.value.passed)
const feedbackLines = computed(() => {
  const raw = currentInquiry.value?.latest_ai_feedback || ''
  if (!raw) return []
  return raw
    .split('\n')
    .map(line => line.trim())
    .filter(Boolean)
})

const canQuote = computed(() => {
  if (!currentInquiry.value) return false
  if (['closed', 'cancelled', 'awaiting_award'].includes(currentInquiry.value.task_status)) return false
  if (isDeadlinePassed.value) return false
  return ['sent', 'negotiation'].includes(currentInquiry.value.status) && new Date() < new Date(currentInquiry.value.deadline)
})

const quoteButtonText = computed(() => {
  if (isDeadlinePassed.value) return '已截止报价'
  if (!canQuote.value) return '当前不可报价'
  return '提交报价'
})

const submitQuote = async () => {
  if (!currentInquiry.value) return
  const buildPayload = (forceSubmit = false) => {
    const items = Object.keys(quoteForm.value).map((reqId) => {
      let d = quoteForm.value[reqId].delivery_date
      if (d && d.length === 10) d += 'T00:00:00'
      return {
        request_id: parseInt(reqId),
        qty: quoteForm.value[reqId].qty,
        price: quoteForm.value[reqId].price,
        delivery_date: d || null,
        remark: quoteForm.value[reqId].remark
      }
    })
    return { items, force_submit: forceSubmit }
  }
  const payload = buildPayload(false)
  const invalid = payload.items.some((item) => item.price <= 0)
  if (invalid) {
    ElMessage.warning('请输入有效的报价金额')
    return
  }
  submitLoading.value = true
  try {
    const res = await api.post(`/supplier/inquiry/${currentLinkId.value}/quote`, payload)
    if (res.data?.next_action === 'confirm_anomaly') {
      try {
        await ElMessageBox.confirm(res.data.message, '异常报价确认', {
          confirmButtonText: '确认无误，强行提交',
          cancelButtonText: '返回修改',
          type: 'warning'
        })
        submitLoading.value = true
        const forceRes = await api.post(`/supplier/inquiry/${currentLinkId.value}/quote`, buildPayload(true))
        ElMessage.success(forceRes.data.message || '强行提交成功')
        dialogVisible.value = false
        fetchInquiries()
      } catch {}
    } else {
      ElMessage.success(res.data.message || '报价提交成功')
      dialogVisible.value = false
      fetchInquiries()
    }
  } catch (error) {
    console.error(error)
    ElMessage.error(error.response?.data?.detail || '提交失败')
  } finally {
    submitLoading.value = false
  }
}
</script>

<style scoped>
.page-container {
  padding: 20px;
  height: auto;
  min-height: 100%;
  display: flex;
  flex-direction: column;
  box-sizing: border-box;
}

.content-card {
  background: white;
  padding: 20px;
  border-radius: 8px;
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: auto;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.05);
}

.table-container {
  flex: 1;
  min-height: 0;
  overflow: auto;
}

.toolbar {
  margin-bottom: 15px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-shrink: 0;
}

.toolbar-left,
.toolbar-right {
  display: flex;
  align-items: center;
  gap: 10px;
}

.search-input {
  width: 200px;
}

.status-select {
  width: 200px;
}

.result-count {
  color: #909399;
  font-size: 13px;
}

.table-action-group {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: 8px;
  flex-wrap: nowrap;
  width: 100%;
  padding-left: 8px;
  box-sizing: border-box;
}

.action-primary-btn {
  width: 118px;
  margin: 0;
}

.action-secondary-btn {
  width: 118px;
  margin: 0;
}

.mobile-card-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  overflow: auto;
}

.mobile-inquiry-card {
  border: 1px solid #ebeef5;
}

.mobile-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
}

.mobile-card-title {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
  line-height: 1.4;
}

.mobile-card-meta {
  margin-top: 8px;
  color: #606266;
  font-size: 13px;
}

.mobile-card-actions {
  margin-top: 12px;
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.dialog-content {
  display: flex;
  flex-direction: column;
  gap: 20px;
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

.task-title {
  font-size: 16px;
  font-weight: bold;
  color: #303133;
}

.feedback-box {
  background-color: #fdf6ec;
  border: 1px solid #faecd8;
  border-radius: 4px;
  padding: 15px;
}

.feedback-title {
  color: #e6a23c;
  font-weight: bold;
  margin-bottom: 8px;
  display: flex;
  align-items: center;
  gap: 5px;
}

.feedback-content {
  color: #606266;
  line-height: 1.5;
  font-size: 14px;
}

.feedback-line + .feedback-line {
  margin-top: 6px;
}

.attachment-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.attachment-item {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.attachment-link {
  color: #409eff;
  text-decoration: none;
  font-weight: 500;
}

.attachment-link:hover {
  text-decoration: underline;
}

.attachment-meta {
  font-size: 12px;
  color: #909399;
}

.attachment-preview-container {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: 420px;
}

.attachment-preview-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.attachment-preview-name {
  color: #303133;
  font-weight: 500;
  word-break: break-all;
}

.attachment-preview-frame {
  width: 100%;
  min-height: 70vh;
  border: 1px solid #ebeef5;
  border-radius: 8px;
}

.attachment-preview-image {
  width: 100%;
  max-height: 70vh;
  object-fit: contain;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  background: #fff;
}

.table-section-title {
  border-left: 4px solid #409eff;
  padding-left: 10px;
  margin-bottom: 10px;
}

.title-text {
  font-size: 15px;
  font-weight: bold;
  color: #303133;
}

.deadline-countdown {
  margin-top: 12px;
  font-size: 14px;
}

.countdown-label {
  color: #606266;
}

.countdown-value {
  color: #303133;
  font-weight: 500;
}

.countdown-urgent {
  color: #f56c6c;
  font-weight: 700;
}

.detail-table-wrap {
  width: 100%;
  overflow-x: auto;
}

@media (max-width: 992px) {
  .toolbar {
    flex-wrap: wrap;
    gap: 8px;
  }

  .toolbar-left,
  .toolbar-right {
    width: 100%;
    justify-content: flex-start;
  }

  .search-input,
  .status-select {
    width: 100%;
  }
}

@media (max-width: 768px) {
  .page-container {
    padding: 10px;
    height: auto;
    min-height: calc(100vh - 80px);
  }

  .content-card {
    padding: 12px;
    min-height: 0;
  }

  .result-count {
    display: none;
  }

  :deep(.el-dialog__body) {
    padding: 12px;
  }

  :deep(.el-dialog__header) {
    padding: 14px 14px 10px;
  }

  :deep(.el-dialog__footer) {
    padding: 10px 14px 14px;
  }
}
</style>
