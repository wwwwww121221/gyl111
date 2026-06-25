"""采购智能体 flow_mode 与流程分流测试。"""

from __future__ import annotations

import asyncio
import unittest
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from procurement_agent.runner import ProcurementAgentRunner
from procurement_agent.schemas import AgentChatResponse, AgentToolResult
from schemas import LLMResponse


def _build_mock_user() -> MagicMock:
    user = MagicMock()
    user.id = 1001
    user.role = "buyer"
    user.department = "采购部"
    return user


def _build_runner() -> ProcurementAgentRunner:
    db = MagicMock()
    user = _build_mock_user()
    with patch.object(ProcurementAgentRunner, "__init__", lambda self, db, user: None):
        runner = ProcurementAgentRunner.__new__(ProcurementAgentRunner)
    runner.db = db
    runner.user = user
    runner.tools = {}
    return runner


def _selected_requests_payload() -> list[dict[str, Any]]:
    return [
        {
            "id": 101,
            "bill_no": "PR-2026-0001",
            "material_code": "MAT-A001",
            "material_name": "测试物料A",
            "material_model": "型号A-1",
            "qty": 100,
            "delivery_date": "2026-07-15",
            "target_price": 12.5,
        },
        {
            "id": 102,
            "bill_no": "PR-2026-0002",
            "material_code": "MAT-B002",
            "material_name": "测试物料B",
            "material_model": "型号B-2",
            "qty": 50,
            "delivery_date": "2026-07-20",
            "target_price": 28.0,
        },
    ]


class FlowModeNormalizationTests(unittest.TestCase):
    def test_none_when_empty(self):
        self.assertIsNone(ProcurementAgentRunner._normalize_flow_mode(None))
        self.assertIsNone(ProcurementAgentRunner._normalize_flow_mode(""))
        self.assertIsNone(ProcurementAgentRunner._normalize_flow_mode("   "))

    def test_none_when_invalid(self):
        self.assertIsNone(ProcurementAgentRunner._normalize_flow_mode("query"))
        self.assertIsNone(ProcurementAgentRunner._normalize_flow_mode("auto"))
        self.assertIsNone(ProcurementAgentRunner._normalize_flow_mode("manual"))

    def test_auto_inquiry(self):
        self.assertEqual(ProcurementAgentRunner._normalize_flow_mode("auto_inquiry"), "auto_inquiry")

    def test_manual_compare(self):
        self.assertEqual(ProcurementAgentRunner._normalize_flow_mode("manual_compare"), "manual_compare")


class IntentClassificationTests(unittest.TestCase):
    def setUp(self):
        self.runner = _build_runner()

    def test_price_history_query_is_read_only(self):
        self.assertEqual(self.runner._classify_user_intent("查一下这个物料历史价格"), "read_only_query")

    def test_supplier_query_is_read_only(self):
        self.assertEqual(self.runner._classify_user_intent("这个物料有哪些供应商"), "read_only_query")

    def test_start_inquiry_is_workflow_action(self):
        self.assertEqual(self.runner._classify_user_intent("帮我发起询价"), "workflow_action")

    def test_allocate_share_is_workflow_action(self):
        self.assertEqual(self.runner._classify_user_intent("根据报价分配份额并生成合同"), "workflow_action")


class AllowedToolsTests(unittest.TestCase):
    def setUp(self):
        self.runner = _build_runner()

    def test_read_only_query_only_allows_read_tools(self):
        allowed = self.runner._get_allowed_tools("read_only_query", None)
        self.assertEqual(allowed, ProcurementAgentRunner.READ_ONLY_TOOL_NAMES)
        self.assertNotIn("create_inquiry_from_selected_requests", allowed)
        self.assertNotIn("publish_inquiry_task", allowed)

    def test_auto_inquiry_allows_publish(self):
        allowed = self.runner._get_allowed_tools("workflow_action", "auto_inquiry")
        self.assertIn("create_inquiry_from_selected_requests", allowed)
        self.assertIn("publish_inquiry_task", allowed)

    def test_manual_compare_forbids_publish(self):
        allowed = self.runner._get_allowed_tools("workflow_action", "manual_compare")
        self.assertIn("save_manual_quotes", allowed)
        self.assertIn("analyze_quotation_compare", allowed)
        self.assertNotIn("publish_inquiry_task", allowed)
        self.assertNotIn("create_inquiry_from_selected_requests", allowed)


