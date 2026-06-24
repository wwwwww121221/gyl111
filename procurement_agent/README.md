# 采购 AI 助手模块说明

`procurement_agent/` 目录用于承载 gyl111 项目中的采购智能体能力。当前版本已经不是单纯的“查询型助手”，而是一个遵循安全边界的全过程采购智能体，覆盖以下链路：

`采购申请勾选 -> AI 生成询价草稿 -> 人工确认 -> 创建询价任务 -> 智能比价 -> 确认中标 -> 生成合同草稿 -> 合同风险检查`

模块设计目标有两条：

1. AI 只能基于真实数据库和工具结果回答，不能编造物料、价格、供应商、合同条款。
2. AI 只能生成建议、草稿或待确认动作，不能直接发送询价、确认中标、提交合同或删除数据。

## 当前能力

当前采购智能体分为两类能力：

1. 只读分析能力
2. 草稿/待确认写入能力

只读分析能力包括：

- 查询物料主数据
- 查询供应商档案
- 查询历史采购价格和价格趋势
- 查询采购申请和采购订单
- 推荐询价供应商
- 询价比价分析
- 合同风险检查

草稿/待确认写入能力包括：

- 基于当前勾选采购申请生成询价任务草稿
- 基于单个物料生成询价草稿
- 生成询价话术
- 生成中标待确认动作
- 生成合同草稿待确认动作

这些写入能力统一采用：

`AI 生成 -> AgentPendingAction -> 人工确认 -> 正式落库`

## 目录职责

- `runner.py`
  采购智能体主流程。负责合并页面上下文、规划工具、补全工具参数、执行工具、组织 prompt、调用大模型。

- `tools.py`
  智能体工具注册中心。定义所有 `StructuredTool` 的参数 schema、描述和闭包注入逻辑。

- `write_tools.py`
  写工具实现。负责生成询价草稿、勾选采购申请发起询价、合同草稿、待确认动作以及确认后的正式落库。

- `risk_checker.py`
  风险和分析工具。负责推荐询价供应商、询价比价分析、合同风险检查。

- `prompts.py`
  system prompt 和 tool planner prompt。明确业务边界、安全约束和工具使用规则。

- `schemas.py`
  智能体接口输入输出结构，例如 `/agent/chat`、会话消息、memory 结构。

- `memory.py`
  会话短期记忆和长期记忆。保存消息、会话摘要以及工具结果元数据。

- `README.md`
  模块说明文档。

## 页面上下文机制

采购智能体现在不再只依赖用户自然语言里的关键词，还会结合前端页面上下文。

前端会通过 `/agent/chat` 的 `context` 传入当前页面信息。当前已支持的关键字段包括：

- `route_name`
- `bill_no`
- `material_code`
- `material_name`
- `material_model`
- `qty`
- `delivery_date`
- `target_price`
- `supplier_id`
- `supplier_code`
- `supplier_name`
- `inquiry_id`
- `contract_id`
- `selected_request_ids`
- `selected_requests`

其中 `selected_request_ids` 和 `selected_requests` 是当前版本的重要增强点，主要用于“采购申请列表勾选后直接发起询价”的场景。

`runner.py` 会把这些上下文合并到消息里，并在工具参数补全时优先使用：

- 当前勾选采购申请
- 当前页面物料
- 当前页面询价任务
- 当前页面合同

这样可以避免智能体把“单据编号”误识别成“物料编码”，也可以让它直接拿到勾选行中的数量、交期、目标价等业务字段。

## 工具清单

### 只读工具

- `search_material`
  按物料编码、名称、规格等查询物料主数据。

- `search_suppliers`
  按供应商编码、名称、短名、分组、等级查询供应商档案。

- `search_purchase_requests`
  查询采购申请明细。

- `search_purchase_orders`
  查询采购订单和历史采购记录。

- `get_material_price_history`
  查询物料历史采购价格、供应商供货情况和月度趋势。

- `get_supplier_purchase_profile`
  查询供应商历史供货概况。

### 分析/风控工具

- `recommend_suppliers_for_inquiry`
  根据历史价格、供货记录、供应商评分、状态、近期交易情况推荐询价供应商。

- `analyze_quotation_compare`
  对询价任务下的报价做价格、交期、评分、历史均价分析，并生成中标建议和待确认动作。

- `check_contract_risks`
  检查合同金额、供应商名称、物料明细、交期、付款方式、质量条款、违约责任等是否缺失或异常。

### 写工具

- `create_inquiry_from_selected_requests`
  基于当前勾选采购申请生成待确认询价任务。不会直接发布询价。

- `create_inquiry_draft`
  基于物料、数量、交期和推荐供应商生成待确认询价草稿。确认后创建 `ai_draft` 状态的询价任务。

- `generate_inquiry_message`
  生成询价话术文本，不直接发送。

- `create_contract_draft_from_award`
  基于建议中标供应商和合同模板生成待确认合同草稿，不直接提交正式合同。

## AgentPendingAction 机制

所有 AI 写动作统一先落到 `agent_pending_actions` 表。

核心字段：

