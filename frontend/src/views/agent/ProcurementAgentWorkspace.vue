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
  }))

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
    })

    const newSessionId = data?.session_id || targetSessionId
    currentSessionId.value = newSessionId
    pendingSessionId.value = ''
    messages.value.push({
      id: `${Date.now()}_assistant`,
      role: 'assistant',
      content: data?.answer || '采购助手暂时没有返回内容。',
      created_at: Math.floor(Date.now() / 1000),
    })
    await refreshSessions(newSessionId)
    scrollToBottom()
  } catch (error) {
    messages.value.push({
      id: `${Date.now()}_error`,
      role: 'assistant',
      content: error.response?.data?.detail || '采购助手暂时不可用，请稍后重试。',
      created_at: Math.floor(Date.now() / 1000),
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
