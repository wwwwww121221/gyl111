# 采购智能体模块说明

这个目录专门存放采购智能体相关代码，和原有询价、比价、合同等业务模块解耦。

## 当前版本做什么

当前是一个查询型智能体 MVP：

1. 用户在前端“采购智能体”页面提问。
2. 后端 `routers/agent.py` 接收请求。
3. `ProcurementAgentRunner` 根据问题选择只读工具。
4. 工具从 PostgreSQL 查询真实业务数据。
5. LangChain `ChatPromptTemplate` 组装 system prompt、用户问题、会话记忆和工具结果。
6. 调用项目已有 `services.llm_factory` 中的大模型服务生成回答。

当前版本不会自动创建询价、发送消息、修改合同或确认中标。

## 文件职责

- `schemas.py`：智能体接口输入输出结构。
- `prompts.py`：LangChain 提示词模板，包含 system/user prompt。
- `tools.py`：LangChain `StructuredTool` 工具定义和真实查询函数。
- `memory.py`：会话记忆。优先保存到 Redis，Redis 不可用时退回进程内存。
- `runner.py`：智能体主流程，负责规划工具、执行工具、组装 prompt、调用模型。

## 工具设计

当前只开放只读工具：

- `search_material`：查询物料主数据。
- `search_suppliers`：查询供应商档案。
- `get_material_price_history`：查询物料历史采购价格和月度趋势。
- `get_supplier_purchase_profile`：查询供应商历史供货概况。

面试表达：

> 我把业务能力封装成 LangChain StructuredTool，每个工具都有明确的参数 schema 和 description。这样模型或执行器可以理解工具用途，同时工具内部仍然由后端控制权限和数据查询逻辑。

## 提示词设计

`prompts.py` 中的 system prompt 主要约束：

- 必须基于工具返回的真实数据回答。
- 没有数据时不能编造。
- 当前版本只能做只读分析。
- 涉及采购动作必须说“建议/需人工确认”。

面试表达：

> system prompt 用来定义智能体角色、边界和安全约束；user prompt 用来注入用户问题、会话记忆和工具观测结果。

## 记忆怎么保存

`memory.py` 使用 Redis 保存最近几轮消息：

- key：`agent:user:{user_id}:session:{session_id}:messages`
- TTL：24 小时
- 最多保留最近 12 条消息

如果 Redis 不可用，会退回进程内存，方便开发测试。

面试表达：

> 这里的 memory 是短期对话记忆，不是知识库。它只保存最近上下文，帮助智能体理解用户连续追问。

## 后续怎么加向量库

向量库适合存非结构化知识：

- 采购制度
- 合同条款
- 供应商准入规则
- 质量协议
- 历史谈判记录

推荐后续新增：

- `vector_store.py`
- Qdrant Docker 服务
- `retrieve_policy_docs` 工具

面试表达：

> 结构化业务数据走 SQL 工具，非结构化制度和合同文档走向量检索，最后由大模型融合回答。
