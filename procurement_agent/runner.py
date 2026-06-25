from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from models import User
from procurement_agent.guardrails import build_guardrail_response, detect_prompt_injection
from procurement_agent.intent_router import extract_keywords
from procurement_agent.memory import (
    append_message,
    list_long_term_memories,
    load_messages,
    new_session_id,
    recall_long_term_memories,
    save_long_term_memory,
    summarize_recent_messages,
)
from procurement_agent.prompts import AGENT_PROMPT, TOOL_PLANNER_PROMPT
from procurement_agent.schemas import AgentChatResponse, AgentToolResult
from procurement_agent.tools import create_langchain_tools
from schemas import ChatMessage
from services.llm_factory import get_procurement_agent_llm_service


class ProcurementAgentRunner:
    """Small query-only procurement agent."""

    MAX_TOOL_PLANNING_ROUNDS = 2
    MAX_TOOL_ACTIONS_PER_ROUND = 3
    READ_ONLY_TOOL_NAMES = {
        "search_material",
        "search_suppliers",
        "get_material_price_history",
        "get_supplier_purchase_profile",
        "search_purchase_requests",
        "search_purchase_orders",
        "recommend_suppliers_for_inquiry",
        "check_contract_risks",
    }
    AUTO_INQUIRY_TOOL_NAMES = {
        "create_inquiry_draft",
        "create_inquiry_from_selected_requests",
        "generate_inquiry_message",
        "publish_inquiry_task",
        "analyze_quotation_compare",
        "create_contract_draft_from_award",
    }
    MANUAL_COMPARE_TOOL_NAMES = {
        "generate_inquiry_message",
        "analyze_quotation_compare",
        "create_contract_draft_from_award",
        "save_manual_quotes",
    }

    def __init__(self, db: Session, user: User):
        self.db = db
        self.user = user
        self.tools = create_langchain_tools(db, user)

    async def chat(
        self,
        message: str,
        session_id: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> AgentChatResponse:
        session_id = session_id or new_session_id()
        user_id = self.user.id
        context = context or {}
        history = load_messages(user_id, session_id)
        effective_message = self._merge_context_into_message(message, context)
        intent_type = self._classify_user_intent(message)
        flow_mode = self._normalize_flow_mode(context.get("flow_mode"))

        guardrail_reason = detect_prompt_injection(message)
        if guardrail_reason:
            answer = build_guardrail_response(guardrail_reason)
            append_message(user_id, session_id, "user", message)
            append_message(user_id, session_id, "assistant", answer, metadata={"tool_results": []})
            return AgentChatResponse(
                session_id=session_id,
                answer=answer,
                tool_results=[],
                memory_count=len(load_messages(user_id, session_id)),
            )

        memory_text = summarize_recent_messages(history)
        recalled_memories = recall_long_term_memories(user_id, effective_message, limit=3)
        recalled_memory_text = self._format_recalled_memories(recalled_memories)

        if (
            intent_type == "workflow_action"
            and flow_mode in {"auto_inquiry", "manual_compare"}
            and not (context.get("selected_request_ids") or [])
            and not context.get("inquiry_id")
        ):
            answer = "请先在采购申请列表中勾选需要处理的物料。"
            append_message(user_id, session_id, "user", message)
            append_message(user_id, session_id, "assistant", answer, metadata={"tool_results": []})
            return AgentChatResponse(
                session_id=session_id,
                answer=answer,
                tool_results=[],
                memory_count=len(load_messages(user_id, session_id)),
            )

        if (
            intent_type == "workflow_action"
            and flow_mode == "manual_compare"
            and self._has_any_keyword(message, ["发布询价", "发送询价单", "推送供应商", "发询价"])
        ):
            answer = "当前为手动比价模式，不能给供应商发送询价单。请先在线下询价或手动录入报价后再进行比价分析。"
            append_message(user_id, session_id, "user", message)
            append_message(user_id, session_id, "assistant", answer, metadata={"tool_results": []})
            return AgentChatResponse(
                session_id=session_id,
                answer=answer,
                tool_results=[],
                memory_count=len(load_messages(user_id, session_id)),
            )

        if intent_type == "workflow_action" and not flow_mode:
            answer, tool_results = self._build_flow_mode_required_response()
            append_message(user_id, session_id, "user", message)
            append_message(
                user_id,
                session_id,
                "assistant",
                answer,
                metadata={"tool_results": [item.model_dump() for item in tool_results]},
            )
            return AgentChatResponse(
                session_id=session_id,
                answer=answer,
                tool_results=tool_results,
                memory_count=len(load_messages(user_id, session_id)),
            )

        llm = get_procurement_agent_llm_service()
        tool_results = await self._run_query_tools(
            llm=llm,
            message=effective_message,
            memory_text=memory_text,
            recalled_memory_text=recalled_memory_text,
            context=context,
            intent_type=intent_type,
            flow_mode=flow_mode,
        )
        tool_text = self._format_tool_results(tool_results)

        prompt_messages = AGENT_PROMPT.format_messages(
            user_message=effective_message,
            memory_text=memory_text or "无",
            recalled_memory_text=recalled_memory_text or "无",
            tool_text=tool_text or "无工具结果",
        )
        llm_messages = [
            ChatMessage(role=self._to_chat_role(item.type), content=str(item.content))
            for item in prompt_messages
        ]

        response = await llm.chat_completion(llm_messages)

        append_message(user_id, session_id, "user", message)
        append_message(
            user_id,
            session_id,
            "assistant",
            response.content,
            metadata={"tool_results": [item.model_dump() for item in tool_results]},
        )
        self._save_long_term_memory(user_id, session_id, message, response.content, tool_results)

        return AgentChatResponse(
            session_id=session_id,
            answer=response.content,
            tool_results=tool_results,
            memory_count=len(load_messages(user_id, session_id)),
        )

    @staticmethod
    def _merge_context_into_message(message: str, context: dict[str, Any]) -> str:
        if not context:
            return message

        parts = []
        page = str(context.get("page") or "").strip()
        if page:
            parts.append(f"CURRENT_PAGE: {page}")

        flow_mode = str(context.get("flow_mode") or "").strip()
        if flow_mode:
            parts.append(f"CURRENT_FLOW_MODE: {flow_mode}")
        route_name = str(context.get("route_name") or "").strip()
        if route_name:
            parts.append(f"当前页面: {route_name}")

        material_name = str(context.get("material_name") or "").strip()
        material_code = str(context.get("material_code") or "").strip()
        if material_name or material_code:
            parts.append(f"当前物料: {material_name or '-'} / {material_code or '-'}")

        material_model = str(context.get("material_model") or "").strip()
        if material_model:
            parts.append(f"CURRENT_MATERIAL_MODEL: {material_model}")
        bill_no = str(context.get("bill_no") or "").strip()
        if bill_no:
            parts.append(f"CURRENT_BILL_NO: {bill_no}")
        qty = str(context.get("qty") or "").strip()
        if qty:
            parts.append(f"CURRENT_QTY: {qty}")
        delivery_date = str(context.get("delivery_date") or "").strip()
        if delivery_date:
            parts.append(f"CURRENT_DELIVERY_DATE: {delivery_date}")
        selected_request_ids = context.get("selected_request_ids") or []
        if isinstance(selected_request_ids, list) and selected_request_ids:
            parts.append(f"SELECTED_REQUEST_IDS_JSON: {json.dumps(selected_request_ids[:50], ensure_ascii=False, default=str)}")
        selected_requests = context.get("selected_requests") or []
        if isinstance(selected_requests, list) and selected_requests:
            normalized_selected_requests = []
            for row in selected_requests[:20]:
                if not isinstance(row, dict):
                    continue
                normalized_selected_requests.append({
                    "id": row.get("id"),
                    "erp_request_id": row.get("erp_request_id"),
                    "bill_no": row.get("bill_no"),
                    "project_info": row.get("project_info"),
                    "material_code": row.get("material_code"),
                    "material_name": row.get("material_name"),
                    "material_model": row.get("material_model"),
                    "price_unit_name": row.get("price_unit_name"),
                    "qty": row.get("qty"),
                    "delivery_date": row.get("delivery_date"),
                    "target_price": row.get("target_price"),
                })
            if normalized_selected_requests:
                parts.append("SELECTED_REQUESTS_JSON_BEGIN")
                parts.append(json.dumps(normalized_selected_requests, ensure_ascii=False, default=str))
                parts.append("SELECTED_REQUESTS_JSON_END")

        supplier_name = str(context.get("supplier_name") or "").strip()
        supplier_code = str(context.get("supplier_code") or "").strip()
        if supplier_name or supplier_code:
            parts.append(f"当前供应商: {supplier_name or '-'} / {supplier_code or '-'}")

        supplier_id = str(context.get("supplier_id") or "").strip()
        if supplier_id:
            parts.append(f"当前供应商ID: {supplier_id}")

        inquiry_id = str(context.get("inquiry_id") or "").strip()
        if inquiry_id:
            parts.append(f"当前询价单ID: {inquiry_id}")

        contract_id = str(context.get("contract_id") or "").strip()
        if contract_id:
            parts.append(f"当前合同ID: {contract_id}")

        if not parts:
            return message

        return f"{message}\n\n[页面上下文]\n" + "\n".join(parts)

    @staticmethod
    def _extract_context_defaults(message: str) -> dict[str, str]:
        defaults = {
            "page": "",
            "flow_mode": "",
            "bill_no": "",
            "material_name": "",
            "material_code": "",
            "material_model": "",
            "qty": "",
            "delivery_date": "",
            "supplier_name": "",
            "supplier_code": "",
            "supplier_id": "",
            "inquiry_id": "",
            "contract_id": "",
        }

        material_match = re.search(r"当前物料:\s*(.*?)\s*/\s*(.*)", message or "")
        if material_match:
            defaults["material_name"] = material_match.group(1).strip().strip("-")
            defaults["material_code"] = material_match.group(2).strip().strip("-")

        supplier_match = re.search(r"当前供应商:\s*(.*?)\s*/\s*(.*)", message or "")
        if supplier_match:
            defaults["supplier_name"] = supplier_match.group(1).strip().strip("-")
            defaults["supplier_code"] = supplier_match.group(2).strip().strip("-")

        supplier_id_match = re.search(r"褰撳墠渚涘簲鍟咺D:\s*(.*)", message or "")
        if supplier_id_match:
            defaults["supplier_id"] = supplier_id_match.group(1).strip()

        inquiry_id_match = re.search(r"褰撳墠璇环鍗旾D:\s*(.*)", message or "")
        if inquiry_id_match:
            defaults["inquiry_id"] = inquiry_id_match.group(1).strip()

        contract_id_match = re.search(r"褰撳墠鍚堝悓ID:\s*(.*)", message or "")
        if contract_id_match:
            defaults["contract_id"] = contract_id_match.group(1).strip()

        return defaults

    @staticmethod
    def _has_any_keyword(message: str, words: list[str]) -> bool:
        text = str(message or "")
        return any(word in text for word in words)

    @staticmethod
    def _extract_selected_request_ids(message: str) -> list[str]:
        match = re.search(r"SELECTED_REQUEST_IDS_JSON:\s*(\[[\s\S]*?\])", message or "")
        if not match:
            return []
        try:
            payload = json.loads(match.group(1))
        except Exception:
            return []
        if not isinstance(payload, list):
            return []
        return [str(item).strip() for item in payload if str(item).strip()][:50]

    @staticmethod
    def _extract_selected_requests(message: str) -> list[dict[str, Any]]:
        match = re.search(r"SELECTED_REQUESTS_JSON_BEGIN\s*([\s\S]*?)\s*SELECTED_REQUESTS_JSON_END", message or "")
        if not match:
            return []
        try:
            payload = json.loads(match.group(1))
        except Exception:
            return []
        if not isinstance(payload, list):
            return []
        return [item for item in payload if isinstance(item, dict)][:20]

    @staticmethod
    def _normalize_flow_mode(value: Any) -> str | None:
        flow_mode = str(value or "").strip()
        return flow_mode if flow_mode in {"auto_inquiry", "manual_compare"} else None

    def _classify_user_intent(self, message: str) -> str:
        text = str(message or "")
        workflow_keywords = [
            "发起询价", "创建询价任务", "发送询价单", "自动询价", "手动比价",
            "分配份额", "确认中标", "生成合同", "发布询价", "生成询价单",
            "生成询价草稿", "生成合同草稿", "发询价", "推送供应商",
        ]
        if any(keyword in text for keyword in workflow_keywords):
            return "workflow_action"
        return "read_only_query"

    @staticmethod
    def _build_flow_mode_required_response() -> tuple[str, list[AgentToolResult]]:
        answer = (
            "这是业务动作请求，执行前需要先选择流程模式。\n\n"
            "请在 AI 助手顶部选择 `自动询价` 或 `手动比价`，当前我不会创建任何询价、比价、定标或合同数据。"
        )
        tool_results = [
            AgentToolResult(
                name="flow_mode_required",
                args={},
                summary="业务动作需要先选择 flow_mode。",
                data={
                    "intent_type": "workflow_action",
                    "flow_mode_required": True,
                    "available_modes": ["auto_inquiry", "manual_compare"],
                },
            )
        ]
        return answer, tool_results

    def _get_allowed_tools(self, intent_type: str, flow_mode: str | None) -> set[str]:
        if intent_type == "read_only_query":
            return set(self.READ_ONLY_TOOL_NAMES)
        if flow_mode == "auto_inquiry":
            return set(self.READ_ONLY_TOOL_NAMES | self.AUTO_INQUIRY_TOOL_NAMES)
        if flow_mode == "manual_compare":
            return set(self.READ_ONLY_TOOL_NAMES | self.MANUAL_COMPARE_TOOL_NAMES)
        return set(self.READ_ONLY_TOOL_NAMES)

    def _is_tool_allowed(self, tool_name: str, intent_type: str, flow_mode: str | None) -> bool:
        return tool_name in self._get_allowed_tools(intent_type, flow_mode)

    def _build_seed_actions(
        self,
        message: str,
        intent_type: str,
        flow_mode: str | None,
    ) -> list[tuple[str, dict[str, Any]]]:
        actions: list[tuple[str, dict[str, Any]]] = []
        context_defaults = self._extract_context_defaults(message)
        selected_request_ids = self._extract_selected_request_ids(message)
        keywords = extract_keywords(message)
        primary_keyword = keywords[0] if keywords else ""
        possible_codes = self._dedupe(re.findall(r"[A-Za-z0-9][A-Za-z0-9._/-]{2,}", message or ""))
        primary_code = possible_codes[0] if possible_codes else ""

        asks_price = self._has_any_keyword(message, ["价格", "趋势", "均价", "最低价", "最高价", "报价", "比价"])
        asks_supplier = self._has_any_keyword(message, ["供应商", "供货", "厂家", "厂商"])
        asks_purchase_order = self._has_any_keyword(message, ["采购订单", "订单", "下单"])
        asks_request = self._has_any_keyword(message, ["采购申请", "申请单", "需求池", "请购"])
        asks_material = self._has_any_keyword(message, ["物料", "材料", "型号", "规格", "编码", "是什么"])

        asks_inquiry = self._has_any_keyword(message, ["询价", "询价单", "发起询价", "生成询价", "比价"])
        asks_draft_inquiry = self._has_any_keyword(
            message,
            ["草稿", "询价草稿", "报价草稿", "报价单", "草稿报价单", "生成草稿报价单", "生成草稿"],
        )
        asks_publish = self._has_any_keyword(message, ["发布询价", "发送询价单", "推送供应商", "发询价"])
        asks_award = self._has_any_keyword(message, ["确认中标", "中标建议", "定标"])
        asks_contract = self._has_any_keyword(message, ["生成合同", "合同草稿"])
        asks_manual_compare = self._has_any_keyword(message, ["手动比价", "报价分析", "比价分析"])
        asks_manual_quote_entry = self._has_any_keyword(
            message,
            ["录入报价", "手动报价", "录入供应商报价", "填入报价", "填写报价", "手动比价任务", "创建手动比价"],
        )
        if intent_type == "workflow_action" and flow_mode == "auto_inquiry" and (asks_inquiry or asks_draft_inquiry) and selected_request_ids:
            actions.append((
                "create_inquiry_from_selected_requests",
                {
                    "request_ids": selected_request_ids,
                },
            ))

        # 手动比价模式：用户要发起询价/生成询价单/处理勾选物料/录入报价/分配份额/生成合同，
        # 且当前没有 inquiry_id（即还没有手动比价任务），优先创建手动比价任务（save_manual_quotes）
        if (
            intent_type == "workflow_action"
            and flow_mode == "manual_compare"
            and selected_request_ids
            and not context_defaults.get("inquiry_id")
            and (
                asks_inquiry
                or asks_draft_inquiry
                or asks_manual_quote_entry
                or asks_manual_compare
                or asks_award
                or asks_contract
            )
        ):
            actions.append((
                "save_manual_quotes",
                {
                    "request_ids": selected_request_ids,
                },
            ))

        if primary_code:
            actions.append((
                "search_material",
                {
                    "keyword": primary_code,
                    "limit": 5,
                },
            ))

            if asks_price or asks_supplier or asks_material:
                actions.append((
                    "get_material_price_history",
                    {
                        "material_code": primary_code,
                        "limit": 8,
                    },
                ))

            if asks_purchase_order:
                actions.append((
                    "search_purchase_orders",
                    {
                        "material_code": primary_code,
                        "limit": 10,
                    },
                ))

            if asks_request:
                actions.append((
                    "search_purchase_requests",
                    {
                        "material_code": primary_code,
                        "limit": 10,
                    },
                ))

        if asks_price:
            if context_defaults["material_code"] or context_defaults["material_name"]:
                actions.append((
                    "get_material_price_history",
                    {
                        "material_code": context_defaults["material_code"] or None,
                        "material_name": context_defaults["material_name"] or None,
                        "limit": 8,
                    },
                ))
            elif primary_keyword:
                actions.append((
                    "get_material_price_history",
                    {
                        "material_name": primary_keyword,
                        "limit": 8,
                    },
                ))
                actions.append(("search_material", {"keyword": primary_keyword, "limit": 5}))

        if asks_supplier and (context_defaults["supplier_code"] or context_defaults["supplier_name"]):
            actions.append((
                "get_supplier_purchase_profile",
                {
                    "supplier_code": context_defaults["supplier_code"] or None,
                    "supplier_name": context_defaults["supplier_name"] or None,
                    "limit": 8,
                },
            ))

        if asks_purchase_order:
            actions.append((
                "search_purchase_orders",
                {
                    "material_code": context_defaults["material_code"] or None,
                    "supplier_code": context_defaults["supplier_code"] or None,
                    "keyword": primary_keyword or None,
                    "limit": 10,
                },
            ))

        if asks_request:
            actions.append((
                "search_purchase_requests",
                {
                    "material_code": context_defaults["material_code"] or None,
                    "material_name": context_defaults["material_name"] or None,
                    "keyword": primary_keyword or None,
                    "limit": 10,
                },
            ))

        if intent_type == "workflow_action" and asks_publish and context_defaults.get("inquiry_id"):
            actions.append((
                "publish_inquiry_task",
                {
                    "inquiry_id": int(context_defaults["inquiry_id"]),
                },
            ))

        if intent_type == "workflow_action" and (asks_award or (flow_mode == "manual_compare" and asks_manual_compare)):
            analyze_args: dict[str, Any] = {"limit": 5}
            if context_defaults.get("inquiry_id"):
                analyze_args["inquiry_id"] = int(context_defaults["inquiry_id"])
            elif selected_request_ids:
                analyze_args["request_ids"] = selected_request_ids
            actions.append((
                "analyze_quotation_compare",
                analyze_args,
            ))

        if intent_type == "workflow_action" and asks_contract and context_defaults.get("inquiry_id") and context_defaults.get("supplier_id"):
            actions.append((
                "create_contract_draft_from_award",
                {
                    "inquiry_id": int(context_defaults["inquiry_id"]),
                    "supplier_id": int(context_defaults["supplier_id"]),
                },
            ))

        actions = [
            (tool_name, args)
            for tool_name, args in actions
            if self._is_tool_allowed(tool_name, intent_type, flow_mode)
        ]
        return actions[:3]

    async def _run_query_tools(
        self,
        llm: Any,
        message: str,
        memory_text: str,
        recalled_memory_text: str,
        context: dict[str, Any],
        intent_type: str,
        flow_mode: str | None,
    ) -> list[AgentToolResult]:
        results: list[AgentToolResult] = []
        seen_signatures = set()

        for tool_name, raw_args in self._build_seed_actions(message, intent_type, flow_mode):
            if tool_name not in self.tools:
                continue
            args = self._normalize_tool_args(tool_name, raw_args, message, results)
            signature = self._tool_signature(tool_name, args)
            if signature in seen_signatures:
                continue
            seen_signatures.add(signature)
            results.append(self._call_tool(tool_name, args))

        for _ in range(self.MAX_TOOL_PLANNING_ROUNDS):
            actions = await self._plan_tool_actions(
                llm=llm,
                message=message,
                memory_text=memory_text,
                recalled_memory_text=recalled_memory_text,
                tool_results=results,
            )
            if not actions:
                break

            executed_any = False
            for action in actions[:self.MAX_TOOL_ACTIONS_PER_ROUND]:
                tool_name = str(action.get("tool") or "").strip()
                raw_args = action.get("args") or {}
                if tool_name not in self.tools or not isinstance(raw_args, dict):
                    continue
                if not self._is_tool_allowed(tool_name, intent_type, flow_mode):
                    continue
                args = self._normalize_tool_args(tool_name, raw_args, message, results)
                signature = self._tool_signature(tool_name, args)
                if signature in seen_signatures:
                    continue
                seen_signatures.add(signature)
                results.append(self._call_tool(tool_name, args))
                executed_any = True

            if not executed_any:
                break

        return results

    def _call_tool(self, name: str, args: dict[str, Any]) -> AgentToolResult:
        tool = self.tools[name]
        data = tool.invoke(args)
        summary = self._summarize_tool_result(name, data)
        return AgentToolResult(name=name, args=args, summary=summary, data=data)

    def get_memory_overview(self, session_id: str | None = None) -> dict[str, Any]:
        short_term_count = len(load_messages(self.user.id, session_id)) if session_id else 0
        long_term_memories = list_long_term_memories(self.user.id, limit=20)
        return {
            "session_id": session_id,
            "short_term_count": short_term_count,
            "long_term_count": len(long_term_memories),
            "long_term_memories": long_term_memories,
        }

    def _collect_material_codes(self, results: list[AgentToolResult]) -> list[str]:
        codes = []
        for result in results:
            if result.name not in {"search_material", "get_material_price_history"}:
                continue
            for item in (result.data or {}).get("items", []):
                code = str(item.get("code") or item.get("material_code") or "").strip()
                if code:
                    codes.append(code)
        return self._dedupe(codes)

    def _collect_supplier_codes(self, results: list[AgentToolResult]) -> list[str]:
        codes = []
        for result in results:
            if result.name == "search_suppliers":
                for item in (result.data or {}).get("items", []):
                    code = str(item.get("code") or "").strip()
                    if code:
                        codes.append(code)
            if result.name == "get_supplier_purchase_profile":
                supplier = (result.data or {}).get("supplier") or {}
                code = str(supplier.get("code") or "").strip()
                if code:
                    codes.append(code)
        return self._dedupe(codes)

    async def _plan_tool_actions(
        self,
        llm: Any,
        message: str,
        memory_text: str,
        recalled_memory_text: str,
        tool_results: list[AgentToolResult],
    ) -> list[dict[str, Any]]:
        prompt_messages = TOOL_PLANNER_PROMPT.format_messages(
            user_message=message,
            memory_text=memory_text or "无",
            recalled_memory_text=recalled_memory_text or "无",
            tool_catalog_text=self._build_tool_catalog_text(),
            tool_text=self._format_tool_results(tool_results) or "无工具结果",
        )
        llm_messages = [
            ChatMessage(role=self._to_chat_role(item.type), content=str(item.content))
            for item in prompt_messages
        ]
        response = await llm.chat_completion(llm_messages, temperature=0)
        return self._parse_tool_actions(response.content)

    @staticmethod
    def _dedupe(items: list[str]) -> list[str]:
        result = []
        seen = set()
        for item in items:
            value = str(item or "").strip()
            if value and value not in seen:
                seen.add(value)
                result.append(value)
        return result

    @staticmethod
    def _summarize_tool_result(name: str, data: dict[str, Any]) -> str:
        count = data.get("count", 0)
        if name == "search_purchase_orders":
            return f"查询到 {count} 条采购订单明细。"
        if name == "search_purchase_requests":
            return f"查询到 {count} 条采购申请明细。"
        if name == "search_material":
            return f"查询到 {count} 条物料候选。"
        if name == "search_suppliers":
            return f"查询到 {count} 条供应商候选。"
        if name == "get_material_price_history":
            trend_count = len(data.get("monthly_trend") or [])
            return f"查询到 {count} 条物料价格历史汇总，{trend_count} 条月度趋势。"
        if name == "get_supplier_purchase_profile":
            return f"查询到供应商历史供货物料 {count} 条。"
        if name == "save_manual_quotes":
            preview = data.get("preview") or {}
            return f"已生成手动比价任务待确认：{preview.get('title') or ''}，物料项 {preview.get('material_item_count') or 0} 项。"
        return f"工具 {name} 执行完成。"

    @staticmethod
    def _format_tool_results(results: list[AgentToolResult]) -> str:
        payload = [
            {
                "tool": item.name,
                "args": item.args,
                "summary": item.summary,
                "data": item.data,
            }
            for item in results
        ]
        return json.dumps(payload, ensure_ascii=False, default=str)[:12000]

    def _build_tool_catalog_text(self) -> str:
        payload = []
        for tool in self.tools.values():
            schema = {}
            if getattr(tool, "args_schema", None):
                try:
                    schema = tool.args_schema.model_json_schema()
                except Exception:
                    schema = {}
            payload.append({
                "name": tool.name,
                "description": tool.description,
                "args_schema": schema,
            })
        return json.dumps(payload, ensure_ascii=False, default=str)

    def _normalize_tool_args(
        self,
        tool_name: str,
        raw_args: dict[str, Any],
        message: str,
        results: list[AgentToolResult],
    ) -> dict[str, Any]:
        args = {key: value for key, value in raw_args.items() if value not in (None, "", [])}
        keywords = extract_keywords(message)
        material_codes = self._collect_material_codes(results)
        supplier_codes = self._collect_supplier_codes(results)
        context_defaults = self._extract_context_defaults(message)

        if context_defaults["material_code"] and context_defaults["material_code"] not in material_codes:
            material_codes = [context_defaults["material_code"], *material_codes]
        if context_defaults["supplier_code"] and context_defaults["supplier_code"] not in supplier_codes:
            supplier_codes = [context_defaults["supplier_code"], *supplier_codes]

        if tool_name == "search_material":
            args["keyword"] = str(
                args.get("keyword")
                or context_defaults["material_code"]
                or context_defaults["material_name"]
                or (keywords[0] if keywords else message[:40])
            ).strip()
            args["limit"] = int(args.get("limit") or 5)
        elif tool_name == "search_suppliers":
            args["keyword"] = str(
                args.get("keyword")
                or context_defaults["supplier_code"]
                or context_defaults["supplier_name"]
                or (keywords[0] if keywords else message[:40])
            ).strip()
            args["limit"] = int(args.get("limit") or 8)
        elif tool_name == "search_purchase_requests":
            if not args.get("keyword") and not args.get("material_code") and not args.get("material_name"):
                args["keyword"] = (
                    context_defaults["material_code"]
                    or context_defaults["material_name"]
                    or (keywords[0] if keywords else message[:40])
                )
            if not args.get("material_code") and material_codes:
                args["material_code"] = material_codes[0]
            args["limit"] = int(args.get("limit") or 10)
        elif tool_name == "search_purchase_orders":
            if not args.get("keyword") and not args.get("material_code") and not args.get("supplier_code"):
                args["keyword"] = (
                    context_defaults["material_code"]
                    or context_defaults["material_name"]
                    or context_defaults["supplier_code"]
                    or context_defaults["supplier_name"]
                    or (keywords[0] if keywords else message[:40])
                )
            if not args.get("material_code") and material_codes:
                args["material_code"] = material_codes[0]
            if not args.get("supplier_code") and supplier_codes:
                args["supplier_code"] = supplier_codes[0]
            args["limit"] = int(args.get("limit") or 10)
        elif tool_name == "get_material_price_history":
            if not args.get("material_code") and material_codes:
                args["material_code"] = material_codes[0]
            if not args.get("material_code") and not args.get("material_name"):
                args["material_name"] = context_defaults["material_name"] or (keywords[0] if keywords else message[:40])
            args["limit"] = int(args.get("limit") or 8)
        elif tool_name == "get_supplier_purchase_profile":
            if not args.get("supplier_code") and supplier_codes:
                args["supplier_code"] = supplier_codes[0]
            if not args.get("supplier_code") and not args.get("supplier_name"):
                args["supplier_name"] = context_defaults["supplier_name"] or (keywords[0] if keywords else message[:40])
            args["limit"] = int(args.get("limit") or 8)
        elif tool_name == "create_inquiry_from_selected_requests":
            selected_request_ids = self._extract_selected_request_ids(message)
            selected_requests = self._extract_selected_requests(message)
            if not args.get("request_ids") and selected_request_ids:
                args["request_ids"] = selected_request_ids
            if not args.get("selected_requests") and selected_requests:
                args["selected_requests"] = selected_requests
            if not args.get("title") and selected_requests:
                first_row = selected_requests[0]
                material_name = str(first_row.get("material_name") or "").strip() or "勾选物料"
                args["title"] = f"AI询价任务-{material_name}-{datetime.now().strftime('%m%d%H%M')}"
        elif tool_name == "save_manual_quotes":
            selected_request_ids = self._extract_selected_request_ids(message)
            selected_requests = self._extract_selected_requests(message)
            if not args.get("request_ids") and selected_request_ids:
                args["request_ids"] = selected_request_ids
            if not args.get("selected_requests") and selected_requests:
                args["selected_requests"] = selected_requests
            if not args.get("title") and selected_requests:
                first_row = selected_requests[0]
                material_name = str(first_row.get("material_name") or "").strip() or "勾选物料"
                args["title"] = f"手动比价任务-{material_name}-{datetime.now().strftime('%m%d%H%M')}"
        elif tool_name in {"recommend_suppliers_for_inquiry", "create_inquiry_draft", "generate_inquiry_message"}:
            current_material_code = str(args.get("material_code") or "").strip()
            if context_defaults["material_code"] and (not current_material_code or current_material_code not in material_codes):
                args["material_code"] = context_defaults["material_code"]
            if not args.get("material_code") and material_codes:
                args["material_code"] = material_codes[0]
            if not args.get("material_code"):
                args["material_code"] = context_defaults["material_code"] or (keywords[0] if keywords else "")
            context_qty_match = re.search(r"CURRENT_QTY:\s*(.*)", message or "")
            context_qty = context_qty_match.group(1).strip() if context_qty_match else ""
            args["qty"] = float(args.get("qty") or context_qty or 1)
            if tool_name != "recommend_suppliers_for_inquiry":
                context_delivery_date_match = re.search(r"CURRENT_DELIVERY_DATE:\s*(.*)", message or "")
                context_delivery_date = context_delivery_date_match.group(1).strip() if context_delivery_date_match else ""
                args["delivery_date"] = str(
                    args.get("delivery_date")
                    or context_delivery_date
                    or datetime.now().strftime("%Y-%m-%d")
                )
            args["limit"] = int(args.get("limit") or 3) if "limit" in args or tool_name != "generate_inquiry_message" else 3
        elif tool_name == "analyze_quotation_compare":
            if not args.get("inquiry_id") and context_defaults.get("inquiry_id"):
                args["inquiry_id"] = int(context_defaults["inquiry_id"])
            if not args.get("request_ids"):
                selected_request_ids = self._extract_selected_request_ids(message)
                if selected_request_ids:
                    args["request_ids"] = selected_request_ids
            if not args.get("selected_requests"):
                selected_requests = self._extract_selected_requests(message)
                if selected_requests:
                    args["selected_requests"] = selected_requests
            args["limit"] = int(args.get("limit") or 5)
        elif tool_name == "publish_inquiry_task":
            if not args.get("inquiry_id") and context_defaults.get("inquiry_id"):
                args["inquiry_id"] = int(context_defaults["inquiry_id"])
        elif tool_name == "create_contract_draft_from_award":
            if not args.get("inquiry_id") and context_defaults.get("inquiry_id"):
                args["inquiry_id"] = int(context_defaults["inquiry_id"])
            if not args.get("supplier_id") and context_defaults.get("supplier_id"):
                args["supplier_id"] = int(context_defaults["supplier_id"])
        elif tool_name == "check_contract_risks":
            if not args.get("contract_id") and context_defaults.get("contract_id"):
                args["contract_id"] = int(context_defaults["contract_id"])
        return args

    @staticmethod
    def _tool_signature(tool_name: str, args: dict[str, Any]) -> str:
        return f"{tool_name}:{json.dumps(args, ensure_ascii=False, sort_keys=True, default=str)}"

    @staticmethod
    def _parse_tool_actions(content: str) -> list[dict[str, Any]]:
        text = str(content or "").strip()
        if not text:
            return []
        try:
            payload = json.loads(text)
            actions = payload.get("actions", []) if isinstance(payload, dict) else []
            return actions if isinstance(actions, list) else []
        except Exception:
            pass

        match = re.search(r"\{[\s\S]*\}", text)
        if not match:
            return []
        try:
            payload = json.loads(match.group(0))
            actions = payload.get("actions", []) if isinstance(payload, dict) else []
            return actions if isinstance(actions, list) else []
        except Exception:
            return []

    @staticmethod
    def _format_recalled_memories(memories: list[Any]) -> str:
        lines = []
        for item in memories:
            if not item.summary:
                continue
            keywords = "、".join(item.keywords[:5]) if item.keywords else "无关键词"
            lines.append(f"- {item.summary}（关键词：{keywords}）")
        return "\n".join(lines)

    def _save_long_term_memory(
        self,
        user_id: int | str,
        session_id: str,
        user_message: str,
        answer: str,
        tool_results: list[AgentToolResult],
    ) -> None:
        if not tool_results:
            return
        message_keywords = extract_keywords(user_message)
        if not message_keywords:
            return
        summary = self._build_memory_summary(user_message, answer)
        save_long_term_memory(
            user_id=user_id,
            session_id=session_id,
            summary=summary,
            keywords=message_keywords,
        )

    @staticmethod
    def _build_memory_summary(user_message: str, answer: str) -> str:
        question = str(user_message or "").strip()
        conclusion = str(answer or "").strip().replace("\n", " ")
        if len(conclusion) > 220:
            conclusion = conclusion[:220] + "..."
        return f"用户关注：{question}；上次结论：{conclusion}"

    @staticmethod
    def _to_chat_role(langchain_type: str) -> str:
        if langchain_type == "system":
            return "system"
        if langchain_type == "ai":
            return "assistant"
        return "user"
