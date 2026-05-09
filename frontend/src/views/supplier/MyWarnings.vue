<template>
  <div class="my-warnings-container">
    <div class="header">
      <h2>发货预警通知</h2>
      <el-button type="primary" :icon="Refresh" circle @click="fetchMessages" :loading="loading" />
    </div>

    <div v-loading="loading">
      <el-empty v-if="messages.length === 0" description="暂无预警通知" />

      <div v-else class="message-list">
        <el-card
          v-for="msg in messages"
          :key="msg.id"
          class="message-card"
          :class="{ 'is-unread': !msg.is_read }"
          shadow="hover"
        >
          <template #header>
            <div class="card-header">
              <div class="header-left">
                <el-icon class="warning-icon" :class="{ 'unread-icon': !msg.is_read }"><WarningFilled /></el-icon>
                <span class="time">{{ formatDateTime(msg.created_at) }}</span>
              </div>
              <div class="header-right">
                <el-tag v-if="!msg.is_read" type="danger" effect="dark" size="small" round>未读</el-tag>
                <el-tag v-else type="info" effect="plain" size="small" round>已读</el-tag>
              </div>
            </div>
          </template>

          <div class="message-content">
            <div class="message-header-text">{{ parseContent(msg.content).header }}</div>
            <el-table 
              v-if="parseContent(msg.content).items.length > 0" 
              :data="parseContent(msg.content).items" 
              size="small" 
              border 
              style="margin-top: 10px; width: 100%"
            >
              <el-table-column prop="material" label="物料名称" min-width="180" />
              <el-table-column prop="qty" label="欠交数量" width="120" align="center">
                <template #default="{row}">
                  <span style="color: #F56C6C; font-weight: bold;">{{ row.qty }}</span>
                </template>
              </el-table-column>
              <el-table-column prop="date" label="要求交期" width="150" align="center" />
            </el-table>
            <pre v-else>{{ msg.content }}</pre>
          </div>

          <!-- 已读和备注信息展示区 -->
          <div class="message-footer" v-if="msg.is_read">
            <el-divider border-style="dashed" />
            <div class="read-status">
              <span class="read-time">读取时间：{{ formatDateTime(msg.read_at) }}</span>
              <div class="remark-box" v-if="msg.supplier_remark">
                <span class="remark-label">您的备注：</span>
                <span class="remark-text">{{ msg.supplier_remark }}</span>
              </div>
            </div>
          </div>

          <!-- 未读操作区 -->
          <div class="card-actions" v-if="!msg.is_read">
            <el-button type="primary" @click="openRemarkDialog(msg)">
              标为已读并回复
            </el-button>
          </div>
        </el-card>
      </div>
    </div>

    <!-- 填写备注弹窗 -->
    <el-dialog v-model="remarkDialogVisible" title="确认预警通知" width="500px">
      <el-form label-position="top">
        <el-form-item label="回复/备注 (选填)">
          <el-input
            v-model="remarkContent"
            type="textarea"
            :rows="4"
            placeholder="您可以告知采购员预计发货时间或延迟原因..."
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="remarkDialogVisible = false">取 消</el-button>
          <el-button type="primary" @click="handleMarkRead" :loading="submitting">
            确 定
          </el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getMyWarningMessages, markWarningMessageRead } from '../../api/warning'
import { ElMessage } from 'element-plus'
import { Refresh, WarningFilled } from '@element-plus/icons-vue'

const loading = ref(false)
const messages = ref([])
const remarkDialogVisible = ref(false)
const remarkContent = ref('')
const currentMsgId = ref(null)
const submitting = ref(false)

const formatDateTime = (dateStr) => {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString()
}

const parseContent = (content) => {
  if (!content) return { header: '', items: [] }
  const lines = content.split('\n').filter(line => line.trim())
  const header = lines[0]
  const items = []
  
  for (let i = 1; i < lines.length; i++) {
    const line = lines[i]
    if (line.startsWith('- 物料：')) {
      const parts = line.split('，')
      let material = '', qty = '', date = ''
      parts.forEach(part => {
        if (part.includes('物料：')) material = part.replace('- 物料：', '').trim()
        if (part.includes('欠交数量：')) qty = part.replace('欠交数量：', '').trim()
        if (part.includes('要求交期：')) date = part.replace('要求交期：', '').trim()
      })
      items.push({ material, qty, date })
    }
  }
  return { header, items }
}

const fetchMessages = async () => {
  loading.value = true
  try {
    const res = await getMyWarningMessages()
    messages.value = res.data.sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
  } catch (error) {
    console.error('Failed to fetch messages:', error)
    ElMessage.error('获取预警通知失败')
  } finally {
    loading.value = false
  }
}

const openRemarkDialog = (msg) => {
  currentMsgId.value = msg.id
  remarkContent.value = ''
  remarkDialogVisible.value = true
}

const handleMarkRead = async () => {
  submitting.value = true
  try {
    await markWarningMessageRead(currentMsgId.value, { remark: remarkContent.value })
    ElMessage.success('已标记为已读并回复')
    const msg = messages.value.find((m) => m.id === currentMsgId.value)
    if (msg) {
      msg.is_read = true
      msg.read_at = new Date().toISOString()
      msg.supplier_remark = remarkContent.value
    }
    remarkDialogVisible.value = false
  } catch (error) {
    console.error('Failed to mark as read:', error)
    ElMessage.error('操作失败')
  } finally {
    submitting.value = false
  }
}

onMounted(() => {
  fetchMessages()
})
</script>

<style scoped>
.my-warnings-container {
  padding: 20px;
  max-width: 900px;
  margin: 0 auto;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.header h2 {
  margin: 0;
  color: #303133;
  font-size: 22px;
}

.message-list {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.message-card {
  border-radius: 10px;
  border: 1px solid #ebeef5;
}

:deep(.message-card .el-card__header) {
  padding: 12px 20px;
  background-color: #fafafa;
  border-bottom: 1px solid #ebeef5;
}

.message-card.is-unread {
  border-left: 5px solid #f56c6c;
}

.message-card:not(.is-unread) {
  border-left: 5px solid #909399;
  opacity: 0.85;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.warning-icon {
  font-size: 18px;
  color: #909399;
}

.unread-icon {
  color: #f56c6c;
}

.time {
  color: #606266;
  font-size: 14px;
  font-weight: 500;
}

.message-content {
  color: #303133;
  font-size: 14px;
  line-height: 1.8;
  padding: 5px 0;
}

.message-content pre {
  margin: 0;
  white-space: pre-wrap;
  font-family: inherit;
  background: #f8f9fa;
  padding: 15px;
  border-radius: 6px;
  border: 1px solid #f0f0f0;
}

.message-footer {
  margin-top: 10px;
}

.read-status {
  display: flex;
  flex-direction: column;
  gap: 8px;
  font-size: 13px;
}

.read-time {
  color: #909399;
}

.remark-box {
  background-color: #f0f9eb;
  padding: 10px 15px;
  border-radius: 6px;
  border-left: 3px solid #67c23a;
  color: #606266;
}

.remark-label {
  font-weight: bold;
  color: #67c23a;
}

.card-actions {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}

@media (max-width: 768px) {
  .my-warnings-container {
    padding: 10px;
  }
  .message-content pre {
    padding: 10px;
    font-size: 13px;
  }
}
</style>