class FlowModeRequiredResponseTests(unittest.TestCase):
    def test_response_mentions_available_modes(self):
        answer, tool_results = ProcurementAgentRunner._build_flow_mode_required_response()
        self.assertIn("自动询价", answer)
        self.assertIn("手动比价", answer)
        self.assertEqual(len(tool_results), 1)
        self.assertTrue(tool_results[0].data.get("flow_mode_required"))
        self.assertEqual(tool_results[0].data.get("available_modes"), ["auto_inquiry", "manual_compare"])


class ChatRoutingTests(unittest.TestCase):
    def setUp(self):
        self.runner = _build_runner()
        self.session_id = "test-session-001"

    def _patch_memory(self):
        return (
            patch("procurement_agent.runner.load_messages", return_value=[]),
            patch("procurement_agent.runner.append_message"),
            patch("procurement_agent.runner.summarize_recent_messages", return_value=""),
            patch("procurement_agent.runner.recall_long_term_memories", return_value=[]),
            patch("procurement_agent.runner.save_long_term_memory"),
            patch("procurement_agent.runner.list_long_term_memories", return_value=[]),
        )

    def _enter_patches(self, patches):
        return [p.start() for p in patches]

    def _exit_patches(self, patches):
        for p in patches:
            p.stop()

    def test_1_query_price_history_without_flow_mode(self):
        patches = self._enter_patches(self._patch_memory())
        try:
            with patch("procurement_agent.runner.detect_prompt_injection", return_value=None), \
                 patch("procurement_agent.runner.get_procurement_agent_llm_service") as mock_llm_factory, \
                 patch.object(self.runner, "_run_query_tools", new_callable=AsyncMock) as mock_tools:
                mock_llm = MagicMock()
                mock_llm.chat_completion = AsyncMock(
                    return_value=LLMResponse(content="该物料最近历史均价为 12.5 元。", raw_response={})
                )
                mock_llm_factory.return_value = mock_llm
                mock_tools.return_value = []

                response = asyncio.run(
                    self.runner.chat(
                        "查一下这个物料历史价格",
                        self.session_id,
                        {
                            "page": "采购申请列表",
                            "flow_mode": None,
                            "selected_request_ids": [],
                            "selected_requests": [],
                        },
                    )
                )

                self.assertIsInstance(response, AgentChatResponse)
                self.assertIn("12.5", response.answer)
                self.assertFalse(any(item.name == "flow_mode_required" for item in response.tool_results))
                mock_tools.assert_called_once()
        finally:
            self._exit_patches(patches)

    def test_2_query_price_history_under_auto_inquiry(self):
        patches = self._enter_patches(self._patch_memory())
        try:
            with patch("procurement_agent.runner.detect_prompt_injection", return_value=None), \
                 patch("procurement_agent.runner.get_procurement_agent_llm_service") as mock_llm_factory, \
                 patch.object(self.runner, "_run_query_tools", new_callable=AsyncMock) as mock_tools:
                mock_llm = MagicMock()
                mock_llm.chat_completion = AsyncMock(
                    return_value=LLMResponse(content="历史均价 12.5 元。", raw_response={})
                )
                mock_llm_factory.return_value = mock_llm
                mock_tools.return_value = []

                response = asyncio.run(
                    self.runner.chat(
                        "先查一下历史价格",
                        self.session_id,
                        {
                            "page": "采购申请列表",
                            "flow_mode": "auto_inquiry",
                            "selected_request_ids": ["101"],
                            "selected_requests": _selected_requests_payload(),
                        },
                    )
                )

                self.assertIsInstance(response, AgentChatResponse)
                self.assertIn("12.5", response.answer)
                self.assertFalse(any(item.name == "create_inquiry_from_selected_requests" for item in response.tool_results))
                mock_tools.assert_called_once()
                kwargs = mock_tools.call_args.kwargs
                self.assertEqual(kwargs.get("intent_type"), "read_only_query")
                self.assertEqual(kwargs.get("flow_mode"), "auto_inquiry")
        finally:
            self._exit_patches(patches)

    def test_3_start_inquiry_without_flow_mode_returns_choice_card(self):
        patches = self._enter_patches(self._patch_memory())
        try:
            with patch("procurement_agent.runner.detect_prompt_injection", return_value=None), \
                 patch("procurement_agent.runner.get_procurement_agent_llm_service") as mock_llm_factory:
                mock_llm_factory.return_value = MagicMock()

                response = asyncio.run(
                    self.runner.chat(
                        "帮我发起询价",
                        self.session_id,
                        {
                            "page": "采购申请列表",
                            "flow_mode": None,
                            "selected_request_ids": ["101"],
                            "selected_requests": _selected_requests_payload(),
                        },
                    )
                )

                self.assertIsInstance(response, AgentChatResponse)
                self.assertIn("自动询价", response.answer)
                self.assertIn("手动比价", response.answer)
                self.assertTrue(any(item.name == "flow_mode_required" for item in response.tool_results))
        finally:
            self._exit_patches(patches)

    def test_4_auto_inquiry_selected_requests_creates_confirmation_card(self):
        patches = self._enter_patches(self._patch_memory())
        try:
            with patch("procurement_agent.runner.detect_prompt_injection", return_value=None), \
                 patch("procurement_agent.runner.get_procurement_agent_llm_service") as mock_llm_factory, \
                 patch.object(self.runner, "_run_query_tools", new_callable=AsyncMock) as mock_tools:
                mock_llm = MagicMock()
                mock_llm.chat_completion = AsyncMock(
                    return_value=LLMResponse(
                        content="已生成自动询价方案，确认后将创建询价任务并发送给供应商。",
                        raw_response={},
                    )
                )
                mock_llm_factory.return_value = mock_llm
                mock_tools.return_value = [
                    AgentToolResult(
                        name="create_inquiry_from_selected_requests",
                        args={"request_ids": ["101", "102"]},
                        summary="自动询价方案已生成。",
                        data={
                            "pending_action_id": 9001,
                            "action_type": "create_inquiry_from_selected_requests",
                            "status": "pending_confirmation",
                            "preview": {"plan_mode": "auto_inquiry"},
                        },
                    )
                ]

                response = asyncio.run(
                    self.runner.chat(
                        "把勾选物料发起询价",
                        self.session_id,
                        {
                            "page": "采购申请列表",
                            "flow_mode": "auto_inquiry",
                            "selected_request_ids": ["101", "102"],
                            "selected_requests": _selected_requests_payload(),
                        },
                    )
                )

                self.assertIsInstance(response, AgentChatResponse)
                tool_names = [item.name for item in response.tool_results]
                self.assertIn("create_inquiry_from_selected_requests", tool_names)
                action = next(item for item in response.tool_results if item.name == "create_inquiry_from_selected_requests")
                self.assertEqual(action.data.get("status"), "pending_confirmation")
                self.assertEqual(action.data.get("preview", {}).get("plan_mode"), "auto_inquiry")
        finally:
            self._exit_patches(patches)

    def test_5_manual_compare_selected_requests_generates_compare_card(self):
        patches = self._enter_patches(self._patch_memory())
        try:
            with patch("procurement_agent.runner.detect_prompt_injection", return_value=None), \
                 patch("procurement_agent.runner.get_procurement_agent_llm_service") as mock_llm_factory, \
                 patch.object(self.runner, "_run_query_tools", new_callable=AsyncMock) as mock_tools:
                mock_llm = MagicMock()
                mock_llm.chat_completion = AsyncMock(
                    return_value=LLMResponse(
                        content="已生成比价与份额分配建议，确认后将生成合同草稿。",
                        raw_response={},
                    )
                )
                mock_llm_factory.return_value = mock_llm
                mock_tools.return_value = [
                    AgentToolResult(
                        name="analyze_quotation_compare",
                        args={"request_ids": ["101", "102"]},
                        summary="比价分析完成。",
                        data={
                            "pending_action_id": 9002,
                            "action_type": "confirm_award",
                            "status": "pending_confirmation",
                            "preview": {
                                "plan_mode": "manual_compare",
                                "quote_source": "手动录入",
                                "share_summary": "供应商A 70%，供应商B 30%",
                            },
                        },
                    )
                ]

                response = asyncio.run(
                    self.runner.chat(
                        "根据报价分配份额并生成合同",
                        self.session_id,
                        {
                            "page": "采购申请列表",
                            "flow_mode": "manual_compare",
                            "selected_request_ids": ["101", "102"],
                            "selected_requests": _selected_requests_payload(),
                        },
                    )
                )

                self.assertIsInstance(response, AgentChatResponse)
                tool_names = [item.name for item in response.tool_results]
                self.assertNotIn("publish_inquiry_task", tool_names)
                self.assertNotIn("create_inquiry_from_selected_requests", tool_names)
                self.assertIn("analyze_quotation_compare", tool_names)
        finally:
            self._exit_patches(patches)

    def test_manual_compare_blocks_publish_request(self):
        patches = self._enter_patches(self._patch_memory())
        try:
            with patch("procurement_agent.runner.detect_prompt_injection", return_value=None), \
                 patch("procurement_agent.runner.get_procurement_agent_llm_service") as mock_llm_factory:
                mock_llm_factory.return_value = MagicMock()

                response = asyncio.run(
                    self.runner.chat(
                        "帮我发布询价给供应商",
                        self.session_id,
                        {
                            "page": "采购申请列表",
                            "flow_mode": "manual_compare",
                            "selected_request_ids": ["101"],
                            "selected_requests": _selected_requests_payload(),
                        },
                    )
                )

                self.assertIsInstance(response, AgentChatResponse)
                self.assertIn("手动比价模式", response.answer)
                self.assertIn("不能给供应商发送询价单", response.answer)
                self.assertEqual(response.tool_results, [])
        finally:
            self._exit_patches(patches)

    def test_auto_inquiry_without_selection_prompts_select(self):
        patches = self._enter_patches(self._patch_memory())
        try:
            with patch("procurement_agent.runner.detect_prompt_injection", return_value=None), \
                 patch("procurement_agent.runner.get_procurement_agent_llm_service") as mock_llm_factory:
                mock_llm_factory.return_value = MagicMock()

                response = asyncio.run(
                    self.runner.chat(
                        "把勾选物料发起询价",
                        self.session_id,
                        {
                            "page": "采购申请列表",
                            "flow_mode": "auto_inquiry",
                            "selected_request_ids": [],
                            "selected_requests": [],
                        },
                    )
                )

                self.assertIsInstance(response, AgentChatResponse)
                self.assertIn("请先在采购申请列表中勾选", response.answer)
        finally:
            self._exit_patches(patches)


