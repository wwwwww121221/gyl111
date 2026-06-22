from __future__ import annotations

import re
from dataclasses import dataclass, field

from procurement_agent.tools import extract_possible_codes


INTENT_MATERIAL = "material"
INTENT_PURCHASE_REQUEST = "purchase_request"
INTENT_PRICE_HISTORY = "price_history"
INTENT_SUPPLIER = "supplier"
INTENT_PURCHASE_ORDER = "purchase_order"


@dataclass
class QueryPlan:
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
    intents: list[str] = []

    if _contains_any(text, ["采购申请", "申请单", "需求池", "请购", "需求单"]):
        intents.append(INTENT_PURCHASE_REQUEST)

    if _contains_any(text, ["价格", "趋势", "均价", "最低价", "最高价", "报价", "比价", "历史价格"]):
        intents.append(INTENT_PRICE_HISTORY)

    if _contains_any(text, ["供应商", "厂家", "厂商", "供货", "合作方", "谁供", "哪家"]):
        intents.append(INTENT_SUPPLIER)

    if _contains_any(text, ["采购订单", "订单", "下单", "订单记录", "采购记录"]):
        intents.append(INTENT_PURCHASE_ORDER)

    if _contains_any(text, ["物料", "材料", "规格", "型号", "编码", "物料编码", "主数据"]):
        intents.append(INTENT_MATERIAL)

    return _dedupe(intents)


def extract_keywords(text: str, codes: list[str] | None = None) -> list[str]:
    keywords = list(codes or [])
    cleaned = str(text or "")

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
    normalized = re.sub(r"[，。；：、,.?:;\n\t/()\[\]（）]+", " ", text)
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
    "请帮我",
    "查一下",
    "查一查",
    "查询一下",
    "查询",
    "看看",
    "分析一下",
    "分析",
    "最近一年",
    "最近半年",
    "最近",
    "最新",
    "有关",
    "相关",
    "情况",
    "信息",
    "数据",
    "记录",
    "明细",
    "清单",
    "列表",
    "采购申请",
    "申请单",
    "需求池",
    "请购",
    "采购订单",
    "订单",
    "历史价格",
    "价格趋势",
    "趋势",
    "均价",
    "最低价",
    "最高价",
    "报价",
    "比价",
    "价格",
    "供应商",
    "供货",
    "厂家",
    "厂商",
    "物料编码",
    "编码",
    "物料",
    "材料",
    "规格",
    "型号",
    "这个",
    "那个",
]


_EDGE_NOISE_WORDS = [
    "这个物料",
    "这个型号",
    "这个",
    "那个",
    "信息",
    "数据",
    "记录",
    "情况",
    "分析",
]
