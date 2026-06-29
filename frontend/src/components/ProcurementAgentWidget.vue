<template>
  <div v-if="visible" class="agent-widget">
    <transition name="agent-fade">
      <section
        v-if="expanded"
        class="agent-panel"
        v-loading="pageLoading"
        :style="panelStyle"
      >
        <aside class="panel-sidebar" :class="{ collapsed: sidebarCollapsed }">
          <div class="sidebar-top">
            <div v-if="!sidebarCollapsed">
              <div class="sidebar-kicker">Procurement Copilot</div>
              <h3>采购助手</h3>
            </div>
            <button class="icon-btn" type="button" @click="sidebarCollapsed = !sidebarCollapsed">
              {{ sidebarCollapsed ? '>' : '<' }}
            </button>
          </div>

          <div v-if="!sidebarCollapsed" class="sidebar-actions">
            <button class="primary-btn" type="button" @click="startNewConversation">新建对话</button>
          </div>

          <div v-if="!sidebarCollapsed" class="session-list">
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
            <div v-if="sessions.length === 0" class="session-empty">暂无历史对话</div>
          </div>
        </aside>

        <section class="panel-main">
          <header class="panel-header" @pointerdown="startDrag">
            <div class="panel-title">
              <div class="panel-kicker">AI Assistant</div>
              <h2>{{ currentSessionTitle }}</h2>
              <p>可查询物料、供应商、历史价格、采购申请和采购订单。</p>
            </div>
            <div class="panel-actions">
              <span class="model-pill">{{ agentModelLabel }}</span>
              <button class="ghost-btn" type="button" :disabled="!currentSessionId || loading" @click.stop="clearCurrentConversation">
                清空当前对话
              </button>
              <button class="icon-btn" type="button" @click.stop="expanded = false">×</button>
            </div>
          </header>

          <div class="flow-mode-bar">
            <div class="flow-mode-summary">
              <span class="flow-mode-label">当前流程：{{ currentFlowModeLabel }}</span>
              <span class="flow-mode-count">已选 {{ selectedRequestCount }} 条采购申请</span>
            </div>
            <div class="flow-mode-actions">
              <button
                type="button"
                class="mode-chip"
                :class="{ active: currentPageContext.flow_mode === 'auto_inquiry' }"
                @click="setFlowMode('auto_inquiry')"
              >
                自动询价
              </button>
              <button
                type="button"
                class="mode-chip"
                :class="{ active: currentPageContext.flow_mode === 'manual_compare' }"
                @click="setFlowMode('manual_compare')"
              >
                手动比价
              </button>
              <button
                type="button"
                class="mode-chip mode-chip-clear"
                @click="clearFlowMode"
              >
                清除流程
              </button>
            </div>
          </div>

          <div ref="messagesRef" class="messages-area">
            <div v-if="messages.length === 0" class="empty-state">
              <div class="empty-card">
                <h4>可以直接这样问</h4>
                <div class="empty-suggestions">
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
                      <template v-if="false">
                        <div class="pending-action-summary">
                          <div>自动询价方案已生成</div>
                          <div>已选采购申请：{{ getActionDraft(action).selected_line_count }} 条</div>
                          <div>涉及物料：{{ getActionDraft(action).material_item_count }} 个</div>
                          <div>推荐供应商：{{ getActionDraft(action).recommended_supplier_count }} 家</div>
                          <div>预计操作：{{ action.preview?.expected_operation || '确认后将创建询价任务，并给供应商发送询价单' }}</div>
                        </div>
                      </template>
                      <template v-else>
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
                          filterable
                          remote
                          reserve-keyword
                          size="small"
                          placeholder="建议供应商"
                          :remote-method="(keyword) => querySearchActionSuppliers(action, keyword)"
                          @change="() => persistActionDraft(action)"
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
                      <div class="pending-action-hint">
                        支持按供应商名称或编码模糊搜索，并可把新供应商追加到当前询价草稿。
                      </div>
                      <div v-if="getSelectedSupplierDetails(action).length" class="selected-supplier-tags">
                        <span
                          v-for="supplier in getSelectedSupplierDetails(action)"
                          :key="`selected-supplier-${supplier.value}`"
                          class="selected-supplier-tag"
                        >
                          {{ supplier.label }}<span v-if="supplier.code">（{{ supplier.code }}）</span>
                        </span>
                      </div>
                      <div v-if="getActionDraft(action).recommended_supplier_details.length" class="recommended-supplier-list">
                        <div
                          v-for="supplier in getActionDraft(action).recommended_supplier_details"
                          :key="`auto-supplier-${supplier.value}`"
                          class="recommended-supplier-card"
                        >
                          <div class="recommended-supplier-name">
                            {{ supplier.label }}
                            <span v-if="supplier.code">（{{ supplier.code }}）</span>
                          </div>
                          <div class="recommended-supplier-meta">
                            <span v-if="supplier.avg_price !== null && supplier.avg_price !== undefined">历史均价：{{ supplier.avg_price }}</span>
                            <span v-if="supplier.latest_price !== null && supplier.latest_price !== undefined">最新价：{{ supplier.latest_price }}</span>
                          </div>
                          <div v-if="supplier.recommend_reason" class="recommended-supplier-reason">{{ supplier.recommend_reason }}</div>
                        </div>
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
                    </template>
                    </div>
                    <div v-else-if="action.action_type === 'save_manual_quotes'" class="pending-action-form">
                      <div class="pending-action-summary">
                        <div>手动比价报价卡</div>
                        <div>已选采购申请：{{ getActionDraft(action).selected_line_count }} 条</div>
                        <div>物料项：{{ getActionDraft(action).material_item_count }} 项</div>
                        <div>请直接补充供应商报价，系统会基于卡片内容继续生成比价和份额分配建议。</div>
                      </div>
                      <el-input v-model="getActionDraft(action).title" size="small" placeholder="手动比价任务标题" />
                      <div v-if="getActionDraft(action).bill_nos" class="pending-action-hint">
                        关联单号：{{ getActionDraft(action).bill_nos }}
                      </div>
                      <div
                        v-for="(line, lineIndex) in getManualQuoteLines(action)"
                        :key="`manual-line-${line.erp_request_id || line.id || lineIndex}`"
                        class="manual-quote-block"
                      >
                        <div class="manual-quote-block-header">
                          <div class="manual-quote-block-title">{{ line.material_name || '未命名物料' }}</div>
                          <div class="manual-quote-block-meta">
                            {{ line.material_code || '-' }} / {{ line.material_model || '-' }} / 数量 {{ line.qty || '-' }}
                          </div>
                        </div>
                        <div v-if="line.delivery_date" class="pending-action-hint">
                          需求交期：{{ line.delivery_date }}
                        </div>
                        <div v-if="line.target_price !== null && line.target_price !== undefined && line.target_price !== ''" class="pending-action-hint">
                          目标价参考：{{ line.target_price }}
                        </div>
                        <div v-if="line.material_history && (line.material_history.price_history?.length || line.material_history.monthly_trend?.length || line.material_history.recent_orders?.length)" class="manual-quote-history">
                          <el-collapse>
                            <el-collapse-item
                              v-if="line.material_history.price_history?.length"
                              :name="`price-history-${lineIndex}`"
                              title="历史价格汇总（按供应商）"
                            >
                              <div class="history-table-wrap">
                                <table class="history-table">
                                  <thead>
                                    <tr>
                                      <th>供应商</th>
                                      <th>订单数</th>
                                      <th>均价</th>
                                      <th>最新价</th>
                                      <th>最低价</th>
                                      <th>最高价</th>
                                      <th>最近日期</th>
                                    </tr>
                                  </thead>
                                  <tbody>
                                    <tr v-for="(ph, phi) in line.material_history.price_history" :key="`ph-${lineIndex}-${phi}`">
                                      <td>{{ ph.supplier_name || '-' }}</td>
                                      <td>{{ ph.order_count ?? '-' }}</td>
                                      <td>{{ ph.avg_tax_net_price ?? '-' }}</td>
                                      <td>{{ ph.latest_tax_net_price ?? '-' }}</td>
                                      <td>{{ ph.lowest_price ?? '-' }}</td>
                                      <td>{{ ph.highest_price ?? '-' }}</td>
                                      <td>{{ ph.latest_date || '-' }}</td>
                                    </tr>
                                  </tbody>
                                </table>
                              </div>
                            </el-collapse-item>
                            <el-collapse-item
                              v-if="line.material_history.monthly_trend?.length"
                              :name="`monthly-trend-${lineIndex}`"
                              title="月度价格趋势"
                            >
                              <div class="history-table-wrap">
                                <table class="history-table">
                                  <thead>
                                    <tr>
                                      <th>月份</th>
                                      <th>供应商</th>
                                      <th>订单数</th>
                                      <th>均价</th>
                                      <th>最低价</th>
                                      <th>最高价</th>
                                    </tr>
                                  </thead>
                                  <tbody>
                                    <tr v-for="(mt, mti) in line.material_history.monthly_trend" :key="`mt-${lineIndex}-${mti}`">
                                      <td>{{ mt.month || '-' }}</td>
                                      <td>{{ mt.supplier_name || '-' }}</td>
                                      <td>{{ mt.order_count ?? '-' }}</td>
                                      <td>{{ mt.avg_tax_net_price ?? '-' }}</td>
                                      <td>{{ mt.min_tax_net_price ?? '-' }}</td>
                                      <td>{{ mt.max_tax_net_price ?? '-' }}</td>
                                    </tr>
                                  </tbody>
                                </table>
                              </div>
                            </el-collapse-item>
                            <el-collapse-item
                              v-if="line.material_history.recent_orders?.length"
                              :name="`recent-orders-${lineIndex}`"
                              title="最近采购订单"
                            >
                              <div class="history-table-wrap">
                                <table class="history-table">
                                  <thead>
                                    <tr>
                                      <th>单号</th>
                                      <th>供应商</th>
                                      <th>单价</th>
                                      <th>数量</th>
                                      <th>日期</th>
                                    </tr>
                                  </thead>
                                  <tbody>
                                    <tr v-for="(ro, roi) in line.material_history.recent_orders" :key="`ro-${lineIndex}-${roi}`">
                                      <td>{{ ro.bill_no || '-' }}</td>
                                      <td>{{ ro.supplier_name || '-' }}</td>
                                      <td>{{ ro.tax_net_price ?? ro.price ?? '-' }}</td>
                                      <td>{{ ro.qty ?? '-' }}</td>
                                      <td>{{ ro.order_date || ro.latest_date || '-' }}</td>
                                    </tr>
                                  </tbody>
                                </table>
                              </div>
                            </el-collapse-item>
                          </el-collapse>
                        </div>
                        <div class="manual-quote-supplier-list">
                          <div class="manual-quote-supplier-head">
                            <span>供应商名称</span>
                            <span>供应商编码</span>
                            <span>报价单价</span>
                            <span>报价数量</span>
                          </div>
                          <div
                            v-for="(supplier, supplierIndex) in line.quote_suppliers"
                            :key="`manual-supplier-${lineIndex}-${supplierIndex}`"
                            class="manual-quote-supplier-row"
                          >
                            <el-autocomplete
                              v-model="supplier.supplier_name"
                              size="small"
                              :trigger-on-focus="true"
                              :fetch-suggestions="(queryString, cb) => querySearchManualSuppliers(action, lineIndex, supplierIndex, queryString, cb)"
                              placeholder="供应商名称"
                              @select="(item) => applyManualSupplierSelection(supplier, item)"
                              @input="() => handleManualSupplierNameInput(supplier)"
                            >
                              <template #default="{ item }">
                                <div class="manual-supplier-option">
                                  <span class="manual-supplier-option-name">{{ item.name || item.value }}</span>
                                  <span v-if="item.code" class="manual-supplier-option-code">{{ item.code }}</span>
                                </div>
                              </template>
                            </el-autocomplete>
                            <el-input v-model="supplier.supplier_code" size="small" placeholder="供应商编码" />
                            <el-input-number
                              v-model="supplier.price"
                              size="small"
                              :min="0"
                              :precision="4"
                              :controls="false"
                              placeholder="报价单价"
                            />
                            <el-input-number
                              v-model="supplier.qty"
                              size="small"
                              :min="0"
                              :precision="4"
                              :controls="false"
                              placeholder="报价数量"
                            />
                            <el-button plain size="small" @click="removeManualQuoteSupplier(action, lineIndex, supplierIndex)">删除</el-button>
                            <div v-if="supplier.recommend_reason || supplier.suggested_price" class="manual-quote-supplier-hint">
                              <span v-if="supplier.suggested_price !== null && supplier.suggested_price !== undefined">建议价：{{ supplier.suggested_price }}</span>
                              <span v-if="supplier.recommend_reason">{{ supplier.recommend_reason }}</span>
                            </div>
                          </div>
                        </div>
                        <el-button plain size="small" @click="addManualQuoteSupplier(action, lineIndex)">新增供应商报价</el-button>
                      </div>
                      <div class="pending-action-button-row">
                        <el-button
                          class="pending-action-confirm-btn"
                          type="primary"
                          size="small"
                          :loading="confirmingActionIds.includes(action.pending_action_id)"
                          @click="confirmAction(action)"
                        >
                          {{ getActionConfirmLabel(action) }}
                        </el-button>
                        <el-button
                          class="pending-action-confirm-btn"
                          plain
                          size="small"
                          @click="dismissPendingAction(action)"
                        >
                          取消
                        </el-button>
                      </div>
                    </div>
                    <div v-if="action.action_type === 'create_inquiry_from_selected_requests'" class="pending-action-button-row">
                      <el-button
                        class="pending-action-confirm-btn"
                        type="primary"
                        size="small"
                        :loading="confirmingActionIds.includes(action.pending_action_id)"
                        @click="confirmAction(action, { execution_mode: 'send_now' })"
                      >
                        确认发送询价单
                      </el-button>
                      <el-button
                        class="pending-action-confirm-btn"
                        type="warning"
                        size="small"
                        :loading="confirmingActionIds.includes(action.pending_action_id)"
                        @click="confirmAction(action, { execution_mode: 'draft_only' })"
                      >
                        只保存草稿
                      </el-button>
                      <el-button
                        class="pending-action-confirm-btn"
                        plain
                        size="small"
                        @click="dismissPendingAction(action)"
                      >
                        取消
                      </el-button>
                    </div>
                    <el-button
                      v-else-if="!(action.action_type === 'confirm_award' && action.preview?.plan_mode === 'manual_compare') && action.action_type !== 'save_manual_quotes'"
                      class="pending-action-confirm-btn"
                      type="primary"
                      size="small"
                      :loading="confirmingActionIds.includes(action.pending_action_id)"
                      @click="confirmAction(action)"
                    >
                      {{ getPendingActionButtonLabel(action) }}
                    </el-button>
                    <div v-if="action.action_type === 'confirm_award' && action.preview?.plan_mode === 'manual_compare'" class="pending-action-form">
                      <div class="pending-action-summary">
                        <div>手动比价方案已生成</div>
                        <div>已选采购申请：{{ getActionDraft(action).selected_line_count }} 条</div>
                        <div>报价来源：{{ getActionDraft(action).quote_source || '已有报价' }}</div>
                        <div>推荐中标供应商：{{ getActionDraft(action).recommended_supplier_count }} 家</div>
                        <div>份额分配：{{ getActionDraft(action).share_summary || '待分配' }}</div>
                        <div>请直接调整份额并继续生成中标与合同草稿。</div>
                      </div>
                      <div class="pending-action-allocation-list">
                        <div
                          v-for="allocation in getActionDraft(action).allocations"
                          :key="allocation.link_id"
                          class="pending-action-allocation-row"
                        >
                          <div class="pending-action-allication-info">
                            <span class="pending-action-allocation-name">{{ allocation.supplier_name }}</span>
                            <span v-if="allocation.quote_total_amount !== null && allocation.quote_total_amount !== undefined" class="pending-action-allocation-meta">
                              报价总额：{{ allocation.quote_total_amount }}
                            </span>
                            <span v-if="allocation.avg_quote_price !== null && allocation.avg_quote_price !== undefined" class="pending-action-allocation-meta">
                              均价：{{ allocation.avg_quote_price }}
                            </span>
                            <span v-if="allocation.recommendation_reason" class="pending-action-allocation-reason">
                              {{ allocation.recommendation_reason }}
                            </span>
                          </div>
                          <div class="pending-action-allocation-control">
                            <el-input-number
                              v-model="allocation.allocated_ratio"
                              size="small"
                              :min="0"
                              :max="100"
                              :precision="2"
                              :disabled="!getActionDraft(action).editing"
                            />
                            <span class="pending-action-allocation-suffix">%</span>
                          </div>
                        </div>
                      </div>
                      <div class="pending-action-hint">
                        当前合计：{{ getAllocationTotal(action) }}%
                      </div>
                      <div class="pending-action-button-row">
                        <el-button
                          class="pending-action-confirm-btn"
                          type="primary"
                          size="small"
                          :loading="confirmingActionIds.includes(action.pending_action_id)"
                          @click="confirmAction(action)"
                        >
                          生成中标与合同草稿
                        </el-button>
                        <el-button
                          class="pending-action-confirm-btn"
                          type="warning"
                          size="small"
                          @click="toggleManualCompareEditing(action)"
                        >
                          修改份额
                        </el-button>
                        <el-button
                          class="pending-action-confirm-btn"
                          plain
                          size="small"
                          @click="dismissPendingAction(action)"
                        >
                          取消
                        </el-button>
                      </div>
                    </div>
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

          <footer class="panel-footer">
            <textarea
              v-model="draft"
              class="chat-input"
              rows="3"
              maxlength="2000"
              placeholder="输入采购相关问题，Enter 发送，Shift + Enter 换行"
              @keydown="handleKeydown"
            ></textarea>
            <div class="footer-actions">
              <span class="footer-tip">支持新建对话、历史切换、拖拽移动与缩放</span>
              <button class="send-btn" type="button" :disabled="!canSend || loading" @click="sendMessage">发送</button>
            </div>
          </footer>
        </section>

        <button
          class="resize-handle"
          type="button"
          aria-label="resize"
          @pointerdown.stop.prevent="startResize"
        ></button>
      </section>
    </transition>

    <button class="floating-trigger" type="button" @click="toggleExpanded">
      <span class="trigger-badge">AI</span>
      <span>采购助手</span>
    </button>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '../api'