class PromptContentTests(unittest.TestCase):
    def test_agent_system_prompt_contains_flow_mode_rules(self):
        from procurement_agent.prompts import AGENT_SYSTEM_PROMPT

        self.assertIn("仅查询", AGENT_SYSTEM_PROMPT)
        self.assertIn("auto_inquiry", AGENT_SYSTEM_PROMPT)
        self.assertIn("manual_compare", AGENT_SYSTEM_PROMPT)
        self.assertIn("普通查询不需要选择流程模式", AGENT_SYSTEM_PROMPT)
        self.assertIn("业务动作", AGENT_SYSTEM_PROMPT)
        self.assertIn("AgentPendingAction", AGENT_SYSTEM_PROMPT)

    def test_agent_system_prompt_contains_auto_inquiry_rules(self):
        from procurement_agent.prompts import AGENT_SYSTEM_PROMPT

        self.assertIn("在供应商报价返回前，不能直接生成合同", AGENT_SYSTEM_PROMPT)
        self.assertIn("自动询价", AGENT_SYSTEM_PROMPT)

    def test_agent_system_prompt_contains_manual_compare_rules(self):
        from procurement_agent.prompts import AGENT_SYSTEM_PROMPT

        self.assertIn("手动比价模式下禁止调用 publish_inquiry_task", AGENT_SYSTEM_PROMPT)
        self.assertIn("不能给供应商发送询价单", AGENT_SYSTEM_PROMPT)
        self.assertIn("请先录入供应商报价", AGENT_SYSTEM_PROMPT)

    def test_tool_planner_prompt_contains_flow_mode_rules(self):
        from procurement_agent.prompts import TOOL_PLANNER_SYSTEM_PROMPT

        self.assertIn("flow_mode", TOOL_PLANNER_SYSTEM_PROMPT)
        self.assertIn("auto_inquiry", TOOL_PLANNER_SYSTEM_PROMPT)
        self.assertIn("manual_compare", TOOL_PLANNER_SYSTEM_PROMPT)
        self.assertIn("禁止调用 publish_inquiry_task", TOOL_PLANNER_SYSTEM_PROMPT)


if __name__ == "__main__":
    unittest.main(verbosity=2)
