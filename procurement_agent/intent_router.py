from __future__ import annotations

from dataclasses import dataclass, field

from procurement_agent.tools import extract_possible_codes


INTENT_MATERIAL = "material"
INTENT_PURCHASE_REQUEST = "purchase_request"
INTENT_PRICE_HISTORY = "price_history"
INTENT_SUPPLIER = "supplier"


@dataclass
class QueryPlan:
    """Deterministic read-only tool plan for one user question."""

    intents: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    codes: list[str] = field(default_factory=list)
    broad_search: bool = False


def build_query_plan(message: str) -> QueryPlan:
    text = str(message or "").strip()
    codes = extract_possible_codes(text)
    intents = detect_intents(text)
    keywords = extract_keywords(text, codes)
    broad_search = not intents

    if broad_search:
        intents = [INTENT_MATERIAL, INTENT_SUPPLIER]
    if not keywords and text:
        keywords = [text[:40]]

    return QueryPlan(
        intents=_dedupe(intents),
        keywords=keywords[:3],
        codes=codes,
        broad_search=broad_search,
    )


def detect_intents(text: str) -> list[str]:
    """Detect all procurement data intents implied by the message.

    A keyword such as "行程开关" is deliberately not tied to one table here.
    The surrounding intent words decide whether it should search master data,
    purchase requests, price history, supplier history, or several together.
    """

    intents: list[str] = []

    if _contains_any(text, ["采购申请", "申请单", "需求池", "请购", "采购需求", "需求单"]):
        intents.append(INTENT_PURCHASE_REQUEST)

    if _contains_any(text, [
        "历史价格",
        "采购价格",
        "价格",
        "历史",
        "趋势",
        "询价",
        "比价",
        "报价",
        "最低价",
        "最高价",
        "均价",
    ]):
        intents.append(INTENT_PRICE_HISTORY)

    if _contains_any(text, [
        "供应商",
        "厂商",
        "厂家",
        "供方",
        "报价方",
        "合作方",
        "供过",
        "供货",
        "谁供",
        "哪家",
    ]):
        intents.append(INTENT_SUPPLIER)

    if _contains_any(text, [
        "物料编码",
        "物料代码",
        "物料",
        "材料",
        "规格",
        "型号",
        "编码",
        "主数据",
    ]):
        intents.append(INTENT_MATERIAL)

    if INTENT_SUPPLIER in intents and _contains_any(text, ["供过", "供货", "谁供", "哪家"]):
        intents.append(INTENT_PRICE_HISTORY)

    if INTENT_PRICE_HISTORY in intents and _contains_any(text, ["采购申请", "申请单", "需求池", "请购", "采购需求"]):
        intents.append(INTENT_PURCHASE_REQUEST)

    return _dedupe(intents)


def extract_keywords(text: str, codes: list[str] | None = None) -> list[str]:
    keywords = list(codes or [])
    cleaned = text
    for word in sorted(_STOP_WORDS, key=len, reverse=True):
        cleaned = cleaned.replace(word, " ")
    for part in _split_keywords(cleaned):
        normalized = _normalize_keyword(part)
        if normalized and normalized not in keywords:
            keywords.append(normalized[:40])
    return _dedupe(keywords)


def _contains_any(text: str, words: list[str]) -> bool:
    return any(word in text for word in words)


def _split_keywords(text: str) -> list[str]:
    normalized = text
    for mark in ["，", "。", "、", ",", ".", "?", "？", "；", ";", "：", ":", "\n", "\t"]:
        normalized = normalized.replace(mark, " ")
    return [part.strip() for part in normalized.split(" ") if part.strip()]


def _normalize_keyword(text: str) -> str:
    value = str(text or "").strip()
    if not value:
        return ""

    changed = True
    while changed and value:
        changed = False
        for word in sorted(_EDGE_NOISE_WORDS, key=len, reverse=True):
            if value.startswith(word):
                value = value[len(word):].strip()
                changed = True
            if value.endswith(word):
                value = value[:-len(word)].strip()
                changed = True
    return value


def _dedupe(items: list[str]) -> list[str]:
    result = []
    seen = set()
    for item in items:
        value = str(item or "").strip()
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


_STOP_WORDS = [
    "帮我",
    "麻烦",
    "请帮忙",
    "查询一下",
    "查询",
    "查一下",
    "看看",
    "看一下",
    "分析一下",
    "分析",
    "最近",
    "最新",
    "一下",
    "有哪些",
    "哪些",
    "哪个",
    "哪家",
    "谁",
    "有没有",
    "是否",
    "相关的",
    "有关的",
    "对应的",
    "采购申请单",
    "采购申请单信息",
    "采购申请",
    "采购需求",
    "申请单",
    "需求池",
    "需求单",
    "请购",
    "历史采购价格",
    "历史价格",
    "采购价格",
    "价格趋势",
    "月度趋势",
    "最低价",
    "最高价",
    "均价",
    "价格",
    "历史",
    "趋势",
    "询价",
    "比价",
    "报价",
    "供应商",
    "厂商",
    "厂家",
    "供方",
    "报价方",
    "合作方",
    "供过",
    "供货",
    "谁供",
    "物料编码",
    "物料代码",
    "物料",
    "材料",
    "规格",
    "型号",
    "编码",
    "主数据",
    "清单",
    "列表",
    "明细",
    "情况",
    "记录",
    "数据",
    "信息",
    "最新信息",
    "最新的",
    "给我",
    "我想",
    "我要",
    "需要",
    "一个",
    "这个物料",
    "这个",
    "那个",
    "这款",
    "这个型号",
    "是什么",
    "什么",
    "是啥",
    "和",
    "及",
    "与",
    "的",
    "了",
    "吗",
]


_EDGE_NOISE_WORDS = [
    "这个物料",
    "这个型号",
    "这款",
    "这个",
    "那个",
    "最新信息",
    "最新的",
    "最新",
    "信息",
    "采购申请单信息",
    "采购申请信息",
    "采购申请单",
    "采购申请",
    "申请单",
    "是什么",
    "什么",
    "是啥",
    "一下",
    "的",
]
