<template>
  <div class="agent-page">
    <div class="agent-shell" v-loading="pageLoading">
      <aside class="agent-sidebar">
        <div class="sidebar-header">
          <div>
            <div class="sidebar-kicker">Procurement Copilot</div>
            <h2>采购助手</h2>
          </div>
          <el-button type="primary" @click="startNewConversation">新建对话</el-button>
        </div>

        <div class="session-list">
          <button
            v-for="session in sessions"
            :key="session.session_id"
            type="button"
            class="session-item"
            :class="{ active: session.session_id === currentSessionId }"
            @click="openSession(session.session_id)"
          >
            <div class="session-title">{{ session.title || '新对话' }}</div>
            <div class="session-preview">{{ session.last_message_preview || '暂无消息' }}</div>
            <div class="session-meta">
              <span>{{ formatDateTime(session.updated_at) }}</span>
              <span>{{ session.message_count }} 条</span>
            </div>
          </button>

          <div v-if="sessions.length === 0" class="session-empty">
            暂无历史对话，点击“新建对话”开始。
          </div>
        </div>
      </aside>

      <section class="agent-main">
        <header class="chat-header">
          <div>
            <h3>{{ currentSessionTitle }}</h3>
            <p>支持查询物料、供应商、历史价格、采购申请和采购订单。</p>
          </div>
          <div class="chat-header-actions">
            <span class="model-pill">{{ agentModelLabel }}</span>
            <el-button plain @click="clearCurrentConversation" :disabled="!currentSessionId || loading">清空当前对话</el-button>
          </div>
        </header>

        <div ref="messagesRef" class="chat-body">
          <div v-if="messages.length === 0" class="chat-empty">
            <div class="empty-card">
              <h4>可以直接这样问我</h4>
              <div class="empty-actions">
                <button type="button" class="prompt-chip" @click="fillPrompt('帮我查一下壳体组件最近一年的供应商价格趋势')">
                  帮我查价格趋势
                </button>
                <button type="button" class="prompt-chip" @click="fillPrompt('帮我看一下某家供应商最近半年供货情况')">
                  帮我看供应商供货情况
                </button>
                <button type="button" class="prompt-chip" @click="fillPrompt('这个物料最近有哪些采购订单')">
                  帮我查采购订单
                </button>
              </div>
            </div>
          </div>

          <article
            v-for="item in messages"
            :key="item.id"
            class="message-row"
            :class="item.role === 'user' ? 'is-user' : 'is-assistant'"
          >
            <div class="message-bubble">
              <div class="message-role">{{ item.role === 'user' ? '你' : '采购助手' }}</div>
              <div class="message-text">{{ item.content }}</div>
              <div v-if="item.role === 'assistant' && getPendingActionCards(item).length" class="pending-actions">
                <div
                  v-for="action in getPendingActionCards(item)"
                  :key="action.pending_action_id"
                  class="pending-action-card"
                >
                  <div class="pending-action-title">{{ action.preview?.title || action.preview?.task_title || 'AI 待确认动作' }}</div>
                  <div class="pending-action-desc">{{ action.message || '该动作需要人工确认后才会执行。' }}</div>
                  <div v-if="action.action_type === 'create_inquiry_draft'" class="pending-action-form">
                    <el-input v-model="getActionDraft(action).title" size="small" placeholder="询价草稿标题" />
                    <div class="pending-action-grid">
                      <el-input v-model="getActionDraft(action).material_code" size="small" placeholder="物料编码" disabled />
                      <el-input v-model="getActionDraft(action).material_name" size="small" placeholder="物料名称" disabled />
                    </div>
                    <div class="pending-action-grid">
                      <el-input-number v-model="getActionDraft(action).qty" size="small" :min="0" :precision="4" :controls="false" placeholder="数量" />
                      <el-input v-model="getActionDraft(action).target_price" size="small" placeholder="目标价建议" />
                    </div>
                    <el-select
                      v-model="getActionDraft(action).supplier_ids"
                      multiple
                      collapse-tags
                      collapse-tags-tooltip
                      size="small"
                      placeholder="建议供应商"
                    >
                      <el-option
                        v-for="supplier in getActionDraft(action).supplier_options"
                        :key="supplier.value"
                        :label="supplier.label"
                        :value="supplier.value"
                      />
                    </el-select>
                    <el-date-picker
                      v-model="getActionDraft(action).delivery_date"
                      type="date"
                      value-format="YYYY-MM-DD"
                      size="small"
                      placeholder="期望交期"
                      style="width: 100%;"
                    />
                    <div v-if="getActionDraft(action).supplier_names" class="pending-action-hint">
                      建议供应商：{{ getActionDraft(action).supplier_names }}
                    </div>
                  </div>
                  <div v-else-if="action.action_type === 'create_inquiry_from_selected_requests'" class="pending-action-form">
                    <el-input v-model="getActionDraft(action).title" size="small" placeholder="询价任务标题" />
                    <div class="pending-action-grid">
                      <el-input v-model="getActionDraft(action).material_codes" size="small" placeholder="物料编码" disabled />
                      <el-input v-model="getActionDraft(action).material_names" size="small" placeholder="物料名称" disabled />
                    </div>
                    <el-input v-model="getActionDraft(action).material_models" size="small" placeholder="规格型号" disabled />
                    <div class="pending-action-grid">
                      <el-input v-model="getActionDraft(action).qty_total" size="small" placeholder="合计数量" disabled />
                      <el-input v-model="getActionDraft(action).delivery_dates" size="small" placeholder="需求交期" disabled />
                    </div>
                    <div class="pending-action-grid">
                      <el-select
                        v-model="getActionDraft(action).supplier_ids"
                        multiple
                        collapse-tags
                        collapse-tags-tooltip
                        size="small"
                        placeholder="建议供应商"
                      >
                        <el-option
                          v-for="supplier in getActionDraft(action).supplier_options"
                          :key="supplier.value"
                          :label="supplier.label"
                          :value="supplier.value"
                        />
                      </el-select>
                      <el-input v-model="getActionDraft(action).target_price" size="small" placeholder="目标价建议" />
                    </div>
                    <div v-if="getActionDraft(action).supplier_names" class="pending-action-hint">
                      建议供应商：{{ getActionDraft(action).supplier_names }}
                    </div>
                    <div v-if="getActionDraft(action).price_reference_text" class="pending-action-hint">
                      历史参考价：{{ getActionDraft(action).price_reference_text }}
                    </div>
                    <div v-if="getActionDraft(action).risk_notes" class="pending-action-hint">
                      风险提示：{{ getActionDraft(action).risk_notes }}
                    </div>
                    <el-date-picker
                      v-model="getActionDraft(action).deadline"
                      type="date"
                      value-format="YYYY-MM-DD"
                      size="small"
                      placeholder="报价截止日期"
                      style="width: 100%;"
                    />
                    <div class="pending-action-hint">
                      已勾选明细：{{ getActionDraft(action).selected_line_count }} 条，物料项：{{ getActionDraft(action).material_item_count }} 项
                    </div>
                    <div v-if="getActionDraft(action).bill_nos" class="pending-action-hint">
                      关联单号：{{ getActionDraft(action).bill_nos }}
                    </div>
                  </div>
                  <div v-else-if="action.action_type === 'save_manual_quotes'" class="pending-action-form">
                    <el-input v-model="getActionDraft(action).title" size="small" placeholder="手动比价任务标题" />
                    <div class="pending-action-hint">
                      已勾选明细：{{ getActionDraft(action).selected_line_count }} 条，物料项：{{ getActionDraft(action).material_item_count }} 项
                    </div>
                    <div v-if="getActionDraft(action).bill_nos" class="pending-action-hint">
                      关联单号：{{ getActionDraft(action).bill_nos }}
                    </div>
                    <div v-if="getActionDraft(action).price_reference_text" class="pending-action-hint">
                      历史参考价：{{ getActionDraft(action).price_reference_text }}
                    </div>
                    <div v-if="getActionDraft(action).risk_notes" class="pending-action-hint">
                      风险提示：{{ getActionDraft(action).risk_notes }}
                    </div>
                    <div v-if="getActionDraft(action).material_lines.length" class="manual-quote-section">
                      <div class="manual-quote-section-title">物料明细（确认后将创建手动比价任务）</div>
                      <div class="manual-quote-table">
                        <div class="manual-quote-table-header">
                          <span>物料编码</span>
                          <span>物料名称</span>
                          <span>规格型号</span>
                          <span>数量</span>
                          <span>需求交期</span>
                        </div>
                        <div
                          v-for="(line, lineIdx) in getActionDraft(action).material_lines"
                          :key="`material-line-${lineIdx}`"
                          class="manual-quote-table-row"
                        >
                          <span>{{ line.material_code || '-' }}</span>
                          <span>{{ line.material_name || '-' }}</span>
                          <span>{{ line.material_model || '-' }}</span>
                          <span>{{ line.qty ?? '-' }}</span>
                          <span>{{ line.delivery_date || '-' }}</span>
                        </div>
                      </div>
                    </div>
                    <div v-if="getActionDraft(action).manual_supplier_options.length" class="manual-quote-section">
                      <div class="manual-quote-section-title">推荐供应商（参考，确认后可在任务详情中录入报价）</div>
                      <div
                        v-for="supplier in getActionDraft(action).manual_supplier_options"
                        :key="`supplier-option-${supplier.value}`"
                        class="manual-supplier-row"
                      >
                        <div class="manual-supplier-name">{{ supplier.label }}</div>
                        <div class="manual-supplier-meta">
                          <span v-if="supplier.avg_price !== null && supplier.avg_price !== undefined">历史均价：{{ supplier.avg_price }}</span>
                          <span v-if="supplier.latest_price !== null && supplier.latest_price !== undefined">最新价：{{ supplier.latest_price }}</span>
                          <span v-if="supplier.rating_score !== null && supplier.rating_score !== undefined">评分：{{ supplier.rating_score }}</span>
                        </div>
                        <div v-if="supplier.recommend_reason" class="manual-supplier-reason">{{ supplier.recommend_reason }}</div>
                      </div>
                    </div>
                    <div class="pending-action-hint manual-quote-tip">
                      确认后将创建手动比价任务（不发送询价单）。您可以在询价任务详情中录入供应商报价，再进行比价分析。
                    </div>
                  </div>
                  <el-button
                    class="pending-action-confirm-btn"
                    type="primary"
                    size="small"
                    :loading="confirmingActionIds.includes(action.pending_action_id)"
                    @click="confirmAction(action)"
                  >
                    {{ getPendingActionButtonLabel(action) }}
                  </el-button>
                </div>
              </div>
            </div>
          </article>

          <article v-if="loading" class="message-row is-assistant">
            <div class="message-bubble loading-bubble">
              <div class="message-role">采购助手</div>
              <div class="typing-dots">
                <span></span>
                <span></span>
                <span></span>
              </div>
            </div>
          </article>
        </div>

        <footer class="chat-footer">
          <textarea
            v-model="draft"
            class="chat-input"
            rows="4"
            maxlength="2000"
            placeholder="输入采购相关问题，Enter 发送，Shift + Enter 换行"
            @keydown="handleKeydown"
          ></textarea>
          <div class="chat-footer-bar">
            <span class="input-tip">当前会话会自动保存，左侧可查看历史记录。</span>
            <el-button type="primary" :loading="loading" :disabled="!canSend" @click="sendMessage">发送</el-button>
          </div>
        </footer>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import {
  clearProcurementAgentMemory,
  confirmProcurementAgentAction,
  createProcurementAgentSession,
  getProcurementAgentSessionMessages,
  getProcurementAgentSessions,
  getProcurementAgentStatus,
  sendProcurementAgentMessage,
} from '../../api/agent'

