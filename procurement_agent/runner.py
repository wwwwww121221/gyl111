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
        history = load_messages(user_id, session_id)
        effective_message = self._merge_context_into_message(message, context or {})

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
        llm = get_procurement_agent_llm_service()
        tool_results = await self._run_query_tools(
            llm=llm,
            message=effective_message,
            memory_text=memory_text,
            recalled_memory_text=recalled_memory_text,
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

    def _build_seed_actions(self, message: str) -> list[tuple[str, dict[str, Any]]]:
        actions: list[tuple[str, dict[str, Any]]] = []
        context_defaults = self._extract_context_defaults(message)
        keywords = extract_keywords(message)
        primary_keyword = keywords[0] if keywords else ""
        possible_codes = self._dedupe(re.findall(r"[A-Za-z0-9][A-Za-z0-9._/-]{2,}", message or ""))
        primary_code = possible_codes[0] if possible_codes else ""

        asks_price = self._has_any_keyword(message, ["价格", "趋势", "均价", "最低价", "最高价", "报价", "比价"])
        asks_supplier = self._has_any_keyword(message, ["供应商", "供货", "厂家", "厂商"])
        asks_purchase_order = self._has_any_keyword(message, ["采购订单", "订单", "下单"])
        asks_request = self._has_any_keyword(message, ["采购申请", "申请单", "需求池", "请购"])
        asks_material = self._has_any_keyword(message, ["物料", "材料", "型号", "规格", "编码", "是什么"])

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

        return actions[:3]

    async def _run_query_tools(
        self,
        llm: Any,
        message: str,
        memory_text: str,
        recalled_memory_text: str,
    ) -> list[AgentToolResult]:
        results: list[AgentToolResult] = []
        seen_signatures = set()

        for tool_name, raw_args in self._build_seed_actions(message):
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
            args["limit"] = int(args.get("limit") or 5)
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
