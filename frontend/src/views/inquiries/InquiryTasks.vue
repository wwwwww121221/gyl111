<template>
  <div class="page-container">
    <el-tabs v-model="activeTaskType" @tab-change="handleTaskTypeChange" class="task-type-tabs">
      <el-tab-pane label="自动询价任务" name="auto"></el-tab-pane>
      <el-tab-pane label="手动询价任务" name="manual"></el-tab-pane>
    </el-tabs>

    <div class="content-card" style="height: calc(100% - 50px);">
      <div class="toolbar">
        <div class="toolbar-left">
          <el-input
            v-model="searchQuery"
            placeholder="搜索任务标题..."
            :prefix-icon="Search"
            clearable
            style="width: 250px;"
          />
        </div>
        <div class="toolbar-right">
          <el-select v-model="statusFilter" clearable placeholder="按状态筛选" style="width: 180px;">
            <el-option v-for="item in statusFilterOptions" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
          <el-button type="primary" @click="fetchTasks" :icon="Refresh" circle />
        </div>
      </div>

      <div class="table-container">
        <el-table 
          v-loading="loadingTasks" 
          :data="filteredTaskList" 
          border 
          stripe 
          highlight-current-row
          style="width: 100%"
          height="100%"
        >
          <el-table-column type="index" label="序号" width="80" align="center" />
          <el-table-column prop="title" label="任务标题" />
          <el-table-column prop="buyer_name" label="负责采购员" width="120" align="center" v-if="isAdminLike" />
          <el-table-column prop="buyer_department" label="所属部门" width="120" align="center" v-if="isAdminLike" />
          <el-table-column prop="deadline" label="截止时间" width="190" align="center">
            <template #default="scope">
              <div>{{ formatDateTime(scope.row.deadline) }}</div>
              <el-tag v-if="hasTaskExpired(scope.row)" type="danger" size="small" effect="plain">已逾期</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="status" label="状态" width="120">
            <template #default="scope">
              <el-tag :type="getTaskStatusType(getTaskDisplayStatus(scope.row))">
                {{ getTaskStatusLabel(getTaskDisplayStatus(scope.row)) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="created_at" label="创建时间" width="180">
            <template #default="scope">
              {{ formatDateTime(scope.row.created_at) }}
            </template>
          </el-table-column>
          <el-table-column label="操作" width="420" align="left">
            <template #default="scope">
              <div class="task-table-action-group">
                <template v-if="canApproveTask(scope.row)">
                  <el-button size="small" type="success" class="task-action-secondary-btn" @click="openApprovalDialog(scope.row, 'approve')">
                    审批通过
                  </el-button>
                  <el-button size="small" type="danger" plain class="task-action-secondary-btn" @click="openApprovalDialog(scope.row, 'reject')">
                    驳回
                  </el-button>
                </template>
                <el-button
                  v-if="canResubmitTask(scope.row)"
                  size="small"
                  type="warning"
                  plain
                  class="task-action-secondary-btn"
                  @click="openResubmitDialog(scope.row)"
                >
                  重新提交
                </el-button>
                <template v-if="scope.row.type === 'manual'">
                  <el-button
                    size="small"
                    type="primary"
                    class="task-action-primary-btn"
                    :disabled="isTaskApprovalPending(scope.row)"
                    @click="goToCompare(scope.row)"
                  >
                    {{ isTaskCompareResultReadonly(scope.row) ? '查看比价结果' : '智能比价' }}
                  </el-button>
                  <el-button
                    v-if="scope.row.status !== 'closed'"
                    size="small"
                    type="success"
                    plain
                    class="task-action-secondary-btn"
                    @click="handleFinishManualTask(scope.row)"
                  >
                    结束流程
                  </el-button>
                </template>
                <template v-else>
                  <el-button size="small" type="primary" class="task-action-primary-btn" @click="viewTaskDetails(scope.row)">
                    详情 / 管理
                  </el-button>
                  <el-button
                    v-if="scope.row.compare_ready"
                    size="small"
                    type="warning"
                    class="task-action-secondary-btn"
                    @click="openAutoAllocationTab(scope.row)"
                  >
                    份额分配
                  </el-button>
                </template>

                <el-button
                  v-if="scope.row.status === 'closed'"
                  size="small"
                  type="danger"
                  plain
                  class="task-action-secondary-btn"
                  @click="handleDeleteTask(scope.row)"
                >
                  删除
                </el-button>
              </div>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </div>

    <!-- Dialog: Task Details -->
    <el-dialog
      v-model="detailsVisible"
      title="询价任务详情"
      width="85%"
      top="5vh"
      class="custom-dialog"
      draggable
      overflow
    >
      <div v-if="currentTaskDetails" v-loading="loadingDetails" class="task-details-container">
        
        <!-- Header Info Card -->
        <el-card shadow="never" class="info-card">
          <template #header>
            <div class="card-header">
              <div class="header-title">
                <span class="task-title">{{ currentTaskDetails.title }}</span>
                <el-tag :type="getTaskStatusType(currentTaskDisplayStatus)" effect="dark" size="default" style="margin-left: 15px;">
                  {{ getTaskStatusLabel(currentTaskDisplayStatus) }}
                </el-tag>
                <el-tag v-if="hasTaskExpired(currentTaskDetails)" type="danger" effect="plain" size="default" style="margin-left: 8px;">
                  已逾期
                </el-tag>
              </div>
              <div class="header-actions">
                <el-button
                  v-if="canApproveTask(currentTaskDetails)"
                  type="success"
                  @click="openApprovalDialog(currentTaskDetails, 'approve')"
                >
                  审批通过
                </el-button>
                <el-button
                  v-if="canApproveTask(currentTaskDetails)"
                  type="danger"
                  plain
                  @click="openApprovalDialog(currentTaskDetails, 'reject')"
                >
                  驳回
                </el-button>
                <el-button
                  v-if="canResubmitTask(currentTaskDetails)"
                  type="warning"
                  plain
                  @click="openResubmitDialog(currentTaskDetails)"
                >
                  重新提交审核
                </el-button>
                <el-button
                  v-if="isCurrentTaskCompareReady"
                  type="warning"
                  @click="openCurrentTaskAllocationTab"
                >
                  前往份额分配
                </el-button>
                <el-button v-if="currentTaskDisplayStatus === 'active'" type="danger" plain @click="handleCloseTask()">
                  终止任务 (流标)
                </el-button>
              </div>
            </div>
          </template>
          <el-descriptions :column="4" border size="small">
            <el-descriptions-item label="负责采购员">
              {{ currentTaskDetails.buyer_name || '-' }}
            </el-descriptions-item>
            <el-descriptions-item label="所属部门">
              {{ currentTaskDetails.buyer_department || '-' }}
            </el-descriptions-item>
            <el-descriptions-item label="审批人">
              {{ currentTaskDetails.approver_name || '待审批' }}
            </el-descriptions-item>
            <el-descriptions-item label="审批时间">
              {{ formatDateTime(currentTaskDetails.approved_at) }}
            </el-descriptions-item>
            <el-descriptions-item label="期望单价(¥)">
              <span style="color: #f56c6c; font-weight: bold; font-size: 16px;">详见下方明细</span>
            </el-descriptions-item>
            <el-descriptions-item label="最大自动谈判轮次">
              <el-tag type="info" size="small">{{ currentTaskDetails.strategy_config?.max_rounds }} 轮</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="AI 期望降价幅度">
              <el-tag type="warning" size="small">{{ (currentTaskDetails.strategy_config?.bargain_ratio * 100).toFixed(0) }}%</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="截止时间">
              {{ formatDateTime(currentTaskDetails.deadline) }}
            </el-descriptions-item>
            <el-descriptions-item label="剩余时间" :span="3">
              <span :class="['countdown-text', { 'countdown-urgent': isDetailDeadlineUrgent }]">
                {{ detailCountdownText }}
              </span>
            </el-descriptions-item>
            <el-descriptions-item label="审批意见" :span="4">
              {{ currentTaskDetails.approval_comment || '-' }}
            </el-descriptions-item>
            <el-descriptions-item label="采购员提交说明" :span="4">
              {{ currentTaskDetails.buyer_comment || '-' }}
            </el-descriptions-item>
          </el-descriptions>
        </el-card>

        <el-alert
          v-if="currentTaskDetails.buyer_comment"
          type="info"
          :closable="false"
          show-icon
          class="buyer-comment-alert"
        >
          <template #title>
            <span class="buyer-comment-title">采购员提交说明</span>
          </template>
          <div class="buyer-comment-content">{{ currentTaskDetails.buyer_comment }}</div>
        </el-alert>

        <el-card
          v-if="currentTaskDetails.buyer_comment_history?.length"
          shadow="never"
          class="info-card"
        >
          <template #header>
            <div class="card-header">
              <span>采购员历史意见</span>
            </div>
          </template>
          <div class="buyer-comment-history">
            <div
              v-for="(historyItem, index) in currentTaskDetails.buyer_comment_history"
              :key="`${historyItem.submitted_at || 'history'}_${index}`"
              class="buyer-comment-history-item"
            >
              <div class="buyer-comment-history-meta">
                <span>{{ getBuyerCommentActionLabel(historyItem.action) }}</span>
                <span>{{ historyItem.submitted_by || currentTaskDetails.buyer_name || '-' }}</span>
                <span>{{ formatDateTime(historyItem.submitted_at) }}</span>
              </div>
              <div class="buyer-comment-history-content">{{ historyItem.comment }}</div>
            </div>
          </div>
        </el-card>

        <el-card v-if="currentTaskDetails.proposed_suppliers?.length" shadow="never" class="info-card">
          <template #header>
            <div class="card-header">
              <span>拟发起供应商名单</span>
            </div>
          </template>
          <div class="proposed-supplier-list">
            <el-tag v-for="supplier in currentTaskDetails.proposed_suppliers" :key="supplier.supplier_id" type="info" effect="plain">
              {{ supplier.supplier_name }}<span v-if="supplier.supplier_code">（{{ supplier.supplier_code }}）</span>
            </el-tag>
          </div>
        </el-card>

        <el-card v-if="currentTaskDetails.attachments?.length" shadow="never" class="info-card">
          <template #header>
            <div class="card-header">
              <span>询价附件</span>
            </div>
          </template>
          <div class="task-attachment-list">
            <div
              v-for="(attachment, index) in currentTaskDetails.attachments"
              :key="`${attachment.file_path || 'attachment'}_${index}`"
              class="task-attachment-item"
            >
              <a
                href="#"
                class="task-attachment-link"
                @click.prevent="previewAttachment(attachment)"
              >
                {{ attachment.name }}
              </a>
              <span class="task-attachment-meta">
                {{ formatFileSize(attachment.size) }}
              </span>
              <span class="task-attachment-meta">
                {{ formatDateTime(attachment.uploaded_at) }}
              </span>
              <el-button type="primary" link @click="previewAttachment(attachment)">预览</el-button>
              <el-button type="primary" link @click="openAttachmentInNewTab(attachment)">新窗口打开</el-button>
            </div>
          </div>
        </el-card>

        <el-alert
          v-if="isCurrentTaskCompareReady"
          :title="compareReadyAlertTitle"
          type="warning"
          :closable="false"
          show-icon
          class="awaiting-award-alert"
        />

        <!-- Main Content Tabs -->
        <el-tabs v-model="detailsActiveTab" class="details-tabs" type="border-card">
          
          <!-- Tab 1: Suppliers -->
          <el-tab-pane name="suppliers">
            <template #label>
              <span class="tab-label-with-status">
                <span>供应商与报价动态</span>
                <el-tag
                  v-if="isCurrentTaskCompareReady"
                  size="small"
                  type="warning"
                  effect="plain"
                >
                  待份额分配
                </el-tag>
              </span>
            </template>
            <div class="tab-toolbar">
              <el-form :inline="true" :model="supplierForm" class="supplier-form" size="default">
                <el-form-item label="新增供应商">
                  <el-input v-model="supplierForm.name" placeholder="输入供应商名称" style="width: 200px;" />
                </el-form-item>
                <el-form-item>
                  <el-button type="primary" @click="handleAddSupplier" :loading="addingSupplier" :disabled="currentTaskDisplayStatus !== 'active'">
                    添加供应商
                  </el-button>
                </el-form-item>
              </el-form>
            </div>

            <el-table :data="currentTaskDetails.links" border stripe style="width: 100%">
              <el-table-column type="expand">
                <template #default="props">
                  <div class="expand-content">
                    <template v-if="props.row.material_allocations && props.row.material_allocations.length > 0">
                      <h4 class="expand-title">
                        <el-icon style="vertical-align: middle; margin-right: 5px;"><DocumentCopy /></el-icon>物料分配详情
                      </h4>
                      <el-table :data="props.row.material_allocations" border size="small" style="margin-bottom: 16px;">
                        <el-table-column prop="material_name" label="物料名称" min-width="180" />
                        <el-table-column prop="material_code" label="物料编码" width="150" />
                        <el-table-column prop="base_qty" label="原始数量" width="100" align="right" />
                        <el-table-column prop="allocated_qty" label="分配数量" width="100" align="right" />
                        <el-table-column prop="allocated_ratio" label="分配占比" width="100" align="right">
                          <template #default="scope">
                            {{ Number(scope.row.allocated_ratio || 0).toFixed(2) }}%
                          </template>
                        </el-table-column>
                        <el-table-column label="成交单价(¥)" width="120" align="right">
                          <template #default="scope">
                            {{ Number(scope.row.price || 0).toFixed(2) }}
                          </template>
                        </el-table-column>
                        <el-table-column label="分配金额(¥)" width="120" align="right">
                          <template #default="scope">
                            {{ Number(scope.row.amount || 0).toFixed(2) }}
                          </template>
                        </el-table-column>
                        <el-table-column prop="delivery_date" label="交期" width="140" align="center">
                          <template #default="scope">
                            {{ formatDate(scope.row.delivery_date) }}
                          </template>
                        </el-table-column>
                      </el-table>
                    </template>
                    <h4 class="expand-title"><el-icon style="vertical-align: middle; margin-right: 5px;"><DocumentCopy /></el-icon>历史报价记录</h4>
                    <el-timeline style="padding-top: 10px;">
                      <el-timeline-item
                        v-for="(quotes, round) in props.row.quotes"
                        :key="round"
                        :timestamp="`第 ${round} 轮报价`"
                        placement="top"
                        type="primary"
                      >
                        <el-card shadow="hover" body-style="padding: 10px;">
                          <el-table :data="quotes" :row-class-name="getQuoteRowClassName" border size="small">
                            <el-table-column prop="item_id" label="明细项ID" width="100" align="center" />
                            <el-table-column prop="qty" label="可供数量" width="100" align="center" />
                            <el-table-column prop="delivery_date" label="承诺交期" width="120" align="center">
                              <template #default="scope">
                                {{ formatDate(scope.row.delivery_date) }}
                              </template>
                            </el-table-column>
                            <el-table-column label="单价(¥)" width="150" align="right">
                              <template #default="scope">
                                <span style="color: #f56c6c; font-weight: bold;">{{ Number(scope.row.price).toFixed(2) }}</span>
                                <el-tooltip
                                  v-if="scope.row.is_anomaly"
                                  :content="scope.row.anomaly_reason"
                                  placement="top"
                                  effect="light"
                                >
                                  <el-icon color="#e6a23c" style="margin-left: 5px; cursor: pointer; vertical-align: middle;">
                                    <Warning />
                                  </el-icon>
                                </el-tooltip>
                              </template>
                            </el-table-column>
                            <el-table-column prop="remark" label="备注说明" />
                          </el-table>
                        </el-card>
                      </el-timeline-item>
                    </el-timeline>
                    <el-empty v-if="!props.row.quotes || Object.keys(props.row.quotes).length === 0" description="暂无报价记录" :image-size="60"></el-empty>
                  </div>
                </template>
              </el-table-column>

              <el-table-column prop="supplier_name" label="供应商名称" min-width="150" />
              <el-table-column prop="status" label="当前状态" width="120" align="center">
                <template #default="scope">
                  <el-tag :type="getLinkStatusType(scope.row.status)" effect="light">{{ getLinkStatusText(scope.row.status) }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="current_round" label="当前轮次" width="100" align="center" />
              <el-table-column label="本轮总价(¥)" width="120" align="right">
                <template #default="scope">
                  <span v-if="scope.row.total_price > 0" style="font-weight: bold;">{{ Number(scope.row.total_price).toFixed(2) }}</span>
                  <span v-else>-</span>
                </template>
              </el-table-column>
              <el-table-column label="平均交期(天)" width="110" align="center">
                <template #default="scope">
                  <span v-if="scope.row.avg_delivery_days > 0">{{ Number(scope.row.avg_delivery_days).toFixed(1) }}</span>
                  <span v-else>-</span>
                </template>
              </el-table-column>
              <el-table-column label="综合评分" width="120" align="center">
                <template #default="scope">
                  <span v-if="scope.row.total_score > 0" style="color: #409EFF; font-weight: bold; font-size: 15px;">
                    {{ Number(scope.row.total_score).toFixed(2) }}
                  </span>
                  <span v-else>-</span>
                </template>
              </el-table-column>
              <el-table-column label="当前排名" width="90" align="center">
                <template #default="scope">
                  <el-tag v-if="scope.row.score_rank" :type="scope.row.score_rank === 1 ? 'danger' : 'info'" effect="dark">
                    第 {{ scope.row.score_rank }} 名
                  </el-tag>
                  <span v-else>-</span>
                </template>
              </el-table-column>

              <el-table-column label="操作" width="260" align="center" fixed="right">
                <template #default="scope">
                  <el-button 
                    v-if="currentTaskDisplayStatus === 'active' && !['deal', 'reject', 'locked'].includes(scope.row.status)" 
                    size="small" 
                    type="success" 
                    plain
                    @click="handleCloseTask(scope.row.link_id)">
                    选定成交
                  </el-button>
                  <span v-else-if="scope.row.status === 'deal'" style="color: #67c23a; font-weight: bold;">已成交</span>
                  <span v-else-if="scope.row.status === 'locked'" style="color: #409eff; font-weight: bold;">已锁定</span>
                  <span v-else-if="scope.row.status === 'reject'" style="color: #909399;">已淘汰</span>
                  <span v-else>-</span>
                  <el-button
                    v-if="currentTaskDisplayStatus === 'active' && scope.row.status === 'negotiation'"
                    size="small"
                    type="warning"
                    plain
                    @click="openManualInterventionDialog(scope.row, 'continue')"
                  >
                    人工通过
                  </el-button>
                  <el-button
                    v-if="currentTaskDisplayStatus === 'active' && scope.row.status === 'negotiation'"
                    size="small"
                    type="danger"
                    plain
                    @click="openManualInterventionDialog(scope.row, 'reject')"
                  >
                    人工淘汰
                  </el-button>
                </template>
              </el-table-column>
            </el-table>
          </el-tab-pane>

          <el-tab-pane v-if="isAutoAllocationAvailable" name="allocation">
            <template #label>
              <span class="tab-label-with-status">
                <span>份额分配</span>
                <el-tag
                  v-if="isCurrentTaskCompareReady"
                  size="small"
                  :type="isAutoAllocationReadonly ? 'info' : 'warning'"
                  effect="plain"
                >
                  {{ isAutoAllocationReadonly ? '历史结果' : '待定标' }}
                </el-tag>
              </span>
            </template>

            <div class="auto-allocation-wrap">
              <el-alert
                :title="isAutoAllocationReadonly ? '当前页展示的是历史分配结果，不能再修改。' : '自动询价已结束，请直接在当前页面完成每个物料的份额分配。'"
                :type="isAutoAllocationReadonly ? 'info' : 'warning'"
                :closable="false"
                show-icon
                class="auto-allocation-alert"
              />

              <div class="allocation-strategy-toolbar global-allocation-toolbar">
                <el-button @click="applyAllocationStrategyToAll('common')" :disabled="isAutoAllocationReadonly">全额给常用 (100%)</el-button>
                <div class="pressure-strategy-group">
                  <el-button type="warning" @click="applyAllocationStrategyToAll('pressure')" :disabled="isAutoAllocationReadonly">价格压迫策略</el-button>
                  <div class="pressure-ratio-group">
                    <span class="pressure-ratio-label">常用占%</span>
                    <el-input-number
                      v-model="pressureCommonRatio"
                      size="small"
                      :min="0"
                      :max="100"
                      :controls="false"
                      :disabled="isAutoAllocationReadonly"
                    />
                    <span class="pressure-ratio-label">最低价占%</span>
                    <el-input-number
                      v-model="pressureLowestRatio"
                      size="small"
                      :min="0"
                      :max="100"
                      :controls="false"
                      :disabled="isAutoAllocationReadonly"
                    />
                  </div>
                </div>
                <el-button type="success" @click="applyAllocationStrategyToAll('lowest')" :disabled="isAutoAllocationReadonly">价低者得 (100%)</el-button>
              </div>

              <el-card
                v-for="item in currentTaskDetails.items"
                :key="item.id"
                shadow="never"
                class="allocation-item-card"
              >
                <template #header>
                  <div class="allocation-item-header">
                    <div>
                      <div class="allocation-item-title">{{ item.material_name }}</div>
                      <div class="allocation-item-meta">
                        <span>物料编码：{{ item.material_code }}</span>
                        <span>需求数量：{{ item.qty }}</span>
                      </div>
                    </div>
                    <div class="allocation-item-actions">
                      <el-button size="small" @click="applyItemAllocationStrategy(item, 'common')" :disabled="isAutoAllocationReadonly">常用100%</el-button>
                      <el-button size="small" type="warning" @click="applyItemAllocationStrategy(item, 'pressure')" :disabled="isAutoAllocationReadonly">压迫策略</el-button>
                      <el-button size="small" type="success" @click="applyItemAllocationStrategy(item, 'lowest')" :disabled="isAutoAllocationReadonly">低价100%</el-button>
                    </div>
                  </div>
                </template>

                <el-table :data="getAllocationSuppliersForItem(item)" border stripe size="small">
                  <el-table-column prop="supplier_name" label="供应商名称" min-width="180">
                    <template #default="scope">
                      <div class="supplier-name-cell">
                        <span>{{ scope.row.supplier_name }}</span>
                        <el-tag
                          v-for="tag in scope.row.identity_tags"
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
                  <el-table-column prop="supplier_grade" label="评级" width="90" align="center" />
                  <el-table-column prop="status" label="状态" width="110" align="center">
                    <template #default="scope">
                      <el-tag :type="getLinkStatusType(scope.row.status)" effect="light">{{ getLinkStatusText(scope.row.status) }}</el-tag>
                    </template>
                  </el-table-column>
                  <el-table-column label="报价(元)" width="120" align="right">
                    <template #default="scope">
                      <span>{{ Number(scope.row.price || 0).toFixed(2) }}</span>
                    </template>
                  </el-table-column>
                  <el-table-column label="分配比例 (%)" width="180" align="center">
                    <template #default="scope">
                      <el-input-number
                        v-model="autoItemAllocations[item.id][scope.row.link_id]"
                        size="small"
                        :min="0"
                        :max="100"
                        :precision="0"
                        :step="5"
                        controls-position="right"
                        :disabled="isAutoAllocationReadonly"
                      />
                    </template>
                  </el-table-column>
                  <el-table-column label="分配数量" width="110" align="center">
                    <template #default="scope">
                      {{ getItemAllocatedQty(item, scope.row) }}
                    </template>
                  </el-table-column>
                </el-table>

                <div class="allocation-item-footer">
                  <span class="allocation-sum-text">当前分配总和：{{ getItemAllocationSum(item.id) }}%</span>
                  <span v-if="!isAutoAllocationReadonly && getItemAllocationSum(item.id) !== 100" class="allocation-warning">该物料分配总和必须等于 100%</span>
                </div>
              </el-card>

              <div v-if="!isAutoAllocationReadonly" class="allocation-submit-bar">
                <el-button type="primary" :disabled="!canSubmitAutoAllocations" :loading="submittingAutoAllocation" @click="submitAutoItemAllocations">
                  确认分配并生成合同
                </el-button>
              </div>
            </div>
          </el-tab-pane>

          <!-- Tab 2: Items -->
          <el-tab-pane label="询价明细 (Items)" name="items">
            <el-table :data="currentTaskDetails.items" border stripe size="small">
              <el-table-column prop="id" label="明细项ID" width="100" align="center" />
              <el-table-column prop="material_code" label="物料编码" width="150" />
              <el-table-column prop="material_name" label="物料名称" min-width="200" />
              <el-table-column prop="qty" label="需求数量" width="120" align="right" />
              <el-table-column prop="target_price" label="设定期望单价(¥)" width="150" align="right">
                <template #default="scope">
                  <span v-if="scope.row.target_price" style="color: #f56c6c; font-weight: bold;">{{ Number(scope.row.target_price).toFixed(2) }}</span>
                  <span v-else style="color: #909399;">不设限</span>
                </template>
              </el-table-column>
              <el-table-column prop="delivery_date" label="需求日期" width="150" align="center">
                <template #default="scope">{{ formatDate(scope.row.delivery_date) }}</template>
              </el-table-column>
            </el-table>
          </el-tab-pane>

        </el-tabs>
      </div>
    </el-dialog>

    <el-dialog
      v-model="attachmentPreviewVisible"
      title="附件预览"
      width="70%"
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
      v-model="manualInterventionDialogVisible"
      :title="manualInterventionMode === 'continue' ? '人工通过谈判' : '人工淘汰供应商'"
      width="520px"
      draggable
      overflow
    >
      <el-form :model="manualInterventionForm" label-width="92px">
        <el-form-item label="处理说明">
          <el-input
            v-model="manualInterventionForm.message"
            type="textarea"
            :rows="4"
            :placeholder="manualInterventionMode === 'continue' ? '请输入给供应商的人工复核反馈' : '请输入淘汰原因（将同步给供应商）'"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="manualInterventionDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="manualInterventionSubmitting" @click="submitManualIntervention">
          确认提交
        </el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="approvalDialogVisible"
      :title="approvalMode === 'approve' ? '审批通过' : '驳回询价申请'"
      width="520px"
      draggable
      overflow
    >
      <el-form :model="approvalForm" label-width="92px">
        <el-form-item label="审批意见">
          <el-input
            v-model="approvalForm.comment"
            type="textarea"
            :rows="4"
            :placeholder="approvalMode === 'approve' ? '请输入审批通过意见，可留空' : '请输入驳回原因'"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="approvalDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="approvalSubmitting" @click="submitTaskApproval">
          确认提交
        </el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="resubmitDialogVisible"
      title="重新提交经理审核"
      width="560px"
      draggable
      overflow
    >
      <el-form :model="resubmitForm" label-width="108px">
        <el-form-item label="提交说明">
          <el-input
            v-model="resubmitForm.comment"
            type="textarea"
            :rows="5"
            maxlength="300"
            show-word-limit
            placeholder="请补充调整原因、采购思路或需要经理再次关注的点"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="resubmitDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="resubmitSubmitting" @click="submitTaskResubmit">
          确认重新提交
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import { getInquiryTasks, addSupplierToTask, getTaskDetails, closeInquiryTask, updateTaskStatus, approveInquiryTask, rejectInquiryTask, resubmitInquiryTask } from '../../api/inquiry'
import api, { getApiOrigin } from '../../api/index'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh, DocumentCopy, Search, Warning } from '@element-plus/icons-vue'

const router = useRouter()
const userRole = computed(() => localStorage.getItem('role') || '')
const isAdminLike = computed(() => ['admin', 'buyer_manager'].includes(userRole.value))

const activeTaskType = ref('auto')
const loadingTasks = ref(false)
const taskList = ref([])
const searchQuery = ref('')
const statusFilter = ref('')
const statusFilterOptions = [
  { label: '待审批', value: 'pending_approval' },
  { label: '审批驳回', value: 'approval_rejected' },
  { label: '进行中', value: 'active' },
  { label: '待填写', value: 'pending_fill' },
  { label: '分析中', value: 'analyzing' },
  { label: '待份额分配', value: 'awaiting_award' },
  { label: '已结束', value: 'closed' }
]
const isTaskCompareResultReadonly = (task) => ['closed', 'cancelled'].includes(String(task?.status || '').toLowerCase())

const handleTaskTypeChange = () => {
  fetchTasks()
}

const getTaskDisplayStatus = (task) => task?.effective_status || task?.status || ''
const isTaskCompareReady = (task) => Boolean(task?.compare_ready)
const isTaskApprovalPending = (task) => ['pending_approval', 'approval_rejected'].includes(String(task?.status || '').toLowerCase())

const goToCompare = (task) => {
  if (isTaskApprovalPending(task)) {
    ElMessage.warning('当前任务尚未通过经理审批，暂不可进入智能比价')
    return
  }
  if (task.status === 'pending_fill') {
    updateTaskStatus(task.id, 'analyzing').then(() => {
      fetchTasks()
    }).catch(err => console.error(err))
  }
  router.push({
    name: 'IntelligentCompare',
    query: { taskId: task.id }
  })
}

const handleFinishManualTask = async (task) => {
  try {
    await ElMessageBox.confirm(`确定要结束任务 "${task.title}" 吗？该操作将按流标关闭任务，并同步结束供应商流程。`, '结束任务', {
      confirmButtonText: '确定结束',
      cancelButtonText: '取消',
      type: 'warning'
    })
    await closeInquiryTask(task.id)
    ElMessage.success('任务已按流标关闭')
    fetchTasks()
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('操作失败: ' + (e.response?.data?.detail || e.message))
    }
  }
}

const filteredTaskList = computed(() => {
  let result = taskList.value
  if (statusFilter.value) {
    result = result.filter(task => getTaskDisplayStatus(task) === statusFilter.value || String(task?.status || '') === statusFilter.value)
  }
  if (!searchQuery.value) return result
  return result.filter(task =>
    task.title.toLowerCase().includes(searchQuery.value.toLowerCase())
  )
})

const detailsVisible = ref(false)
const detailsActiveTab = ref('suppliers')
const currentTask = ref(null)
const currentTaskDetails = ref(null)
const attachmentPreviewVisible = ref(false)
const previewingAttachment = ref(null)
const loadingDetails = ref(false)
const addingSupplier = ref(false)
const supplierForm = reactive({
  name: '',
  contact: '',
  phone: ''
})
const manualInterventionDialogVisible = ref(false)
const manualInterventionSubmitting = ref(false)
const manualInterventionMode = ref('continue')
const manualInterventionLinkId = ref(null)
const manualInterventionForm = reactive({
  message: ''
})
const approvalDialogVisible = ref(false)
const approvalSubmitting = ref(false)
const approvalMode = ref('approve')
const approvalTargetTask = ref(null)
const approvalForm = reactive({
  comment: ''
})
const resubmitDialogVisible = ref(false)
const resubmitSubmitting = ref(false)
const resubmitTargetTask = ref(null)
const resubmitForm = reactive({
  comment: ''
})
const pressureCommonRatio = ref(80)
const pressureLowestRatio = ref(20)
const autoItemAllocations = ref({})
const topHistoricalSupplierMap = ref({})
const submittingAutoAllocation = ref(false)
const nowTs = ref(Date.now())
let timerId = null
let syncingPressureRatios = false

const fetchTasks = async () => {
  loadingTasks.value = true
  try {
    const res = await getInquiryTasks({ type: activeTaskType.value === 'auto' ? 'auto' : 'manual' })
    taskList.value = res.data || []
  } catch (error) {
    console.error(error)
    ElMessage.error('获取任务列表失败')
  } finally {
    loadingTasks.value = false
  }
}

const viewTaskDetails = async (task, preferredTab = 'suppliers') => {
  currentTask.value = task
  detailsActiveTab.value = preferredTab
  detailsVisible.value = true
  loadingDetails.value = true
  try {
    const res = await getTaskDetails(task.id)
    currentTaskDetails.value = res.data
    initializeAutoItemAllocations()
    if (currentTaskDetails.value?.type === 'auto') {
      await loadTopHistoricalSuppliers(currentTaskDetails.value)
    } else {
      topHistoricalSupplierMap.value = {}
    }
  } catch (error) {
    console.error(error)
    ElMessage.error('获取任务详情失败')
  } finally {
    loadingDetails.value = false
  }
}

const handleCloseTask = async (linkId = null) => {
  try {
    await closeInquiryTask(currentTaskDetails.value.id, linkId)
    ElMessage.success(linkId ? '已选定该供应商并自动关闭任务' : '任务已手动结束 (流标)')
    viewTaskDetails(currentTask.value)
    fetchTasks()
  } catch (error) {
    console.error(error)
    ElMessage.error('操作失败')
  }
}

const openAutoAllocationTab = async (task) => {
  await viewTaskDetails(task, 'allocation')
}

const openCurrentTaskAllocationTab = () => {
  if (!isAutoAllocationAvailable.value) return
  detailsActiveTab.value = 'allocation'
}

const handleDeleteTask = async (task) => {
  try {
    await ElMessageBox.confirm('确认删除该询价单吗？相关的报价记录将一并删除，且操作不可恢复。', '警告', {
      confirmButtonText: '确认删除',
      cancelButtonText: '取消',
      type: 'warning'
    })
    
    await api.delete(`/inquiry/tasks/${task.id}`)
    ElMessage.success('删除成功')
    fetchTasks()
  } catch (e) {
    if (e !== 'cancel') {
      console.error(e)
      ElMessage.error('删除失败')
    }
  }
}

const canApproveTask = (task) => {
  if (!task || !isAdminLike.value) return false
  return ['pending_approval', 'approval_rejected'].includes(String(task.status || '').toLowerCase())
}

const canResubmitTask = (task) => {
  if (!task || userRole.value !== 'buyer') return false
  return String(task.status || '').toLowerCase() === 'approval_rejected'
}

const openApprovalDialog = (task, mode) => {
  approvalTargetTask.value = task
  approvalMode.value = mode
  approvalForm.comment = ''
  approvalDialogVisible.value = true
}

const submitTaskApproval = async () => {
  if (!approvalTargetTask.value) return
  approvalSubmitting.value = true
  try {
    if (approvalMode.value === 'approve') {
      await approveInquiryTask(approvalTargetTask.value.id, { comment: approvalForm.comment || undefined })
      ElMessage.success('审批通过，任务已进入正式询价流程')
    } else {
      await rejectInquiryTask(approvalTargetTask.value.id, { comment: approvalForm.comment || undefined })
      ElMessage.success('已驳回该询价申请')
    }
    approvalDialogVisible.value = false
    await fetchTasks()
    if (detailsVisible.value && currentTaskDetails.value?.id === approvalTargetTask.value.id) {
      await viewTaskDetails(approvalTargetTask.value, detailsActiveTab.value)
    }
  } catch (error) {
    console.error(error)
    ElMessage.error(error.response?.data?.detail || '审批操作失败')
  } finally {
    approvalSubmitting.value = false
  }
}

const openResubmitDialog = (task) => {
  resubmitTargetTask.value = task
  resubmitForm.comment = task?.buyer_comment || currentTaskDetails.value?.buyer_comment || ''
  resubmitDialogVisible.value = true
}

const submitTaskResubmit = async () => {
  if (!resubmitTargetTask.value) return
  resubmitSubmitting.value = true
  try {
    await resubmitInquiryTask(resubmitTargetTask.value.id, {
      comment: (resubmitForm.comment || '').trim() || undefined
    })
    ElMessage.success('已重新提交经理审核')
    resubmitDialogVisible.value = false
    await fetchTasks()
    if (detailsVisible.value && currentTaskDetails.value?.id === resubmitTargetTask.value.id) {
      await viewTaskDetails(resubmitTargetTask.value, detailsActiveTab.value)
    }
  } catch (error) {
    console.error(error)
    ElMessage.error(error.response?.data?.detail || '重新提交失败')
  } finally {
    resubmitSubmitting.value = false
  }
}

const openManualInterventionDialog = (row, mode) => {
  manualInterventionMode.value = mode
  manualInterventionLinkId.value = row.link_id
  manualInterventionForm.message = ''
  manualInterventionDialogVisible.value = true
}

const submitManualIntervention = async () => {
  if (!currentTaskDetails.value || !manualInterventionLinkId.value) return
  manualInterventionSubmitting.value = true
  try {
    const endpoint = manualInterventionMode.value === 'continue' ? 'manual-continue' : 'manual-reject'
    await api.post(`/inquiry/tasks/${currentTaskDetails.value.id}/links/${manualInterventionLinkId.value}/${endpoint}`, {
      message: manualInterventionForm.message || null
    })
    ElMessage.success(manualInterventionMode.value === 'continue' ? '已人工通过，供应商可继续谈判' : '已人工淘汰该供应商')
    manualInterventionDialogVisible.value = false
    await viewTaskDetails(currentTask.value)
    await fetchTasks()
  } catch (error) {
    console.error(error)
    ElMessage.error('人工干预失败')
  } finally {
    manualInterventionSubmitting.value = false
  }
}

const handleAddSupplier = async () => {
  if (!supplierForm.name) {
    ElMessage.warning('请输入供应商名称')
    return
  }
  addingSupplier.value = true
  try {
    await addSupplierToTask(currentTask.value.id, {
      supplier_name: supplierForm.name,
      contact_person: supplierForm.contact,
      phone: supplierForm.phone
    })
    ElMessage.success(`供应商添加成功`)
    supplierForm.name = ''
    viewTaskDetails(currentTask.value)
  } catch (error) {
    console.error(error)
    ElMessage.error('添加供应商失败')
  } finally {
    addingSupplier.value = false
  }
}

const getLinkStatusType = (status) => {
  const map = {
    'sent': 'info',
    'quoted': 'primary',
    'negotiation': 'warning',
    'locked': 'success',
    'deal': 'success',
    'reject': 'danger'
  }
  return map[status] || ''
}

const getLinkStatusText = (status) => {
  const map = {
    'sent': '已发送(未报)',
    'quoted': '已报价',
    'negotiation': '谈判中',
    'locked': '已锁定',
    'deal': '已成交',
    'reject': '已淘汰'
  }
  return map[status] || status
}

const formatDateTime = (dateStr) => {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString()
}

const formatDate = (dateStr) => {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleDateString()
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

const formatFileSize = (size) => {
  const numericSize = Number(size || 0)
  if (!numericSize) return '-'
  if (numericSize < 1024) return `${numericSize} B`
  if (numericSize < 1024 * 1024) return `${(numericSize / 1024).toFixed(1)} KB`
  return `${(numericSize / (1024 * 1024)).toFixed(1)} MB`
}

const getBuyerCommentActionLabel = (action) => {
  const map = {
    create: '首次提交',
    resubmit: '重新提交'
  }
  return map[action] || '提交说明'
}

const getCountdownMeta = (deadline) => {
  if (!deadline) return { text: '未设置截止时间', urgent: false }
  const deadlineMs = new Date(deadline).getTime()
  if (Number.isNaN(deadlineMs)) return { text: '截止时间无效', urgent: false }
  const diffMs = deadlineMs - nowTs.value
  if (diffMs <= 0) return { text: '已逾期', urgent: true }
  const totalSeconds = Math.floor(diffMs / 1000)
  const days = Math.floor(totalSeconds / 86400)
  const hours = Math.floor((totalSeconds % 86400) / 3600)
  const minutes = Math.floor((totalSeconds % 3600) / 60)
  const seconds = totalSeconds % 60
  const text = days > 0
    ? `${days}天 ${hours}时 ${minutes}分 ${seconds}秒`
    : `${hours}时 ${minutes}分 ${seconds}秒`
  return { text, urgent: diffMs < 2 * 3600 * 1000 }
}

const hasTaskExpired = (task) => {
  if (!task || getTaskDisplayStatus(task) !== 'active' || !task.deadline) return false
  const deadlineMs = new Date(task.deadline).getTime()
  if (Number.isNaN(deadlineMs)) return false
  return nowTs.value > deadlineMs
}

const detailCountdownMeta = computed(() => getCountdownMeta(currentTaskDetails.value?.deadline))
const currentTaskDisplayStatus = computed(() => getTaskDisplayStatus(currentTaskDetails.value))
const isCurrentTaskCompareReady = computed(() => isTaskCompareReady(currentTaskDetails.value))
const isAutoAllocationAvailable = computed(() => {
  const task = currentTaskDetails.value
  if (!task || task.type !== 'auto') return false
  const status = String(task.status || '').toLowerCase()
  return Boolean(task.compare_ready || ['closed', 'cancelled'].includes(status))
})
const isAutoAllocationReadonly = computed(() => {
  const status = String(currentTaskDetails.value?.status || '').toLowerCase()
  return ['closed', 'cancelled'].includes(status)
})
const compareReadyAlertTitle = computed(() => {
  if (currentTaskDetails.value?.compare_ready_reason === 'max_rounds_reached') {
    return '自动谈判已达到最大轮次：当前任务进入“待份额分配”状态，请直接在当前详情页完成按物料拆单定标。'
  }
  return '自动谈判已提前结束：当前任务进入“待份额分配”状态，请直接在当前详情页完成按物料拆单定标。'
})
const detailCountdownText = computed(() =>
  isCurrentTaskCompareReady.value ? '自动谈判已结束，等待采购员完成份额定标' : detailCountdownMeta.value.text
)
const isDetailDeadlineUrgent = computed(() => !isCurrentTaskCompareReady.value && detailCountdownMeta.value.urgent)
const canSubmitAutoAllocations = computed(() => {
  if (!isAutoAllocationAvailable.value || isAutoAllocationReadonly.value) return false
  const items = currentTaskDetails.value?.items || []
  return items.length > 0 && items.every((item) => {
    const suppliers = getAllocationSuppliersForItem(item)
    return suppliers.length > 0 && getItemAllocationSum(item.id) === 100
  })
})

const getTaskStatusType = (status) => {
  const map = {
    'draft': 'info',
    'pending_approval': 'warning',
    'approval_rejected': 'danger',
    'active': 'success',
    'closed': 'info',
    'awaiting_award': 'warning',
    'cancelled': 'danger',
    'pending_fill': 'warning',
    'analyzing': 'primary'
  }
  return map[status] || ''
}

const getTaskStatusLabel = (status) => {
  const map = {
    'draft': '草稿',
    'pending_approval': '待审批',
    'approval_rejected': '审批驳回',
    'active': '进行中',
    'closed': '已结束',
    'awaiting_award': '待份额分配',
    'cancelled': '已取消',
    'pending_fill': '待填写',
    'analyzing': '分析中'
  }
  return map[status] || status
}

const getQuoteRowClassName = ({ row }) => {
  return row?.is_anomaly ? 'anomaly-row' : ''
}

const resolveLatestItemQuote = (link, itemId) => {
  const rounds = Object.keys(link?.quotes || {})
    .map((round) => Number(round))
    .filter((round) => Number.isFinite(round))
    .sort((a, b) => b - a)

  for (const round of rounds) {
    const quotes = link?.quotes?.[round] || link?.quotes?.[String(round)] || []
    const matched = quotes.find((quote) => Number(quote?.item_id) === Number(itemId))
    if (matched) return matched
  }
  return null
}

const getHistoricalAllocatedRatio = (link, item) => {
  const materialAllocation = (link?.material_allocations || []).find((allocation) => {
    return Number(allocation?.item_id) === Number(item?.id) ||
      String(allocation?.material_code || '') === String(item?.material_code || '')
  })
  return Number(materialAllocation?.allocated_ratio || 0)
}

const initializeAutoItemAllocations = () => {
  const task = currentTaskDetails.value
  if (!task || task.type !== 'auto') {
    autoItemAllocations.value = {}
    return
  }

  const nextAllocations = {}
  ;(task.items || []).forEach((item) => {
    nextAllocations[item.id] = {}
    ;(task.links || []).forEach((link) => {
      const quote = resolveLatestItemQuote(link, item.id)
      if (!quote) return
      nextAllocations[item.id][link.link_id] = isAutoAllocationReadonly.value ? getHistoricalAllocatedRatio(link, item) : 0
    })
  })
  autoItemAllocations.value = nextAllocations
}

const loadTopHistoricalSuppliers = async (taskDetails) => {
  const items = taskDetails?.items || []
  const nextMap = {}
  await Promise.all(items.map(async (item) => {
    try {
      const res = await api.get(`/compare/suppliers/${item.material_code}`)
      nextMap[item.material_code] = Array.isArray(res.data) && res.data.length > 0 ? res.data[0] : null
    } catch (error) {
      console.error(`获取物料 ${item.material_code} 历史供应商失败`, error)
      nextMap[item.material_code] = null
    }
  }))
  topHistoricalSupplierMap.value = nextMap
}

const getAllocationSuppliersForItem = (item) => {
  const links = currentTaskDetails.value?.links || []
  const commonSupplier = topHistoricalSupplierMap.value?.[item.material_code]
  const commonCode = String(commonSupplier?.code || '')
  const commonName = String(commonSupplier?.name || commonSupplier?.supplier_name || '')

  const rows = links.map((link) => {
    const quote = resolveLatestItemQuote(link, item.id)
    if (!quote) return null
    return {
      link_id: link.link_id,
      supplier_id: link.supplier_id,
      supplier_name: link.supplier_name,
      supplier_code: link.supplier_code,
      supplier_grade: link.supplier_grade,
      status: link.status,
      price: Number(quote.price || 0),
      qty: Number(quote.qty || item.qty || 0),
      material_allocations: link.material_allocations || []
    }
  }).filter(Boolean)

  const validRows = rows.filter((row) => Number(row.price || 0) > 0)
  const minPrice = validRows.length ? Math.min(...validRows.map((row) => Number(row.price || 0))) : null
  const maxPrice = validRows.length ? Math.max(...validRows.map((row) => Number(row.price || 0))) : null

  return rows.map((row) => {
    const tags = []
    if ((commonCode && String(row.supplier_code || '') === commonCode) || (commonName && String(row.supplier_name || '') === commonName)) {
      tags.push({ label: '常用供应商', type: 'primary' })
    }
    if (minPrice !== null && Number(row.price || 0) === minPrice) {
      tags.push({ label: '最低价', type: 'success' })
    }
    if (maxPrice !== null && Number(row.price || 0) === maxPrice) {
      tags.push({ label: '最高价', type: 'danger' })
    }
    return {
      ...row,
      is_common: tags.some(tag => tag.label === '常用供应商'),
      is_lowest: tags.some(tag => tag.label === '最低价'),
      identity_tags: tags
    }
  })
}

const getItemAllocationBucket = (itemId) => {
  if (!autoItemAllocations.value[itemId]) {
    autoItemAllocations.value[itemId] = {}
  }
  return autoItemAllocations.value[itemId]
}

const getItemAllocationSum = (itemId) => {
  const bucket = getItemAllocationBucket(itemId)
  return Object.values(bucket).reduce((sum, value) => sum + Number(value || 0), 0)
}

const getItemAllocatedQty = (item, supplierRow) => {
  const ratio = Number(getItemAllocationBucket(item.id)[supplierRow.link_id] || 0)
  if (ratio <= 0) return '-'
  return Math.round(Number(item.qty || 0) * ratio / 100)
}

const applyItemAllocationStrategy = (item, type, silent = false) => {
  const suppliers = getAllocationSuppliersForItem(item)
  if (!suppliers.length) {
    if (!silent) ElMessage.warning(`物料 ${item.material_name} 暂无可分配供应商`)
    return false
  }

  const bucket = {}
  suppliers.forEach((supplier) => {
    bucket[supplier.link_id] = 0
  })

  const commonSupplier = suppliers.find((supplier) => supplier.is_common)
  const lowestSupplier = suppliers.find((supplier) => supplier.is_lowest)

  if (type === 'common') {
    if (!commonSupplier) {
      if (!silent) ElMessage.warning(`物料 ${item.material_name} 未识别到常用供应商`)
      return false
    }
    bucket[commonSupplier.link_id] = 100
  } else if (type === 'lowest') {
    if (!lowestSupplier) {
      if (!silent) ElMessage.warning(`物料 ${item.material_name} 未识别到最低价供应商`)
      return false
    }
    bucket[lowestSupplier.link_id] = 100
  } else if (type === 'pressure') {
    if (!commonSupplier && !lowestSupplier) {
      if (!silent) ElMessage.warning(`物料 ${item.material_name} 未识别到常用供应商或最低价供应商`)
      return false
    }
    if (commonSupplier && lowestSupplier && commonSupplier.link_id !== lowestSupplier.link_id) {
      bucket[commonSupplier.link_id] = Number(pressureCommonRatio.value || 0)
      bucket[lowestSupplier.link_id] = Number(pressureLowestRatio.value || 0)
    } else {
      const preferredSupplier = commonSupplier || lowestSupplier
      if (preferredSupplier) {
        bucket[preferredSupplier.link_id] = 100
      }
    }
  }

  autoItemAllocations.value = {
    ...autoItemAllocations.value,
    [item.id]: bucket
  }
  return true
}

const applyAllocationStrategyToAll = (type) => {
  const items = currentTaskDetails.value?.items || []
  let appliedCount = 0
  items.forEach((item) => {
    if (applyItemAllocationStrategy(item, type, true)) {
      appliedCount += 1
    }
  })
  if (!appliedCount) {
    ElMessage.warning('当前没有可应用策略的物料')
  }
}

const submitAutoItemAllocations = async () => {
  if (!currentTaskDetails.value || !canSubmitAutoAllocations.value) {
    ElMessage.warning('请先完成所有物料的份额分配，且每个物料总和必须等于 100%')
    return
  }

  const allocationMap = {}
  ;(currentTaskDetails.value.items || []).forEach((item) => {
    const suppliers = getAllocationSuppliersForItem(item)
    suppliers.forEach((supplier) => {
      const ratio = Number(getItemAllocationBucket(item.id)[supplier.link_id] || 0)
      if (ratio <= 0) return
      if (!allocationMap[supplier.link_id]) {
        allocationMap[supplier.link_id] = {
          link_id: supplier.link_id,
          item_allocations: []
        }
      }
      allocationMap[supplier.link_id].item_allocations.push({
        item_id: item.id,
        allocated_ratio: ratio
      })
    })
  })

  const payload = {
    allocations: Object.values(allocationMap)
  }
  if (!payload.allocations.length) {
    ElMessage.warning('请至少为一个供应商分配份额')
    return
  }

  submittingAutoAllocation.value = true
  try {
    await closeInquiryTask(currentTaskDetails.value.id, payload)
    ElMessage.success('份额分配成功，合同生成流程已触发')
    await viewTaskDetails(currentTask.value, 'allocation')
    await fetchTasks()
  } catch (error) {
    console.error(error)
    ElMessage.error(error.response?.data?.detail || '份额分配失败')
  } finally {
    submittingAutoAllocation.value = false
  }
}

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

onMounted(() => {
  fetchTasks()
  timerId = window.setInterval(() => {
    nowTs.value = Date.now()
  }, 1000)
})

onUnmounted(() => {
  if (timerId) {
    window.clearInterval(timerId)
  }
})
</script>

<style scoped>
.page-container {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  background: white;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.page-title {
  margin: 0;
  font-size: 24px;
  color: #303133;
}

.content-card {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  padding: 15px;
}

.table-container {
  flex: 1;
  min-height: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

:deep(.el-table) {
  flex: 1;
  height: 100%;
}

.toolbar {
  margin-bottom: 15px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-shrink: 0;
}

.toolbar-left, .toolbar-right {
  display: flex;
  align-items: center;
  gap: 10px;
}

/* 任务详情弹窗美化 */
.task-details-container {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.awaiting-award-alert {
  margin-top: -8px;
}

.buyer-comment-alert {
  margin-top: -8px;
}

.buyer-comment-title {
  font-weight: 700;
}

.buyer-comment-content {
  white-space: pre-wrap;
  line-height: 1.7;
  color: #303133;
}

.buyer-comment-history {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.buyer-comment-history-item {
  padding: 12px 14px;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  background: #fafafa;
}

.buyer-comment-history-meta {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  font-size: 12px;
  color: #909399;
  margin-bottom: 8px;
}

.buyer-comment-history-content {
  white-space: pre-wrap;
  line-height: 1.7;
  color: #303133;
}

.task-attachment-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.task-attachment-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  background: #fafafa;
  flex-wrap: wrap;
}

.task-attachment-link {
  color: #409eff;
  text-decoration: none;
  font-weight: 500;
}

.task-attachment-link:hover {
  text-decoration: underline;
}

.task-attachment-meta {
  color: #909399;
  font-size: 12px;
}

.attachment-preview-container {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: 520px;
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

.tab-label-with-status {
  display: inline-flex;
  align-items: center;
  gap: 6px;
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

.header-title {
  display: flex;
  align-items: center;
}

.task-title {
  font-size: 18px;
  font-weight: bold;
  color: #303133;
}

.details-tabs {
  box-shadow: 0 2px 12px 0 rgba(0,0,0,0.05);
  border-radius: 8px;
  overflow: hidden;
}

.tab-toolbar {
  margin-bottom: 15px;
  display: flex;
  justify-content: flex-start;
  align-items: center;
  background-color: #f5f7fa;
  padding: 10px 15px;
  border-radius: 4px;
}

.supplier-form {
  margin-bottom: 0;
}

.supplier-form .el-form-item {
  margin-bottom: 0;
  margin-right: 15px;
}

.expand-content {
  padding: 20px 40px;
  background-color: #fafafa;
  border-top: 1px solid #ebeef5;
  border-bottom: 1px solid #ebeef5;
}

.expand-title {
  margin-top: 0;
  margin-bottom: 15px;
  color: #606266;
  font-size: 15px;
}

.auto-allocation-wrap {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.auto-allocation-alert {
  margin-bottom: 4px;
}

.global-allocation-toolbar {
  margin-bottom: 0;
}

.allocation-item-card {
  border-radius: 8px;
}

.allocation-item-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  flex-wrap: wrap;
}

.allocation-item-title {
  font-size: 15px;
  font-weight: 700;
  color: #303133;
}

.allocation-item-meta {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  margin-top: 6px;
  color: #909399;
  font-size: 12px;
}

.allocation-item-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.allocation-item-footer {
  margin-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.allocation-submit-bar {
  display: flex;
  justify-content: flex-end;
}

.task-table-action-group {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: 8px;
  flex-wrap: nowrap;
  width: 100%;
  padding-left: 8px;
  box-sizing: border-box;
}

.task-action-primary-btn {
  width: 96px;
  margin: 0;
}

.task-action-secondary-btn {
  width: 78px;
  margin: 0;
}

.approval-cell {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.approval-subtext {
  color: #909399;
  font-size: 12px;
  line-height: 1.4;
}

.supplier-name-cell {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.allocation-strategy-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
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

.allocation-sum-text {
  font-size: 14px;
  color: #303133;
  font-weight: 500;
}

.allocation-warning {
  font-size: 13px;
  color: #f56c6c;
}

.countdown-text {
  font-weight: 500;
  color: #606266;
}

.countdown-urgent {
  color: #f56c6c;
  font-weight: 700;
}

:deep(.anomaly-row) {
  background-color: #fff8e1;
}
</style>