const pageLoading = ref(false)
const loading = ref(false)
const draft = ref('')
const sessions = ref([])
const messages = ref([])
const currentSessionId = ref('')
const pendingSessionId = ref('')
const agentModelLabel = ref('DeepSeek Flash')
const messagesRef = ref(null)
const confirmingActionIds = ref([])
const pendingActionDrafts = ref({})

const canSend = computed(() => draft.value.trim().length > 0)
const currentSessionTitle = computed(() => {
  const current = sessions.value.find((item) => item.session_id === currentSessionId.value)
  if (current?.title) return current.title
  if (pendingSessionId.value) return '新对话'
  return '采购助手'
})

const normalizeMessages = (rows = []) =>
  rows.map((item, index) => ({
    id: `${item.created_at || Date.now()}_${index}`,
    role: item.role,
    content: item.content,
    created_at: item.created_at,
    metadata: item.metadata || {},
  }))

const getPendingActionCards = (message) => {
  const toolResults = Array.isArray(message?.metadata?.tool_results) ? message.metadata.tool_results : []
  return toolResults
    .flatMap((item) => {
      const data = item?.data || {}
      if (Number(data?.pending_action_id) > 0) {
        return [{
          ...data,
          action_type: data?.action_type || item?.name || '',
        }]
      }
      if (Number(data?.award_suggestion?.pending_action_id) > 0) {
        return [{
          pending_action_id: data.award_suggestion.pending_action_id,
          action_type: 'confirm_award',
          preview: {
            task_title: data?.inquiry?.title || '',
            supplier_name: data?.award_suggestion?.recommended_supplier?.supplier_name || '',
            quote_total_amount: data?.award_suggestion?.recommended_supplier?.quote_total_amount,
          },
          message: data?.award_suggestion?.note || '',
        }]
      }
      return []
    })
}