import {
  clearProcurementAgentMemory,
  confirmProcurementAgentAction,
  createProcurementAgentSession,
  getProcurementAgentSessionMessages,
  getProcurementAgentSessions,
  getProcurementAgentStatus,
  sendProcurementAgentMessage,
  updateProcurementAgentAction,
} from '../api/agent'

const route = useRoute()
const authSnapshot = ref({
  role: '',
  token: '',
  department: '',
})
const syncAuthSnapshot = () => {
  authSnapshot.value = {
    role: localStorage.getItem('role') || '',
    token: localStorage.getItem('token') || '',
    department: localStorage.getItem('department') || '',
  }
}
const role = computed(() => authSnapshot.value.role)
const token = computed(() => authSnapshot.value.token)
const department = computed(() => authSnapshot.value.department)
const visible = computed(() => role.value !== 'supplier' && department.value === '采购部' && Boolean(token.value))

const expanded = ref(false)
const sidebarCollapsed = ref(false)
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
const savingActionDraftIds = ref([])
const actionDraftSaveTimers = new Map()
const dismissedPendingActionIds = ref([])
const hasInitialized = ref(false)
const pageContextVersion = ref(0)
let ensureLoadedPromise = null

const panelWidth = ref(920)
const panelHeight = ref(720)
const panelRight = ref(24)
const panelBottom = ref(94)