- `action_type`
- `payload`
- `preview`
- `status`
- `created_by`
- `confirmed_by`
- `created_at`
- `confirmed_at`

常见 `action_type`：

- `create_inquiry_from_selected_requests`
- `create_inquiry_draft`
- `confirm_award`
- `create_contract_draft`

确认接口：

- `POST /agent/actions/{id}/confirm`

确认后的处理逻辑在 `write_tools.confirm_pending_action()` 中统一分发。

## 询价链路

### 1. 采购申请勾选

采购申请列表页勾选后，会把以下信息写入 `sessionStorage` 中的 `procurement_agent_page_context`：

- 勾选明细 id
- ERP request id
- bill_no
- material_code / material_name / material_model
- qty / delivery_date / target_price

### 2. AI 发起询价

用户可以：

- 直接点击页面上的“把勾选物料发起询价”
- 或在 AI 助手中输入类似“把勾选物料发起询价”

此时智能体优先调用 `create_inquiry_from_selected_requests`。

### 3. 生成待确认动作

AI 不会直接创建正式询价，而是生成一个 `pending_confirmation` 动作，并在聊天卡片中返回确认按钮。

### 4. 人工确认

用户点击“确认创建询价任务”后：

- 若勾选采购申请已在 `InquiryRequest` 中存在，则直接复用
- 若尚未存在，则基于勾选行补齐 `InquiryRequest`
- 创建 `InquiryTask`
- 创建 `InquiryTaskItem`
- 如有推荐供应商，则创建 `InquirySupplier`
- 初始状态为 `TaskStatus.AI_DRAFT`

### 5. 列表刷新

确认成功后，前端会广播 `procurement-agent-action-confirmed` 事件，采购申请列表和询价任务列表会自动刷新。

## 比价与中标链路

`analyze_quotation_compare` 会对询价任务下的供应商报价进行分析，输出：

- 供应商报价对比
- 历史均价参考
- 评分
- 中标建议

该工具不会自动中标，而是生成 `confirm_award` 类型的 `AgentPendingAction`。

用户确认后，后端会复用现有正式定标流程：

- 调用 `routers.inquiry.close_inquiry_task(...)`
- 更新中标结果
- 保留操作日志

## 合同链路

在完成中标建议后，智能体可以继续：

1. 调用 `create_contract_draft_from_award`
2. 生成待确认合同草稿动作
3. 人工确认后创建合同草稿记录
4. 调用 `check_contract_risks` 做合同风险检查

这里仍然遵循“AI 生成草稿 + 人工确认”的模式，不允许 AI 直接提交正式合同。

## 权限与安全边界

权限控制分三层：

1. 页面可见性
   只有采购部用户可见采购 AI 助手。

2. 路由与接口校验
   `/agent/*` 接口会校验当前用户角色和部门。

3. 工具内校验
   写工具和风险工具内部都会再次校验采购权限。

system prompt 中还明确约束：

- 只能基于真实数据库和工具结果回答
- 不能编造价格、供应商、合同条款
- 遇到无数据时必须明确说明“数据不足”
- 涉及业务动作时只能输出建议、草稿或待确认动作

## 操作日志

所有 AI 写入动作和确认动作都会记录 `operation_logs`。

典型日志包括：

- `AGENT_CREATE_INQUIRY_FROM_SELECTED_REQUESTS`
- `AGENT_CREATE_INQUIRY_DRAFT`
- `AGENT_ANALYZE_QUOTATION`
- `AGENT_CREATE_CONTRACT_DRAFT`
- `AGENT_CONFIRM_ACTION`

日志中会保留：

- 操作人
- 动作类型
- 模块
- 目标对象
- 结果
- `pending_action_id`
- 关联 task / supplier / request 信息

## 当前实现边界

虽然当前模块已经覆盖了全过程采购智能体的主链路，但仍有几点需要注意：

1. AI 不直接发送询价消息给供应商，`generate_inquiry_message` 只生成文本。
2. AI 不直接发布询价任务，必须通过待确认动作。
3. AI 不直接确认中标，必须通过 `confirm_award` 待确认动作。
4. AI 不直接提交合同，合同也必须先生成草稿。
5. 智能体的部分上下文解析仍然是基于 prompt 中嵌入的结构化文本，后续可以继续演进为更显式的上下文对象驱动。

## 推荐后续演进

建议后续继续增强：

1. 为 `/agent/chat` 的 `context` 增加正式 schema，而不是完全依赖自由 dict。
2. 增加“发布询价”待确认动作，和真正的供应商通知动作解耦。
3. 为合同草稿增加更细的模板变量回填和条款差异比对。
4. 为 AI 助手增加更可见的上下文回显，例如“当前识别到的勾选物料/数量/交期”。
5. 增加端到端自动化测试，覆盖：
   `selected_requests -> pending_action -> confirm -> inquiry_task -> compare -> award -> contract`

## 一句话总结

当前版本的采购智能体已经从“查询助手”升级为“带安全确认机制的全过程采购协同智能体”：

- 能看懂当前页面和勾选上下文
- 能生成询价和合同草稿
- 能做比价和风险检查
- 能推动业务流程前进
- 但所有正式动作都必须人工确认