const getPendingActionButtonLabel = (action) => {
  const actionType = String(action?.action_type || '').trim()
  if (actionType === 'create_inquiry_draft') return '确认创建询价草稿'
  if (actionType === 'create_inquiry_from_selected_requests') return '确认创建询价任务'
  if (actionType === 'save_manual_quotes') return '确认创建手动比价任务'
  if (actionType === 'confirm_award') return '确认中标'
  if (actionType === 'create_contract_draft') return '确认生成合同草稿'
  return '确认执行'
}

const getActionDraft = (action) => {
  const actionId = Number(action?.pending_action_id)
  if (!Number.isFinite(actionId) || actionId <= 0) return {}
  if (!pendingActionDrafts.value[actionId]) {
    const preview = action?.preview || {}
    const recommendedSuppliers = Array.isArray(preview.recommended_suppliers) ? preview.recommended_suppliers : []
    const supplierOptions = Array.isArray(preview.supplier_options) ? preview.supplier_options : []
    pendingActionDrafts.value[actionId] = {
      title: preview.title || preview.task_title || '',
      material_code: preview.material_code || '',
      material_name: preview.material_name || '',
      qty: preview.qty ?? null,
      delivery_date: preview.delivery_date || '',
      target_price: preview.target_price_suggestion ?? '',
      supplier_ids: Array.isArray(preview.supplier_ids) ? preview.supplier_ids.filter((item) => Number(item) > 0) : [],
      supplier_names: Array.isArray(preview.supplier_names) ? preview.supplier_names.filter(Boolean).join('、') : '',
      supplier_options: recommendedSuppliers
        .filter((item) => Number(item?.supplier_id) > 0)
        .map((item) => ({ value: Number(item.supplier_id), label: item.supplier_name || `供应商${item.supplier_id}` })),
      deadline: preview.deadline || '',
      request_count: preview.request_count ?? '',
      selected_line_count: preview.selected_line_count ?? preview.request_count ?? '',
      material_item_count: preview.material_item_count ?? '',
      bill_nos: Array.isArray(preview.bill_nos) ? preview.bill_nos.filter(Boolean).join('、') : '',
      material_codes: Array.isArray(preview.material_codes) ? preview.material_codes.filter(Boolean).join('、') : '',
      material_names: Array.isArray(preview.material_names) ? preview.material_names.filter(Boolean).join('、') : '',
      material_models: Array.isArray(preview.material_models) ? preview.material_models.filter(Boolean).join('、') : '',
      delivery_dates: Array.isArray(preview.delivery_dates) ? preview.delivery_dates.filter(Boolean).join('、') : '',
      qty_total: preview.qty_total ?? '',
      price_reference_text: formatPriceReference(preview.price_reference),
      risk_notes: Array.isArray(preview.risk_notes) ? preview.risk_notes.filter(Boolean).join('；') : '',
      // 手动比价专用：物料明细和供应商候选
      material_lines: Array.isArray(preview.material_lines) ? preview.material_lines : [],
      manual_supplier_options: supplierOptions
        .filter((item) => Number(item?.supplier_id) > 0)
        .map((item) => ({
          value: Number(item.supplier_id),
          label: item.supplier_name || `供应商${item.supplier_id}`,
          avg_price: item.avg_price,
          latest_price: item.latest_price,
          rating_score: item.rating_score,
          recommend_reason: item.recommend_reason,
        })),
    }
  }
  return pendingActionDrafts.value[actionId]
}