const minWidth = 720
const minHeight = 520
const maxWidthPadding = 36
const maxHeightPadding = 120

const dragState = {
  active: false,
  startX: 0,
  startY: 0,
  startRight: 0,
  startBottom: 0,
}

const resizeState = {
  active: false,
  startX: 0,
  startY: 0,
  startWidth: 0,
  startHeight: 0,
}

const canSend = computed(() => draft.value.trim().length > 0)
const currentSessionTitle = computed(() => {
  const current = sessions.value.find((item) => item.session_id === currentSessionId.value)
  if (current?.title) return current.title
  if (pendingSessionId.value) return '新对话'
  return '采购助手'
})

const readStoredAgentPageContext = () => {
  try {
    return JSON.parse(sessionStorage.getItem('procurement_agent_page_context') || '{}')
  } catch {
    return {}
  }
}

const currentPageContext = computed(() => {
  pageContextVersion.value
  const stored = readStoredAgentPageContext()

  return {
    page: stored.page || stored.route_name || route.path,
    route_name: stored.route_name || route.path,
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

const selectedRequestCount = computed(() => currentPageContext.value.selected_request_ids.length)

const currentFlowModeLabel = computed(() => {
  if (currentPageContext.value.flow_mode === 'auto_inquiry') return '自动询价'
  if (currentPageContext.value.flow_mode === 'manual_compare') return '手动比价'
  return '仅查询'
})

const writeAgentPageContext = (patch = {}) => {
  const nextContext = {
    ...readStoredAgentPageContext(),
    ...patch,
  }
  sessionStorage.setItem('procurement_agent_page_context', JSON.stringify(nextContext))
  pageContextVersion.value += 1
  window.dispatchEvent(new CustomEvent('procurement-agent-context-updated', { detail: nextContext }))
}

const setFlowMode = (flowMode) => {
  writeAgentPageContext({ flow_mode: flowMode || null })
}

const clearFlowMode = () => {
  writeAgentPageContext({ flow_mode: null })
}

const panelStyle = computed(() => ({
  width: `${panelWidth.value}px`,
  height: `${panelHeight.value}px`,
  right: `${panelRight.value}px`,
  bottom: `${panelBottom.value}px`,
}))

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
    .filter((item) => !dismissedPendingActionIds.value.includes(Number(item?.pending_action_id)))
}

const getPendingActionButtonLabel = (action) => {
  const actionType = String(action?.action_type || '').trim()
  if (actionType === 'create_inquiry_draft') return '确认创建询价草稿'
  if (actionType === 'create_inquiry_from_selected_requests') return '确认创建询价任务'
  if (actionType === 'confirm_award' && action?.preview?.plan_mode === 'manual_compare') return '生成中标与合同草稿'
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
        .map((item) => ({
          value: Number(item.supplier_id),
          label: item.supplier_name || `供应商${item.supplier_id}`,
          code: item?.supplier_code || '',
          avg_price: item?.avg_price ?? null,
          latest_price: item?.latest_price ?? null,
          recommend_reason: item?.recommend_reason || '',
        })),
      recommended_supplier_details: recommendedSuppliers
        .filter((item) => Number(item?.supplier_id) > 0)
        .map((item) => ({
          value: Number(item.supplier_id),
          label: item.supplier_name || `供应商${item.supplier_id}`,
          code: item?.supplier_code || '',
          avg_price: item?.avg_price ?? null,
          latest_price: item?.latest_price ?? null,
          recommend_reason: item?.recommend_reason || '',
        })),
      deadline: preview.deadline || '',
      request_count: preview.request_count ?? '',
      selected_line_count: preview.selected_line_count ?? preview.request_count ?? '',
      material_item_count: preview.material_item_count ?? '',
      recommended_supplier_count: preview.recommended_supplier_count ?? (Array.isArray(preview.supplier_ids) ? preview.supplier_ids.length : 0),
      bill_nos: Array.isArray(preview.bill_nos) ? preview.bill_nos.filter(Boolean).join('、') : '',
      material_codes: Array.isArray(preview.material_codes) ? preview.material_codes.filter(Boolean).join('、') : '',
      material_names: Array.isArray(preview.material_names) ? preview.material_names.filter(Boolean).join('、') : '',
      material_models: Array.isArray(preview.material_models) ? preview.material_models.filter(Boolean).join('、') : '',
      delivery_dates: Array.isArray(preview.delivery_dates) ? preview.delivery_dates.filter(Boolean).join('、') : '',
      qty_total: preview.qty_total ?? '',
      price_reference_text: formatPriceReference(preview.price_reference),
      risk_notes: Array.isArray(preview.risk_notes) ? preview.risk_notes.filter(Boolean).join('；') : '',
      quote_source: preview.quote_source || '',
      share_summary: preview.share_summary || '',
      editing: false,
      allocations: Array.isArray(preview.allocations)
        ? preview.allocations.map((item) => ({
            link_id: Number(item?.link_id) || 0,
            supplier_id: Number(item?.supplier_id) || 0,
            supplier_name: item?.supplier_name || '',
            allocated_ratio: Number(item?.allocated_ratio) || 0,
            quote_total_amount: item?.quote_total_amount ?? null,
            avg_quote_price: item?.avg_quote_price ?? null,
            supplier_rating_score: item?.supplier_rating_score ?? null,
            recommendation_reason: item?.recommendation_reason || '',
          }))
        : [],
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

const mergeSupplierOptions = (currentOptions = [], incomingOptions = []) => {
  const merged = new Map()
  ;[...currentOptions, ...incomingOptions].forEach((item) => {
    const value = Number(item?.value || item?.id || item?.supplier_id) || 0
    const label = String(item?.label || item?.name || item?.supplier_name || '').trim()
    if (!value || !label) return
    merged.set(value, {
      value,
      label,
      code: item?.code || item?.supplier_code || '',
      avg_price: item?.avg_price ?? null,
      latest_price: item?.latest_price ?? null,
      recommend_reason: item?.recommend_reason || '',
    })
  })
  return Array.from(merged.values())
}

const getSelectedSupplierDetails = (action) => {
  const draftModel = getActionDraft(action)
  const selectedIds = Array.isArray(draftModel.supplier_ids) ? draftModel.supplier_ids.map((item) => Number(item) || 0) : []
  if (!selectedIds.length) return []
  const optionMap = new Map(
    mergeSupplierOptions(draftModel.supplier_options, draftModel.recommended_supplier_details)
      .map((item) => [Number(item.value) || 0, item]),
  )
  return selectedIds
    .filter((item) => item > 0)
    .map((item) => optionMap.get(item))
    .filter(Boolean)
}

const querySearchActionSuppliers = async (action, keyword) => {
  const draftModel = getActionDraft(action)
  const search = String(keyword || '').trim()
  if (!search) {
    draftModel.supplier_options = mergeSupplierOptions(
      draftModel.supplier_options,
      draftModel.recommended_supplier_details,
    )
    return
  }

  try {
    const { data } = await api.get('/supplier/list', {
      params: {
        page: 1,
        page_size: 20,
        keyword: search,
      },
      silentError: true,
    })
    const remoteOptions = (Array.isArray(data?.list) ? data.list : []).map((item) => ({
      value: Number(item?.id || item?.supplier_id) || 0,
      label: item?.name || item?.supplier_name || '',
      code: item?.code || item?.supplier_code || '',
      avg_price: item?.avg_price ?? null,
      latest_price: item?.latest_price ?? null,
      recommend_reason: item?.recommend_reason || '',
    }))
    draftModel.supplier_options = mergeSupplierOptions(
      mergeSupplierOptions(draftModel.supplier_options, draftModel.recommended_supplier_details),
      remoteOptions,
    )
  } catch {
    draftModel.supplier_options = mergeSupplierOptions(
      draftModel.supplier_options,
      draftModel.recommended_supplier_details,
    )
  }
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
  if (actionType === 'confirm_award' && action?.preview?.plan_mode === 'manual_compare') {
    return {
      allocations: Array.isArray(draftModel.allocations)
        ? draftModel.allocations.map((item) => ({
            link_id: Number(item?.link_id) || 0,
            allocated_ratio: Number(item?.allocated_ratio) || 0,
          }))
        : [],
    }
  }
  return {}
}

const applySavedActionPreview = (action, preview = {}) => {
  if (!action || !preview || typeof preview !== 'object') return
  action.preview = {
    ...(action.preview || {}),
    ...preview,
  }
  const actionId = Number(action?.pending_action_id)
  if (!Number.isFinite(actionId) || actionId <= 0) return
  delete pendingActionDrafts.value[actionId]
}

const persistActionDraft = (action) => {
  const actionId = Number(action?.pending_action_id)
  if (!Number.isFinite(actionId) || actionId <= 0) return
  if (actionDraftSaveTimers.has(actionId)) {
    clearTimeout(actionDraftSaveTimers.get(actionId))
  }
  actionDraftSaveTimers.set(actionId, setTimeout(async () => {
    savingActionDraftIds.value = Array.from(new Set([...savingActionDraftIds.value, actionId]))
    try {
      const { data } = await updateProcurementAgentAction(actionId, buildActionOverrides(action))
      applySavedActionPreview(action, data?.preview || {})
    } catch (error) {
      ElMessage.error(error.response?.data?.detail || '保存供应商草稿失败')
    } finally {
      savingActionDraftIds.value = savingActionDraftIds.value.filter((id) => id !== actionId)
      actionDraftSaveTimers.delete(actionId)
    }
  }, 300))
}

const ensureManualQuoteDraft = (action) => {
  const draftModel = getActionDraft(action)
  if (String(action?.action_type || '').trim() !== 'save_manual_quotes') {
    return draftModel
  }
  if (Array.isArray(draftModel.material_lines)) {
    return draftModel
  }
  const preview = action?.preview || {}
  const recommendedSuppliers = Array.isArray(preview.supplier_options) ? preview.supplier_options : []
  const materialLines = Array.isArray(preview.material_lines) ? preview.material_lines : []
  const materialHistoryMap = {}
  if (Array.isArray(preview.material_history)) {
    for (const hist of preview.material_history) {
      const code = String(hist?.material_code || '').trim()
      if (code) {
        materialHistoryMap[code] = hist
      }
    }
  }
  draftModel.material_lines = materialLines.map((line) => {
    const code = String(line?.material_code || '').trim()
    const hist = code ? materialHistoryMap[code] || null : null
    return {
      id: line?.id ?? null,
      erp_request_id: line?.erp_request_id || '',
      bill_no: line?.bill_no || '',
      material_code: code,
      material_name: line?.material_name || '',
      material_model: line?.material_model || '',
      qty: Number(line?.qty) || 0,
      delivery_date: line?.delivery_date || '',
      target_price: line?.target_price ?? preview.target_price_suggestion ?? '',
      quote_suppliers: (recommendedSuppliers.length ? recommendedSuppliers : [{}]).map((supplier) => ({
        supplier_id: Number(supplier?.supplier_id) || null,
        supplier_code: supplier?.supplier_code || '',
        supplier_name: supplier?.supplier_name || '',
        price: supplier?.avg_price ?? '',
        qty: Number(line?.qty) || 0,
        delivery_date: line?.delivery_date || '',
        suggested_price: supplier?.avg_price ?? null,
        recommend_reason: supplier?.recommend_reason || '',
      })),
      material_history: hist,
    }
  })
  return draftModel
}

const getManualQuoteLines = (action) => {
  const draftModel = ensureManualQuoteDraft(action)
  return Array.isArray(draftModel.material_lines) ? draftModel.material_lines : []
}

const buildManualQuoteOverrides = (action) => {
  if (String(action?.action_type || '').trim() !== 'save_manual_quotes') {
    return {}
  }
  const draftModel = ensureManualQuoteDraft(action)
  return {
    title: String(draftModel.title || '').trim(),
    manual_quote_entries: Array.isArray(draftModel.material_lines)
      ? draftModel.material_lines
        .map((line) => ({
          request_id: line?.id || null,
          erp_request_id: line?.erp_request_id || null,
          material_code: line?.material_code || '',
          suppliers: Array.isArray(line?.quote_suppliers)
            ? line.quote_suppliers
              .filter((supplier) => Number(supplier?.price || 0) > 0 && Number(supplier?.qty || 0) > 0 && (supplier?.supplier_name || supplier?.supplier_code))
              .map((supplier) => ({
                supplier_id: supplier?.supplier_id || null,
                supplier_code: supplier?.supplier_code || '',
                supplier_name: supplier?.supplier_name || '',
                price: Number(supplier?.price || 0),
                qty: Number(supplier?.qty || 0),
                delivery_date: supplier?.delivery_date || null,
              }))
            : [],
        }))
        .filter((line) => line.material_code && Array.isArray(line.suppliers) && line.suppliers.length > 0)
      : [],
  }
}

const hasManualQuoteEntries = (action) => {
  const overrides = buildManualQuoteOverrides(action)
  return Array.isArray(overrides.manual_quote_entries) && overrides.manual_quote_entries.length > 0
}

const getActionConfirmLabel = (action) => {
  if (String(action?.action_type || '').trim() === 'save_manual_quotes') {
    return hasManualQuoteEntries(action) ? '生成比价方案' : '填写报价后生成比价方案'
  }
  return getPendingActionButtonLabel(action)
}

const addManualQuoteSupplier = (action, lineIndex) => {
  const line = getManualQuoteLines(action)[lineIndex]
  if (!line) return
  if (!Array.isArray(line.quote_suppliers)) {
    line.quote_suppliers = []
  }
  line.quote_suppliers.push({
    supplier_id: null,
    supplier_code: '',
    supplier_name: '',
    price: '',
    qty: Number(line.qty) || 0,
    delivery_date: line.delivery_date || '',
    suggested_price: null,
    recommend_reason: '',
  })
}

const removeManualQuoteSupplier = (action, lineIndex, supplierIndex) => {
  const line = getManualQuoteLines(action)[lineIndex]
  if (!line || !Array.isArray(line.quote_suppliers)) return
  line.quote_suppliers.splice(supplierIndex, 1)
  if (!line.quote_suppliers.length) {
    addManualQuoteSupplier(action, lineIndex)
  }
}

const normalizeSupplierSearchOption = (supplier = {}) => ({
  value: supplier?.name || supplier?.value || '',
  id: Number(supplier?.id || supplier?.supplier_id) || null,
  code: supplier?.code || supplier?.supplier_code || '',
  name: supplier?.name || supplier?.supplier_name || supplier?.value || '',
  grade: supplier?.grade || supplier?.supplier_grade || '',
})

const getManualSupplierBaseOptions = (action, lineIndex) => {
  const line = getManualQuoteLines(action)[lineIndex]
  const seen = new Map()
  ;(Array.isArray(line?.quote_suppliers) ? line.quote_suppliers : []).forEach((supplier) => {
    const option = normalizeSupplierSearchOption(supplier)
    const key = `${option.id || ''}:${option.code}:${option.name}`.trim()
    if (option.name && !seen.has(key)) {
      seen.set(key, option)
    }
  })
  return Array.from(seen.values())
}

const applyManualSupplierSelection = (supplier, item) => {
  supplier.supplier_id = Number(item?.id) || null
  supplier.supplier_name = item?.name || item?.value || ''
  supplier.supplier_code = item?.code || supplier.supplier_code || ''
}

const handleManualSupplierNameInput = (supplier) => {
  supplier.supplier_id = null
  supplier.supplier_code = ''
}

const querySearchManualSuppliers = async (action, lineIndex, supplierIndex, queryString, cb) => {
  const keyword = String(queryString || '').trim()
  const localOptions = getManualSupplierBaseOptions(action, lineIndex)
  const localMatched = keyword
    ? localOptions.filter((item) => {
        const name = String(item?.name || '').toLowerCase()
        const code = String(item?.code || '').toLowerCase()
        const search = keyword.toLowerCase()
        return name.includes(search) || code.includes(search)
      })
    : localOptions

  if (!keyword) {
    cb(localMatched.slice(0, 12))
    return
  }

  try {
    const { data } = await api.get('/supplier/list', {
      params: {
        page: 1,
        page_size: 20,
        keyword,
      },
      silentError: true,
    })
    const remoteOptions = (Array.isArray(data?.list) ? data.list : [])
      .map((item) => normalizeSupplierSearchOption(item))
      .filter((item) => item.name)
    const merged = new Map()
    ;[...localMatched, ...remoteOptions].forEach((item) => {
      const key = `${item.id || ''}:${item.code}:${item.name}`.trim()
      if (item.name && !merged.has(key)) {
        merged.set(key, item)
      }
    })
    cb(Array.from(merged.values()).slice(0, 20))
  } catch {
    cb(localMatched.slice(0, 12))
  }
}

const getAllocationTotal = (action) => {
  const draftModel = getActionDraft(action)
  const total = Array.isArray(draftModel.allocations)
    ? draftModel.allocations.reduce((sum, item) => sum + (Number(item?.allocated_ratio) || 0), 0)
    : 0
  return Number(total.toFixed(2))
}

const toggleManualCompareEditing = (action) => {
  const draftModel = getActionDraft(action)
  draftModel.editing = !draftModel.editing
}

const clampPanelBounds = () => {
  const maxWidth = Math.max(minWidth, window.innerWidth - maxWidthPadding)
  const maxHeight = Math.max(minHeight, window.innerHeight - maxHeightPadding)

  panelWidth.value = Math.min(Math.max(panelWidth.value, minWidth), maxWidth)
  panelHeight.value = Math.min(Math.max(panelHeight.value, minHeight), maxHeight)

  const maxRight = Math.max(12, window.innerWidth - panelWidth.value - 12)
  const maxBottom = Math.max(12, window.innerHeight - panelHeight.value - 12)
  panelRight.value = Math.min(Math.max(panelRight.value, 12), maxRight)
  panelBottom.value = Math.min(Math.max(panelBottom.value, 12), maxBottom)
}

const resetPanelPosition = () => {
  panelWidth.value = Math.min(920, window.innerWidth - maxWidthPadding)
  panelHeight.value = Math.min(720, window.innerHeight - maxHeightPadding)
  panelRight.value = window.innerWidth <= 768 ? 12 : 24
  panelBottom.value = window.innerWidth <= 768 ? 82 : 94
  clampPanelBounds()
}

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

const dismissPendingAction = (action) => {
  const normalizedId = Number(action?.pending_action_id)
  if (!Number.isFinite(normalizedId) || normalizedId <= 0) return
  if (!dismissedPendingActionIds.value.includes(normalizedId)) {
    dismissedPendingActionIds.value = [...dismissedPendingActionIds.value, normalizedId]
  }
}

const confirmAction = async (action, extraOverrides = {}) => {
  const normalizedId = Number(action?.pending_action_id)
  if (!Number.isFinite(normalizedId) || normalizedId <= 0) return
  if (confirmingActionIds.value.includes(normalizedId)) return

  confirmingActionIds.value = [...confirmingActionIds.value, normalizedId]
  try {
    const { data } = await confirmProcurementAgentAction(normalizedId, {
      ...buildActionOverrides(action),
      ...buildManualQuoteOverrides(action),
      ...extraOverrides,
    })
    if (data?.already_processed) {
      // 动作已被确认过，幂等处理：不重复执行，仅移除卡片
      ElMessage.info('该动作已处理，无需重复确认')
      delete pendingActionDrafts.value[normalizedId]
      dismissPendingAction(action)
      return
    }
    ElMessage.success('AI 待确认动作已执行')
    window.dispatchEvent(new CustomEvent('procurement-agent-action-confirmed', { detail: data }))
    delete pendingActionDrafts.value[normalizedId]
    const nextPendingAction = data?.result?.next_pending_action
    messages.value.push({
      id: `${Date.now()}_confirm`,
      role: 'assistant',
      content: `已完成确认动作：${data?.action_type || normalizedId}`,
      created_at: Math.floor(Date.now() / 1000),
      metadata: nextPendingAction ? {
        tool_results: [{
          name: nextPendingAction.action_type || 'next_pending_action',
          data: nextPendingAction,
        }],
      } : {},
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
  messages.value.push({
    id: `${Date.now()}_user`,
    role: 'user',
    content: message,
    created_at: Math.floor(Date.now() / 1000),
  })
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

const ensureLoaded = async () => {
  if (!visible.value) return
  if (hasInitialized.value) return
  if (ensureLoadedPromise) return ensureLoadedPromise
  ensureLoadedPromise = (async () => {
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
    hasInitialized.value = true
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '初始化采购助手失败')
  } finally {
    pageLoading.value = false
    ensureLoadedPromise = null
  }
  })()
  return ensureLoadedPromise
}

const handlePointerMove = (event) => {
  if (dragState.active) {
    panelRight.value = dragState.startRight - (event.clientX - dragState.startX)
    panelBottom.value = dragState.startBottom - (event.clientY - dragState.startY)
    clampPanelBounds()
  }

  if (resizeState.active) {
    panelWidth.value = resizeState.startWidth + (event.clientX - resizeState.startX)
    panelHeight.value = resizeState.startHeight + (event.clientY - resizeState.startY)
    clampPanelBounds()
  }
}

const stopInteractions = () => {
  dragState.active = false
  resizeState.active = false
}

const handleAgentOpen = async (event) => {
  const prompt = String(event?.detail?.prompt || '').trim()
  if (prompt) {
    draft.value = prompt
  }
  if (!expanded.value) {
    expanded.value = true
  }
  clampPanelBounds()
  await ensureLoaded()
  scrollToBottom()
}

const handleAgentContextUpdated = () => {
  pageContextVersion.value += 1
}

const startDrag = (event) => {
  if (window.innerWidth <= 768) return
  dragState.active = true
  dragState.startX = event.clientX
  dragState.startY = event.clientY
  dragState.startRight = panelRight.value
  dragState.startBottom = panelBottom.value
}

const startResize = (event) => {
  if (window.innerWidth <= 768) return
  resizeState.active = true
  resizeState.startX = event.clientX
  resizeState.startY = event.clientY
  resizeState.startWidth = panelWidth.value
  resizeState.startHeight = panelHeight.value
}

const toggleExpanded = async () => {
  expanded.value = !expanded.value
  if (expanded.value) {
    clampPanelBounds()
    await ensureLoaded()
    scrollToBottom()
  }
}

onMounted(() => {
  syncAuthSnapshot()
  resetPanelPosition()
  pageContextVersion.value += 1
  window.addEventListener('resize', resetPanelPosition)
  window.addEventListener('pointermove', handlePointerMove)
  window.addEventListener('pointerup', stopInteractions)
  window.addEventListener('pointercancel', stopInteractions)
  window.addEventListener('procurement-agent-open', handleAgentOpen)
  window.addEventListener('procurement-agent-context-updated', handleAgentContextUpdated)
  window.addEventListener('auth-changed', syncAuthSnapshot)
  window.addEventListener('focus', syncAuthSnapshot)
})

onBeforeUnmount(() => {
  actionDraftSaveTimers.forEach((timerId) => clearTimeout(timerId))
  actionDraftSaveTimers.clear()
  window.removeEventListener('resize', resetPanelPosition)
  window.removeEventListener('pointermove', handlePointerMove)
  window.removeEventListener('pointerup', stopInteractions)
  window.removeEventListener('pointercancel', stopInteractions)
  window.removeEventListener('procurement-agent-open', handleAgentOpen)
  window.removeEventListener('procurement-agent-context-updated', handleAgentContextUpdated)
  window.removeEventListener('auth-changed', syncAuthSnapshot)
  window.removeEventListener('focus', syncAuthSnapshot)
})

watch(() => route.fullPath, () => {
  syncAuthSnapshot()
})
</script>

<style scoped>
.agent-widget {
  position: fixed;
  right: 24px;
  bottom: 24px;
  z-index: 2100;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 14px;
}

.agent-panel {
  position: fixed;
  border-radius: 24px;
  overflow: hidden;
  display: grid;
  grid-template-columns: 280px minmax(0, 1fr);
  background: #f7fafc;
  border: 1px solid #d9e3ef;
  box-shadow: 0 24px 70px rgba(22, 33, 24, 0.24);
}

.panel-sidebar {
  background: linear-gradient(180deg, #f2f7ff 0%, #edf4ff 100%);
  border-right: 1px solid #dbe6f2;
  display: flex;
  flex-direction: column;
  min-width: 0;
  overflow: hidden;
}

.panel-sidebar.collapsed {
  width: 64px;
}

.panel-main {
  display: grid;
  grid-template-rows: auto auto minmax(0, 1fr) auto;
  min-width: 0;
  min-height: 0;
  background:
    radial-gradient(circle at top right, rgba(80, 145, 255, 0.08), transparent 22%),
    linear-gradient(180deg, #f8fbff 0%, #f4f8fc 100%);
}

.sidebar-top {
  padding: 18px 16px 12px;
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 10px;
}

.sidebar-kicker,
.panel-kicker,
.message-role,
.footer-tip {
  font-size: 12px;
  letter-spacing: 0.04em;
  color: #72839a;
}

.sidebar-top h3,
.panel-header h2 {
  margin: 6px 0 0;
  color: #1f2b3d;
}

.sidebar-actions {
  padding: 0 16px 14px;
}

.session-list {
  flex: 1;
  overflow-y: auto;
  min-height: 0;
  padding: 0 14px 14px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.session-item {
  text-align: left;
  border: 1px solid #d7e2f0;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.92);
  padding: 12px;
  cursor: pointer;
}

.session-item.active {
  border-color: #2c67d9;
  background: #ffffff;
  box-shadow: 0 10px 24px rgba(44, 103, 217, 0.12);
}

.session-title {
  font-size: 14px;
  font-weight: 600;
  color: #21324a;
}

.session-preview {
  margin-top: 6px;
  font-size: 12px;
  color: #6b7a90;
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.session-meta {
  margin-top: 8px;
  display: flex;
  justify-content: space-between;
  font-size: 11px;
  color: #8a97aa;
}

.session-empty {
  padding: 18px 12px;
  text-align: center;
  color: #7d8da3;
}

.panel-header {
  padding: 20px 22px 16px;
  border-bottom: 1px solid #dde6f2;
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  cursor: move;
  user-select: none;
}

.panel-title {
  min-width: 0;
}

.panel-header p {
  margin: 8px 0 0;
  color: #76879d;
}

.panel-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.pending-action-summary {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 13px;
  color: #345;
  line-height: 1.5;
}

.pending-action-button-row {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.pending-action-allocation-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.pending-action-allocation-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 140px;
  gap: 8px;
  align-items: center;
  padding: 6px 8px;
  border: 1px solid #ebeef5;
  border-radius: 6px;
}

.pending-action-allication-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.pending-action-allocation-name {
  font-size: 13px;
  font-weight: 600;
  color: #1f2b3d;
}

.pending-action-allocation-meta {
  font-size: 11px;
  color: #607287;
}

.pending-action-allocation-reason {
  font-size: 11px;
  color: #909399;
}

.pending-action-allocation-control {
  display: flex;
  align-items: center;
  gap: 4px;
  justify-content: flex-end;
}

.pending-action-allocation-suffix {
  font-size: 13px;
  color: #607287;
}

.manual-quote-block {
  padding: 10px;
  border-radius: 12px;
  background: #ffffff;
  border: 1px solid #dce6f2;
}

.manual-quote-block-header {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 8px;
}

.manual-quote-block-title {
  font-size: 13px;
  font-weight: 700;
  color: #1f2b3d;
}

.manual-quote-block-meta {
  font-size: 12px;
  color: #607287;
}

.manual-quote-supplier-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin: 8px 0;
}

.manual-quote-history {
  margin: 8px 0;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  overflow: hidden;
}

.manual-quote-history :deep(.el-collapse) {
  border: none;
}

.manual-quote-history :deep(.el-collapse-item__header) {
  padding: 0 12px;
  font-size: 12px;
  font-weight: 600;
  color: #303133;
  background: #fafafa;
}

.manual-quote-history :deep(.el-collapse-item__content) {
  padding: 8px 12px;
}

.history-table-wrap {
  overflow-x: auto;
}

.history-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 11px;
  white-space: nowrap;
}

.history-table th,
.history-table td {
  padding: 4px 8px;
  border: 1px solid #ebeef5;
  text-align: left;
}

.history-table th {
  background: #f5f7fa;
  font-weight: 600;
  color: #606266;
}

.history-table td {
  color: #303133;
}

.manual-quote-supplier-head {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
  padding: 0 10px;
  font-size: 12px;
  font-weight: 600;
  color: #607287;
}

.manual-quote-supplier-row {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
  align-items: start;
  padding: 10px;
  border-radius: 10px;
  background: #f8fbff;
  border: 1px solid #e0e9f5;
}

.manual-quote-supplier-row :deep(.el-input),
.manual-quote-supplier-row :deep(.el-input-number) {
  width: 100%;
  min-width: 0;
}

.manual-supplier-option {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
}

.manual-supplier-option-name {
  color: #1f2b3d;
}

.manual-supplier-option-code {
  color: #7d8da3;
  font-size: 12px;
  flex-shrink: 0;
}

.manual-quote-supplier-row > :deep(.el-button) {
  grid-column: 1 / -1;
  justify-self: end;
  white-space: nowrap;
}

.manual-quote-supplier-hint {
  grid-column: 1 / -1;
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  font-size: 12px;
  color: #6b7a90;
  padding-top: 2px;
}

.flow-mode-bar {
  padding: 14px 22px;
  border-bottom: 1px solid #dde6f2;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  background: rgba(255, 255, 255, 0.72);
}

.flow-mode-summary {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  align-items: center;
}

.flow-mode-label {
  font-size: 14px;
  font-weight: 600;
  color: #1f2b3d;
}

.flow-mode-count {
  font-size: 13px;
  color: #607287;
}

.flow-mode-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.mode-chip {
  border: 1px solid #cfdced;
  background: #fff;
  color: #345;
  border-radius: 999px;
  padding: 8px 14px;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.mode-chip:hover {
  border-color: #2c67d9;
  color: #2c67d9;
}

.mode-chip.active {
  border-color: #2c67d9;
  background: #2c67d9;
  color: #fff;
  box-shadow: 0 8px 18px rgba(44, 103, 217, 0.18);
}

.mode-chip-clear {
  background: #f7fafc;
}

.messages-area {
  overflow-y: auto;
  min-height: 0;
  padding: 18px 22px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.empty-state {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100%;
}

.empty-card {
  width: min(540px, 100%);
  padding: 24px;
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.92);
  border: 1px solid #dbe6f2;
}

.empty-card h4 {
  margin: 0 0 14px;
  font-size: 18px;
  color: #223249;
}

.empty-suggestions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.message-row {
  display: flex;
}

.message-row.is-user {
  justify-content: flex-end;
}

.message-bubble {
  max-width: 82%;
  padding: 13px 15px;
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

.message-text {
  white-space: pre-wrap;
  line-height: 1.7;
  font-size: 14px;
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

.recommended-supplier-list {
  display: grid;
  gap: 8px;
}

.selected-supplier-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.selected-supplier-tag {
  display: inline-flex;
  align-items: center;
  padding: 6px 10px;
  border-radius: 999px;
  background: #ebf4ff;
  border: 1px solid #cfe0f6;
  color: #23456b;
  font-size: 12px;
  font-weight: 600;
}

.recommended-supplier-card {
  padding: 10px 12px;
  border-radius: 12px;
  background: #ffffff;
  border: 1px solid #dce6f2;
}

.recommended-supplier-name {
  font-size: 13px;
  font-weight: 700;
  color: #1f2b3d;
}

.recommended-supplier-meta {
  margin-top: 4px;
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  font-size: 12px;
  color: #607287;
}

.recommended-supplier-reason {
  margin-top: 4px;
  font-size: 12px;
  color: #6b7a90;
  line-height: 1.5;
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

.panel-footer {
  padding: 16px 22px 18px;
  border-top: 1px solid #dde6f2;
  background: #f9fbfe;
}

.chat-input {
  width: 100%;
  resize: none;
  border: 1px solid #cfdbeb;
  border-radius: 16px;
  background: #fff;
  padding: 12px 14px;
  box-sizing: border-box;
  font: inherit;
  outline: none;
}

.chat-input:focus {
  border-color: #5183e6;
  box-shadow: 0 0 0 3px rgba(81, 131, 230, 0.12);
}

.footer-actions {
  margin-top: 10px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.primary-btn,
.ghost-btn,
.send-btn,
.floating-trigger,
.prompt-chip,
.icon-btn,
.resize-handle {
  border: 0;
}

.primary-btn {
  width: 100%;
  padding: 12px 14px;
  border-radius: 14px;
  background: #2f67d4;
  color: #fff;
  font-weight: 600;
}

.ghost-btn,
.icon-btn {
  background: rgba(255, 255, 255, 0.8);
  color: #214530;
  border-radius: 999px;
  padding: 8px 12px;
}

.icon-btn {
  width: 34px;
  height: 34px;
  padding: 0;
  font-size: 18px;
  cursor: pointer;
}

.model-pill {
  padding: 8px 12px;
  border-radius: 999px;
  background: #ebf2ff;
  color: #2b5ebc;
  font-size: 13px;
}

.prompt-chip {
  border: 1px solid #d8e3f1;
  border-radius: 999px;
  background: #f7faff;
  padding: 10px 14px;
  color: #27456f;
  cursor: pointer;
}

.send-btn {
  padding: 10px 18px;
  border-radius: 999px;
  background: #225836;
  color: #fff;
  font-weight: 600;
  cursor: pointer;
}

.send-btn:disabled,
.ghost-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.floating-trigger {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  padding: 14px 18px;
  border-radius: 999px;
  background: linear-gradient(135deg, #173f29 0%, #2f7a49 100%);
  color: #fffef9;
  box-shadow: 0 18px 40px rgba(18, 49, 31, 0.24);
  font-weight: 600;
  cursor: pointer;
}

.trigger-badge {
  width: 30px;
  height: 30px;
  border-radius: 999px;
  display: grid;
  place-items: center;
  background: rgba(255, 255, 255, 0.16);
}

.resize-handle {
  position: absolute;
  right: 6px;
  bottom: 6px;
  width: 22px;
  height: 22px;
  background: linear-gradient(135deg, transparent 0 45%, rgba(47, 103, 212, 0.25) 45% 55%, rgba(47, 103, 212, 0.55) 55% 100%);
  cursor: nwse-resize;
  border-radius: 6px;
}

.agent-fade-enter-active,
.agent-fade-leave-active {
  transition: all 0.22s ease;
}

.agent-fade-enter-from,
.agent-fade-leave-to {
  opacity: 0;
  transform: translateY(12px) scale(0.98);
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
  .agent-panel {
    grid-template-columns: 1fr;
  }

  .panel-sidebar {
    max-height: 240px;
  }

  .panel-sidebar.collapsed {
    width: 100%;
  }
}

@media (max-width: 768px) {
  .agent-widget {
    right: 12px;
    left: 12px;
    bottom: 12px;
    align-items: stretch;
  }

  .panel-header,
  .footer-actions {
    flex-direction: column;
    align-items: flex-start;
  }

  .panel-header {
    cursor: default;
  }

  .message-bubble {
    max-width: 100%;
  }

  .floating-trigger {
    justify-content: center;
  }

  .resize-handle {
    display: none;
  }

  .manual-quote-supplier-head,
  .manual-quote-supplier-row {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
