from __future__ import annotations


_OVERRIDE_VERBS = ["忽略", "无视", "忘记", "覆盖", "绕过", "不用遵守", "不需要遵守"]
_OVERRIDE_TARGETS = ["指令", "规则", "提示词", "约束", "系统", "开发者", "身份"]
_ROLE_SWITCH_WORDS = ["你现在不是", "你现在扮演", "你现在作为", "假装你是", "切换角色", "切换身份"]
_SECRET_WORDS = ["系统提示词", "隐藏指令", "内部指令", "开发者消息", "密钥", "密码", "token", "环境变量", "数据库连接"]
_WRITE_OR_COMMAND_WORDS = [
    "删除数据库",
    "清空数据库",
    "修改数据库",
    "删除数据表",
    "运行命令",
    "执行命令",
    "执行脚本",
    "执行shell",
    "执行sql",
    "drop table",
    "truncate table",
]

_ENGLISH_RISK_PHRASES = [
    "ignore previous",
    "ignore all previous",
    "ignore above",
    "system prompt",
    "developer message",
    "reveal prompt",
    "reveal secret",
    "show me your prompt",
    "bypass rules",
]

_BUSINESS_KEYWORDS = [
    "采购",
    "供应商",
    "物料",
    "询价",
    "报价",
    "合同",
    "订单",
    "价格",
    "比价",
    "供应链",
    "交付",
    "库存",
    "质量",
]


def _contains_any(text: str, words: list[str]) -> bool:
    return any(word.lower() in text.lower() for word in words)


def detect_prompt_injection(text: str) -> str | None:
    """Return a reason when the user message tries to override agent boundaries."""
    normalized = str(text or "").strip()
    if not normalized:
        return None

    if _contains_any(normalized, _OVERRIDE_VERBS) and _contains_any(normalized, _OVERRIDE_TARGETS):
        return "检测到可能的提示词注入或越权引导。"
    if _contains_any(normalized, _ROLE_SWITCH_WORDS):
        return "检测到可能的角色切换或身份覆盖请求。"
    if _contains_any(normalized, _SECRET_WORDS):
        return "检测到可能的敏感信息请求。"
    if _contains_any(normalized, _WRITE_OR_COMMAND_WORDS):
        return "检测到可能的越权写入、删除或命令执行请求。"
    if _contains_any(normalized, _ENGLISH_RISK_PHRASES):
        return "检测到可能的提示词注入、越权操作或敏感信息请求。"
    return None


def is_procurement_related(text: str) -> bool:
    normalized = str(text or "")
    return any(keyword in normalized for keyword in _BUSINESS_KEYWORDS)


def build_guardrail_response(reason: str) -> str:
    return (
        f"{reason}\n\n"
        "我只能作为采购智能体，基于系统授权的只读工具回答采购、供应商、物料、价格、合同等相关问题。"
        "我不能泄露系统提示词、密钥或配置，也不能执行删除、修改数据库、运行命令等操作。\n\n"
        "你可以换成这样的问法：帮我查询某个物料的历史价格、分析某个供应商的合作情况，"
        "或根据已有数据给出询价建议。"
    )