const formatPriceReference = (priceReference) => {
  if (!priceReference || typeof priceReference !== 'object') return ''
  const minPrice = priceReference.min_price
  const maxPrice = priceReference.max_price
  const avgPrice = priceReference.avg_price
  const rangeText = (minPrice !== null && minPrice !== undefined && maxPrice !== null && maxPrice !== undefined)
    ? `${minPrice} ~ ${maxPrice}`
    : ''
  if (rangeText && avgPrice !== null && avgPrice !== undefined) {
    return `${rangeText}，均价 ${avgPrice}`
  }
  if (rangeText) return rangeText
  if (avgPrice !== null && avgPrice !== undefined) return `均价 ${avgPrice}`
  return ''
}

const buildActionOverrides = (action) => {
  const actionType = String(action?.action_type || '').trim()
  const draftModel = getActionDraft(action)
  if (actionType === 'create_inquiry_draft') {
    return {
      title: String(draftModel.title || '').trim(),
      qty: draftModel.qty,
      delivery_date: draftModel.delivery_date || null,
      target_price: draftModel.target_price === '' ? null : draftModel.target_price,
      supplier_ids: Array.isArray(draftModel.supplier_ids) ? draftModel.supplier_ids : [],
    }
  }
  if (actionType === 'create_inquiry_from_selected_requests') {
    return {
      title: String(draftModel.title || '').trim(),
      deadline: draftModel.deadline || null,
      supplier_ids: Array.isArray(draftModel.supplier_ids) ? draftModel.supplier_ids : [],
      target_price: draftModel.target_price === '' ? null : draftModel.target_price,
    }
  }
  if (actionType === 'save_manual_quotes') {
    return {
      title: String(draftModel.title || '').trim(),
    }
  }
  return {}
}

const currentPageContext = computed(() => {
  let stored = {}
  try {
    stored = JSON.parse(sessionStorage.getItem('procurement_agent_page_context') || '{}')
  } catch {
    stored = {}
  }
  return {
    page: stored.page || stored.route_name || '/agent/workspace',
    route_name: stored.route_name || '/agent/workspace',
    flow_mode: stored.flow_mode ?? null,
    selected_request_ids: Array.isArray(stored.selected_request_ids) ? stored.selected_request_ids : [],
    selected_requests: Array.isArray(stored.selected_requests) ? stored.selected_requests : [],
    bill_no: stored.bill_no || '',
    material_code: stored.material_code || '',
    material_name: stored.material_name || '',
    material_model: stored.material_model || '',
    qty: stored.qty ?? '',
    delivery_date: stored.delivery_date || '',
    target_price: stored.target_price ?? null,
    supplier_id: stored.supplier_id || '',
    supplier_code: stored.supplier_code || '',
    supplier_name: stored.supplier_name || '',
    inquiry_id: stored.inquiry_id || '',
    contract_id: stored.contract_id || '',
  }
})

const scrollToBottom = async () => {
  await nextTick()
  const el = messagesRef.value
  if (el) el.scrollTop = el.scrollHeight
}

const formatDateTime = (timestamp) => {
  if (!timestamp) return ''
  const date = new Date(Number(timestamp) * 1000)
  const month = `${date.getMonth() + 1}`.padStart(2, '0')
  const day = `${date.getDate()}`.padStart(2, '0')
  const hours = `${date.getHours()}`.padStart(2, '0')
  const minutes = `${date.getMinutes()}`.padStart(2, '0')
  return `${month}-${day} ${hours}:${minutes}`
}

const refreshSessions = async (preferredSessionId = '') => {
  const { data } = await getProcurementAgentSessions()
  sessions.value = Array.isArray(data) ? data : []

  if (preferredSessionId) {
    currentSessionId.value = preferredSessionId
    return
  }

  if (currentSessionId.value && sessions.value.some((item) => item.session_id === currentSessionId.value)) {
    return
  }

  currentSessionId.value = sessions.value[0]?.session_id || ''
}

const openSession = async (sessionId) => {
  if (!sessionId) return
  pageLoading.value = true
  pendingSessionId.value = ''
  try {
    const { data } = await getProcurementAgentSessionMessages(sessionId)
    currentSessionId.value = sessionId
    messages.value = normalizeMessages(Array.isArray(data) ? data : [])
    scrollToBottom()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '加载历史对话失败')
  } finally {
    pageLoading.value = false
  }
}

const startNewConversation = async () => {
  messages.value = []
  currentSessionId.value = ''
  try {
    const { data } = await createProcurementAgentSession()
    pendingSessionId.value = data?.session_id || ''
  } catch {
    pendingSessionId.value = ''
  }
}

const clearCurrentConversation = async () => {
  const targetSessionId = currentSessionId.value
  messages.value = []
  if (!targetSessionId) return

  try {
    await clearProcurementAgentMemory({
      scope: 'current_session',
      session_id: targetSessionId,
    })
    await refreshSessions()
    if (sessions.value.length > 0) {
      await openSession(sessions.value[0].session_id)
    } else {
      currentSessionId.value = ''
      pendingSessionId.value = ''
    }
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '清空当前对话失败')
  }
}

const fillPrompt = (text) => {
  draft.value = text
}

const confirmAction = async (action) => {
  const normalizedId = Number(action?.pending_action_id)
  if (!Number.isFinite(normalizedId) || normalizedId <= 0) return
  if (confirmingActionIds.value.includes(normalizedId)) return

  confirmingActionIds.value = [...confirmingActionIds.value, normalizedId]
  try {
    const { data } = await confirmProcurementAgentAction(normalizedId, buildActionOverrides(action))
    ElMessage.success('AI 待确认动作已执行')
    window.dispatchEvent(new CustomEvent('procurement-agent-action-confirmed', { detail: data }))
    delete pendingActionDrafts.value[normalizedId]
    messages.value.push({
      id: `${Date.now()}_confirm`,
      role: 'assistant',
      content: `已完成确认动作：${data?.action_type || normalizedId}`,
      created_at: Math.floor(Date.now() / 1000),
      metadata: {},
    })
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '确认动作失败')
  } finally {
    confirmingActionIds.value = confirmingActionIds.value.filter((id) => id !== normalizedId)
    scrollToBottom()
  }
}

const sendMessage = async () => {
  const message = draft.value.trim()
  if (!message || loading.value) return

  const targetSessionId = currentSessionId.value || pendingSessionId.value || ''
  const userMessage = {
    id: `${Date.now()}_user`,
    role: 'user',
    content: message,
    created_at: Math.floor(Date.now() / 1000),
  }

  messages.value.push(userMessage)
  draft.value = ''
  loading.value = true
  scrollToBottom()

  try {
    const { data } = await sendProcurementAgentMessage({
      message,
      session_id: targetSessionId || null,
      context: currentPageContext.value,
    })

    const newSessionId = data?.session_id || targetSessionId
    currentSessionId.value = newSessionId
    pendingSessionId.value = ''
    messages.value.push({
      id: `${Date.now()}_assistant`,
      role: 'assistant',
      content: data?.answer || '采购助手暂时没有返回内容。',
      created_at: Math.floor(Date.now() / 1000),
      metadata: {
        tool_results: Array.isArray(data?.tool_results) ? data.tool_results : [],
      },
    })
    await refreshSessions(newSessionId)
    scrollToBottom()
  } catch (error) {
    messages.value.push({
      id: `${Date.now()}_error`,
      role: 'assistant',
      content: error.response?.data?.detail || '采购助手暂时不可用，请稍后重试。',
      created_at: Math.floor(Date.now() / 1000),
      metadata: {},
    })
  } finally {
    loading.value = false
    scrollToBottom()
  }
}

const handleKeydown = (event) => {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    sendMessage()
  }
}

onMounted(async () => {
  pageLoading.value = true
  try {
    const [statusRes] = await Promise.all([
      getProcurementAgentStatus(),
      refreshSessions(),
    ])
    if (statusRes?.data?.model) {
      agentModelLabel.value = statusRes.data.model
    }
    if (currentSessionId.value) {
      await openSession(currentSessionId.value)
    }
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '初始化采购助手失败')
  } finally {
    pageLoading.value = false
  }
})
</script>

<style scoped>
.agent-page {
  height: 100%;
  padding: 20px;
  box-sizing: border-box;
}

.agent-shell {
  height: 100%;
  display: grid;
  grid-template-columns: 320px 1fr;
  gap: 18px;
}

.agent-sidebar,
.agent-main {
  background: #f7fafc;
  border: 1px solid #d9e3ef;
  border-radius: 22px;
  box-shadow: 0 12px 30px rgba(88, 115, 155, 0.08);
}

.agent-sidebar {
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.sidebar-header {
  padding: 22px 22px 16px;
  border-bottom: 1px solid #dde6f2;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.sidebar-kicker {
  font-size: 12px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #7d8da3;
}

.sidebar-header h2,
.chat-header h3 {
  margin: 0;
  font-size: 28px;
  color: #1f2b3d;
}

.session-list {
  flex: 1;
  overflow-y: auto;
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.session-item {
  width: 100%;
  text-align: left;
  border: 1px solid #dce7f4;
  border-radius: 16px;
  padding: 14px;
  background: #ffffff;
  cursor: pointer;
}

.session-item.active {
  border-color: #2c67d9;
  background: linear-gradient(180deg, #f1f6ff 0%, #ffffff 100%);
  box-shadow: 0 10px 24px rgba(44, 103, 217, 0.12);
}

.session-title {
  font-size: 15px;
  font-weight: 600;
  color: #21324a;
}

.session-preview {
  margin-top: 6px;
  font-size: 13px;
  line-height: 1.5;
  color: #6b7a90;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.session-meta {
  margin-top: 10px;
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: #8a97aa;
}

.session-empty {
  padding: 24px 16px;
  border-radius: 16px;
  background: #fff;
  color: #7d8da3;
  text-align: center;
}

.agent-main {
  display: grid;
  grid-template-rows: auto 1fr auto;
  overflow: hidden;
}

.chat-header {
  padding: 24px 26px 18px;
  border-bottom: 1px solid #dde6f2;
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
}

.chat-header p {
  margin: 8px 0 0;
  color: #76879d;
}

.chat-header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.model-pill {
  padding: 8px 12px;
  border-radius: 999px;
  background: #ebf2ff;
  color: #2b5ebc;
  font-size: 13px;
}

.chat-body {
  overflow-y: auto;
  padding: 22px 24px;
  background:
    radial-gradient(circle at top right, rgba(80, 145, 255, 0.08), transparent 22%),
    linear-gradient(180deg, #f8fbff 0%, #f4f8fc 100%);
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.chat-empty {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100%;
}

.empty-card {
  width: min(680px, 100%);
  padding: 30px;
  border-radius: 22px;
  background: rgba(255, 255, 255, 0.92);
  border: 1px solid #dbe6f2;
}

.empty-card h4 {
  margin: 0 0 16px;
  font-size: 20px;
  color: #223249;
}

.empty-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.prompt-chip {
  border: 1px solid #d8e3f1;
  border-radius: 999px;
  background: #f7faff;
  padding: 12px 16px;
  color: #27456f;
  cursor: pointer;
}

.message-row {
  display: flex;
}

.message-row.is-user {
  justify-content: flex-end;
}

.message-bubble {
  max-width: min(760px, 82%);
  padding: 14px 16px;
  border-radius: 18px;
  box-shadow: 0 10px 24px rgba(58, 88, 128, 0.08);
}

.is-user .message-bubble {
  background: linear-gradient(135deg, #2f67d4 0%, #4179e3 100%);
  color: #fff;
}

.is-assistant .message-bubble {
  background: #fff;
  color: #243449;
  border: 1px solid #dce6f2;
}

.message-role {
  font-size: 12px;
  margin-bottom: 6px;
  opacity: 0.7;
}

.message-text {
  white-space: pre-wrap;
  line-height: 1.7;
}

.pending-actions {
  margin-top: 12px;
  display: grid;
  gap: 10px;
}

.pending-action-card {
  padding: 12px;
  border-radius: 14px;
  background: #f2f7ff;
  border: 1px solid #d7e4fb;
}

.pending-action-form {
  display: grid;
  gap: 8px;
  margin-top: 8px;
}

.pending-action-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.pending-action-hint {
  font-size: 12px;
  line-height: 1.5;
  color: #5f6b7a;
}

:deep(.pending-action-confirm-btn) {
  min-width: auto;
}

.pending-action-title {
  margin-bottom: 6px;
  font-weight: 700;
  color: #1f2a44;
}

.pending-action-desc {
  margin-bottom: 10px;
  line-height: 1.6;
  font-size: 13px;
  color: #5b6b82;
}

.manual-quote-section {
  margin-top: 8px;
  padding: 10px;
  border-radius: 10px;
  background: #ffffff;
  border: 1px solid #e3ecf7;
}

.manual-quote-section-title {
  font-size: 13px;
  font-weight: 600;
  color: #2b3a55;
  margin-bottom: 8px;
}

.manual-quote-table {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.manual-quote-table-header,
.manual-quote-table-row {
  display: grid;
  grid-template-columns: 1.2fr 1.4fr 1.2fr 0.8fr 1fr;
  gap: 6px;
  font-size: 12px;
}

.manual-quote-table-header {
  color: #6b7a90;
  font-weight: 600;
  padding: 4px 6px;
  background: #f4f8fc;
  border-radius: 6px;
}

.manual-quote-table-row {
  padding: 4px 6px;
  color: #3a4a63;
  border-bottom: 1px dashed #e6eef7;
}

.manual-quote-table-row:last-child {
  border-bottom: none;
}

.manual-supplier-row {
  padding: 8px 6px;
  border-bottom: 1px dashed #e6eef7;
}

.manual-supplier-row:last-child {
  border-bottom: none;
}

.manual-supplier-name {
  font-size: 13px;
  font-weight: 600;
  color: #2b3a55;
}

.manual-supplier-meta {
  margin-top: 4px;
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  font-size: 12px;
  color: #6b7a90;
}

.manual-supplier-reason {
  margin-top: 4px;
  font-size: 12px;
  color: #8a97aa;
}

.manual-quote-tip {
  margin-top: 8px;
  padding: 8px 10px;
  background: #fff8e6;
  border: 1px solid #f3e2b3;
  border-radius: 8px;
  color: #8a6d2b;
}

.loading-bubble {
  min-width: 90px;
}

.typing-dots {
  display: flex;
  gap: 6px;
  padding-top: 6px;
}

.typing-dots span {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: #4a73b8;
  animation: typing 1s infinite ease-in-out;
}

.typing-dots span:nth-child(2) {
  animation-delay: 0.15s;
}

.typing-dots span:nth-child(3) {
  animation-delay: 0.3s;
}

.chat-footer {
  padding: 18px 24px 22px;
  border-top: 1px solid #dde6f2;
  background: #f9fbfe;
}

.chat-input {
  width: 100%;
  resize: none;
  border: 1px solid #cfdbeb;
  border-radius: 18px;
  background: #fff;
  padding: 14px 16px;
  box-sizing: border-box;
  font: inherit;
  outline: none;
}

.chat-input:focus {
  border-color: #5183e6;
  box-shadow: 0 0 0 3px rgba(81, 131, 230, 0.12);
}

.chat-footer-bar {
  margin-top: 12px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.input-tip {
  color: #7d8da3;
  font-size: 13px;
}

@keyframes typing {
  0%, 80%, 100% {
    transform: scale(0.7);
    opacity: 0.5;
  }
  40% {
    transform: scale(1);
    opacity: 1;
  }
}

@media (max-width: 1024px) {
  .agent-shell {
    grid-template-columns: 1fr;
    height: auto;
  }

  .agent-sidebar {
    max-height: 280px;
  }

  .chat-header,
  .chat-footer-bar {
    flex-direction: column;
    align-items: flex-start;
  }

  .message-bubble {
    max-width: 100%;
  }
}
</style>
