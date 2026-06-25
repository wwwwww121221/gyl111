from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from statistics import mean
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from models import (
    AgentPendingAction,
    Contract,
    ContractTemplate,
    InquiryRequest,
    InquirySupplier,
    InquiryTask,
    InquiryTaskItem,
    Material,
    PurchaseOrderMonthlyStat,
    PurchaseOrderSummary,
    Quotation,
    Supplier,
    TaskStatus,
    User,
)
from routers.system import log_operation


def _require_procurement_roles(user: User) -> None:
    if user.role not in ["admin", "buyer", "buyer_manager"]:
        raise HTTPException(status_code=403, detail="Only procurement users can use write-capable agent tools")


def _format_date(value: Any) -> str:
    return value.strftime("%Y-%m-%d") if isinstance(value, datetime) else ""


def _resolve_material(db: Session, material_code: str) -> Material | None:
    normalized_code = str(material_code or "").strip()
    if not normalized_code:
        return None
    return db.query(Material).filter(func.trim(Material.code) == normalized_code).first()


def _build_supplier_recommendation_reason(candidate: dict[str, Any], peer_avg_price: float | None) -> str:
    reasons: list[str] = []
    if candidate["order_count"] > 0:
        reasons.append(f"历史供货 {candidate['order_count']} 次")
    if candidate["recent_transaction"]:
        reasons.append("最近 6 个月有交易")
    if candidate["avg_price"] is not None and peer_avg_price:
        if candidate["avg_price"] <= peer_avg_price:
            reasons.append("价格处于候选供应商较优区间")
    if candidate["rating_score"] >= 85:
        reasons.append("供应商评分较高")
    if candidate["delivery_stability"] >= 70:
        reasons.append("近期开单稳定")
    if not reasons:
        reasons.append("具备基础历史合作记录")
    return "，".join(reasons[:3])


def _build_supplier_risk_notes(candidate: dict[str, Any]) -> list[str]:
    notes: list[str] = []
    if not candidate["status_normal"]:
        notes.append("供应商状态异常，需人工复核")
    if candidate["bad_record"]:
        notes.append("供应商审核状态存在异常记录")
    if not candidate["recent_transaction"]:
        notes.append("最近 6 个月无成交记录")
    if candidate["delivery_stability"] < 50:
        notes.append("近期开单连续性偏弱")
    if candidate["rating_score"] <= 60:
        notes.append("供应商评分偏低")
    return notes


def _collect_supplier_candidates(
    db: Session,
    material_code: str,
    limit: int,
) -> tuple[list[dict[str, Any]], list[str]]:
    normalized_code = str(material_code or "").strip()
    if not normalized_code:
        raise HTTPException(status_code=400, detail="material_code is required")

    summary_rows = (
        db.query(PurchaseOrderSummary)
        .filter(func.trim(PurchaseOrderSummary.material_code) == normalized_code)
        .order_by(PurchaseOrderSummary.order_count.desc(), PurchaseOrderSummary.latest_date.desc())
        .all()
    )
    supplier_codes = [str(row.supplier_code or "").strip() for row in summary_rows if str(row.supplier_code or "").strip()]
    suppliers = db.query(Supplier).filter(Supplier.code.in_(supplier_codes)).all() if supplier_codes else []
    supplier_map = {str(item.code or "").strip(): item for item in suppliers}

    monthly_rows = (
        db.query(PurchaseOrderMonthlyStat)
        .filter(func.trim(PurchaseOrderMonthlyStat.material_code) == normalized_code)
        .order_by(PurchaseOrderMonthlyStat.stat_month.desc())
        .all()
    )
    monthly_by_supplier: dict[str, list[PurchaseOrderMonthlyStat]] = defaultdict(list)
    for row in monthly_rows:
        code = str(row.supplier_code or "").strip()
        if code:
            monthly_by_supplier[code].append(row)

    peer_avg_price = mean(
        [float(row.avg_tax_net_price) for row in summary_rows if row.avg_tax_net_price is not None]
    ) if any(row.avg_tax_net_price is not None for row in summary_rows) else None

    candidates: list[dict[str, Any]] = []
    now = datetime.now()
    for row in summary_rows:
        supplier_code = str(row.supplier_code or "").strip()
        if not supplier_code:
            continue
        supplier = supplier_map.get(supplier_code)
        latest_date = row.latest_date
        recent_transaction = bool(latest_date and latest_date >= now - timedelta(days=180))
        supplier_monthly = monthly_by_supplier.get(supplier_code, [])
        active_months = len([item for item in supplier_monthly[:6] if int(item.order_count or 0) > 0])
        delivery_stability = min(100, int(active_months / 6 * 100)) if supplier_monthly else (60 if recent_transaction else 20)
        status_normal = bool(supplier and supplier.status == "approved")
        bad_record = bool(supplier and str(supplier.profile_audit_status or "").lower() in {"rejected", "change_returned"})
        rating_score = float(supplier.rating_score or 0) if supplier else 0.0
        avg_price = float(row.avg_tax_net_price) if row.avg_tax_net_price is not None else None
        price_score = 0.0
        if avg_price is not None and peer_avg_price and peer_avg_price > 0:
            ratio = avg_price / peer_avg_price
            if ratio <= 0.9:
                price_score = 20
            elif ratio <= 1.0:
                price_score = 15
            elif ratio <= 1.1:
                price_score = 8
        total_score = (
            min(int(row.order_count or 0) * 4, 30)
            + price_score
            + (12 if recent_transaction else 0)
            + min(int(rating_score / 5), 20)
            + min(int(delivery_stability / 5), 20)
            + (8 if status_normal else -20)
            + (-15 if bad_record else 0)
        )
        candidate = {
            "supplier_id": supplier.id if supplier else None,
            "supplier_code": supplier_code,
            "supplier_name": row.supplier_name or (supplier.name if supplier else supplier_code),
            "order_count": int(row.order_count or 0),
            "avg_price": avg_price,
            "latest_price": float(row.latest_tax_net_price) if row.latest_tax_net_price is not None else None,
            "latest_date": _format_date(latest_date),
            "rating_score": round(rating_score, 2),
            "status": supplier.status if supplier else "",
            "status_normal": status_normal,
            "bad_record": bad_record,
            "delivery_stability": delivery_stability,
            "recent_transaction": recent_transaction,
            "score": round(total_score, 2),
        }
        candidate["recommend_reason"] = _build_supplier_recommendation_reason(candidate, peer_avg_price)
        candidate["risk_notes"] = _build_supplier_risk_notes(candidate)
        candidates.append(candidate)

    candidates.sort(
        key=lambda item: (
            item["status_normal"],
            not item["bad_record"],
            item["score"],
            item["order_count"],
        ),
        reverse=True,
    )

    global_risks = []
    if not candidates:
        global_risks.append("未找到该物料对应的历史供货供应商")
    elif all(not item["status_normal"] for item in candidates[:limit]):
        global_risks.append("候选供应商均未处于 approved 状态，需人工筛选")
    return candidates[:limit], global_risks


def recommend_suppliers_for_inquiry(
    db: Session,
    user: User,
    material_code: str,
    qty: float,
    delivery_date: str | None = None,
    limit: int = 3,
) -> dict[str, Any]:
    _require_procurement_roles(user)
    if qty is None or float(qty) <= 0:
        raise HTTPException(status_code=400, detail="qty must be greater than 0")

    material = _resolve_material(db, material_code)
    candidates, global_risks = _collect_supplier_candidates(db, material_code, max(1, min(int(limit or 3), 10)))
    price_values = [item["avg_price"] for item in candidates if item["avg_price"] is not None]
    price_reference = {
        "min_price": round(min(price_values), 2) if price_values else None,
        "max_price": round(max(price_values), 2) if price_values else None,
        "avg_price": round(mean(price_values), 2) if price_values else None,
    }

    log_operation(
        db,
        user.id,
        "AGENT_RECOMMEND_SUPPLIERS",
        f"AI 推荐询价供应商: {material_code}",
        module="采购智能体",
        target_type="询价建议",
        target_name=material_code,
        result="success",
        extra_data={"material_code": material_code, "qty": qty, "delivery_date": delivery_date, "limit": limit},
    )

    return {
        "material": {
            "code": material_code,
            "name": material.name if material else "",
            "specification": material.specification if material else "",
            "qty": float(qty),
            "delivery_date": delivery_date,
        },
        "recommended_suppliers": candidates,
        "price_reference": price_reference,
        "risk_notes": global_risks,
    }


def _normalize_selected_request_rows(selected_requests: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    normalized_rows: list[dict[str, Any]] = []
    for row in selected_requests or []:
        if not isinstance(row, dict):
            continue
        normalized_rows.append({
            "id": row.get("id"),
            "erp_request_id": str(row.get("erp_request_id") or "").strip(),
        })
    return normalized_rows


def _resolve_analysis_task(
    db: Session,
    inquiry_id: int | None,
    request_ids: list[str | int] | None,
    selected_requests: list[dict[str, Any]] | None,
) -> InquiryTask | None:
    if inquiry_id:
        return db.query(InquiryTask).filter(InquiryTask.id == inquiry_id).first()

    normalized_rows = _normalize_selected_request_rows(selected_requests)
    normalized_request_ids = [str(item).strip() for item in (request_ids or []) if str(item).strip()]
    numeric_ids = [int(item) for item in normalized_request_ids if item.isdigit()]
    erp_request_ids = [item for item in normalized_request_ids if not item.isdigit()]
    for row in normalized_rows:
        row_id = row.get("id")
        erp_request_id = row.get("erp_request_id")
        if row_id not in (None, ""):
            try:
                numeric_ids.append(int(row_id))
            except (TypeError, ValueError):
                pass
        if erp_request_id:
            erp_request_ids.append(erp_request_id)

    numeric_ids = sorted({item for item in numeric_ids if item > 0})
    erp_request_ids = sorted({item for item in erp_request_ids if item})
    if not numeric_ids and not erp_request_ids:
        return None

    query = (
        db.query(InquiryTask)
        .join(InquiryTaskItem, InquiryTaskItem.task_id == InquiryTask.id)
        .join(InquiryRequest, InquiryRequest.id == InquiryTaskItem.request_id)
    )
    filters = []
    if numeric_ids:
        filters.append(InquiryRequest.id.in_(numeric_ids))
    if erp_request_ids:
        filters.append(InquiryRequest.erp_request_id.in_(erp_request_ids))
    if len(filters) == 1:
        tasks = query.filter(filters[0]).all()
    else:
        tasks = query.filter(or_(*filters)).all()

    best_task = None
    best_sort_key: tuple[int, int, int] | None = None
    for task in tasks:
        quote_count = (
            db.query(Quotation)
            .join(InquirySupplier, InquirySupplier.id == Quotation.inquiry_supplier_id)
            .filter(InquirySupplier.task_id == task.id)
            .count()
        )
        match_count = len(task.items or [])
        sort_key = (
            1 if str(task.type or "").strip() == "manual" else 0,
            quote_count,
            match_count,
        )
        if best_sort_key is None or sort_key > best_sort_key:
            best_sort_key = sort_key
            best_task = task
    return best_task


def _load_latest_effective_quotes(db: Session, inquiry_supplier_id: int) -> list[Quotation]:
    quotes = (
        db.query(Quotation)
        .filter(Quotation.inquiry_supplier_id == inquiry_supplier_id)
        .order_by(Quotation.round.desc(), Quotation.created_at.desc())
        .all()
    )
    latest_by_item: dict[int, Quotation] = {}
    for quote in quotes:
        latest_by_item.setdefault(int(quote.item_id), quote)
    return list(latest_by_item.values())


def _build_manual_compare_allocations(analysis_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not analysis_rows:
        return []
    if len(analysis_rows) == 1:
        row = analysis_rows[0]
        return [{
            "link_id": row["link_id"],
            "supplier_id": row["supplier_id"],
            "supplier_name": row["supplier_name"],
            "allocated_ratio": 100.0,
            "quote_total_amount": row["quote_total_amount"],
        }]

    top_row = analysis_rows[0]
    second_row = analysis_rows[1]
    second_is_competitive = float(second_row["quote_total_amount"] or 0) <= float(top_row["quote_total_amount"] or 0) * 1.08
    if second_is_competitive:
        return [
            {
                "link_id": top_row["link_id"],
                "supplier_id": top_row["supplier_id"],
                "supplier_name": top_row["supplier_name"],
                "allocated_ratio": 70.0,
                "quote_total_amount": top_row["quote_total_amount"],
            },
            {
                "link_id": second_row["link_id"],
                "supplier_id": second_row["supplier_id"],
                "supplier_name": second_row["supplier_name"],
                "allocated_ratio": 30.0,
                "quote_total_amount": second_row["quote_total_amount"],
            },
        ]
    return [{
        "link_id": top_row["link_id"],
        "supplier_id": top_row["supplier_id"],
        "supplier_name": top_row["supplier_name"],
        "allocated_ratio": 100.0,
        "quote_total_amount": top_row["quote_total_amount"],
    }]


def _collect_task_counts(task: InquiryTask) -> tuple[int, int]:
    request_count = len(task.items or [])
    material_keys = set()
    for item in task.items or []:
        request = item.request
        if not request:
            continue
        material_keys.add((
            str(request.material_code or "").strip(),
            str(request.material_model or "").strip(),
            request.delivery_date.strftime("%Y-%m-%d") if request.delivery_date else "",
        ))
    return request_count, len(material_keys)


def analyze_quotation_compare(
    db: Session,
    user: User,
    inquiry_id: int | None = None,
    request_ids: list[str | int] | None = None,
    selected_requests: list[dict[str, Any]] | None = None,
    limit: int = 5,
) -> dict[str, Any]:
    _require_procurement_roles(user)
    task = _resolve_analysis_task(db, inquiry_id, request_ids, selected_requests)
    if not task:
        return {
            "status": "quote_required",
            "message": "当前未找到可用于手动比价的询价任务，请先录入供应商报价。",
            "comparisons": [],
        }

    supplier_links = db.query(InquirySupplier).filter(InquirySupplier.task_id == task.id).all()
    if not supplier_links:
        return {
            "inquiry": {"id": task.id, "title": task.title, "status": task.status},
            "status": "quote_required",
            "message": "当前还没有供应商报价，请先录入供应商报价。",
            "comparisons": [],
        }

    analysis_rows: list[dict[str, Any]] = []
    for link in supplier_links:
        effective_quotes = _load_latest_effective_quotes(db, link.id)
        if not effective_quotes:
            continue

        prices = [float(item.price or 0) for item in effective_quotes if item.price is not None]
        deliveries = [item.delivery_date for item in effective_quotes if item.delivery_date]
        quote_total = sum(float(item.qty or 0) * float(item.price or 0) for item in effective_quotes)
        supplier = link.supplier
        avg_price = round(mean(prices), 2) if prices else None
        score = float(supplier.rating_score or 0) if supplier else 0.0
        latest_delivery = max(deliveries).strftime("%Y-%m-%d") if deliveries else ""

        history_prices = (
            db.query(PurchaseOrderSummary)
            .filter(PurchaseOrderSummary.supplier_code == supplier.code)
            .limit(20)
            .all()
        ) if supplier and supplier.code else []
        history_avg = round(
            mean([float(row.avg_tax_net_price) for row in history_prices if row.avg_tax_net_price is not None]),
            2,
        ) if any(row.avg_tax_net_price is not None for row in history_prices) else None

        composite_score = (1000 - quote_total) + score * 5
        analysis_rows.append({
            "link_id": link.id,
            "supplier_id": supplier.id if supplier else None,
            "supplier_name": supplier.name if supplier else f"Supplier-{link.supplier_id}",
            "quote_count": len(effective_quotes),
            "avg_quote_price": avg_price,
            "quote_total_amount": round(quote_total, 2),
            "latest_delivery_date": latest_delivery,
            "supplier_rating_score": round(score, 2),
            "historical_avg_price": history_avg,
            "analysis_score": round(composite_score, 2),
            "recommendation_reason": "综合报价较优、供应商评分较高" if score >= 80 else "报价有优势，建议人工复核交期与条款",
        })

    if not analysis_rows:
        return {
            "inquiry": {"id": task.id, "title": task.title, "status": task.status},
            "status": "quote_required",
            "message": "当前还没有有效报价，请先录入供应商报价。",
            "comparisons": [],
        }

    analysis_rows.sort(key=lambda item: (item["quote_total_amount"], -item["supplier_rating_score"]))
    analysis_rows = analysis_rows[: max(1, min(int(limit or 5), 10))]
    recommended = analysis_rows[0] if analysis_rows else None
    allocation_rows = _build_manual_compare_allocations(analysis_rows)
    request_count, material_item_count = _collect_task_counts(task)
    quote_source = "手动录入" if str(task.type or "").strip() == "manual" else "已有报价"
    share_summary = "，".join(
        f"{row['supplier_name']} {int(row['allocated_ratio']) if float(row['allocated_ratio']).is_integer() else row['allocated_ratio']}%"
        for row in allocation_rows
    )

    pending_action = None
    if recommended and allocation_rows:
        pending_action = AgentPendingAction(
            action_type="confirm_award",
            payload={
                "task_id": task.id,
                "allocations": [
                    {"link_id": row["link_id"], "allocated_ratio": row["allocated_ratio"]}
                    for row in allocation_rows
                ],
                "source_mode": "manual_compare",
            },
            preview={
                "task_id": task.id,
                "task_title": task.title,
                "plan_mode": "manual_compare",
                "quote_source": quote_source,
                "request_count": request_count,
                "selected_line_count": request_count,
                "material_item_count": material_item_count,
                "recommended_supplier_count": len(allocation_rows),
                "share_summary": share_summary,
                "expected_operation": "确认后将保存份额分配结果，并生成合同草稿",
                "allocations": allocation_rows,
            },
            status="pending",
            created_by=user.id,
        )
        db.add(pending_action)
        db.commit()
        db.refresh(pending_action)

    log_operation(
        db,
        user.id,
        "AGENT_ANALYZE_QUOTATION",
        f"AI 分析询价比价: {task.title}",
        module="采购智能体",
        target_type="询价单",
        target_name=task.title,
        result="success",
        extra_data={"task_id": task.id, "pending_action_id": pending_action.id if pending_action else None},
    )

    return {
        "inquiry": {"id": task.id, "title": task.title, "status": task.status},
        "comparisons": analysis_rows,
        "pending_action_id": pending_action.id if pending_action else None,
        "action_type": "confirm_award" if pending_action else None,
        "preview": pending_action.preview if pending_action else None,
        "message": "手动比价方案已生成，确认后将保存份额分配结果，并生成合同草稿。" if pending_action else "当前还没有有效报价，请先录入供应商报价。",
        "award_suggestion": {
            "recommended_supplier": recommended,
            "recommended_suppliers": allocation_rows,
            "note": "仅提供手动比价与份额分配建议，不会自动确认中标。请人工确认。",
            "pending_action_id": pending_action.id if pending_action else None,
        },
    }


def check_contract_risks(
    db: Session,
    user: User,
    contract_id: int | None = None,
    supplier_name: str | None = None,
    total_amount: float | None = None,
    material_items: list[dict[str, Any]] | None = None,
    delivery_date: str | None = None,
    payment_terms: str | None = None,
    quality_terms: str | None = None,
    breach_terms: str | None = None,
) -> dict[str, Any]:
    _require_procurement_roles(user)
    risk_items: list[dict[str, str]] = []

    if contract_id is not None:
        contract = db.query(Contract).filter(Contract.id == contract_id).first()
        if not contract:
            raise HTTPException(status_code=404, detail="Contract not found")
        supplier_name = supplier_name or (
            contract.inquiry_supplier.supplier.name
            if contract.inquiry_supplier and contract.inquiry_supplier.supplier
            else None
        )
        total_amount = total_amount if total_amount is not None else contract.total_amount

    if not supplier_name:
        risk_items.append({"level": "high", "field": "supplier_name", "message": "缺少供应商名称"})
    elif not db.query(Supplier).filter(Supplier.name == supplier_name).first():
        risk_items.append({"level": "medium", "field": "supplier_name", "message": "供应商名称未匹配到系统档案"})

    if total_amount is None or float(total_amount) <= 0:
        risk_items.append({"level": "high", "field": "total_amount", "message": "合同金额缺失或异常"})

    if not material_items:
        risk_items.append({"level": "high", "field": "material_items", "message": "缺少物料明细"})

    if not delivery_date:
        risk_items.append({"level": "medium", "field": "delivery_date", "message": "缺少交期"})
    if not payment_terms:
        risk_items.append({"level": "medium", "field": "payment_terms", "message": "缺少付款方式"})
    if not quality_terms:
        risk_items.append({"level": "medium", "field": "quality_terms", "message": "缺少质量条款"})
    if not breach_terms:
        risk_items.append({"level": "medium", "field": "breach_terms", "message": "缺少违约责任条款"})

    active_template = db.query(ContractTemplate).filter(ContractTemplate.is_active == True).first()
    log_operation(
        db,
        user.id,
        "AGENT_CHECK_CONTRACT_RISKS",
        f"AI 检查合同风险: {supplier_name or contract_id or 'draft'}",
        module="采购智能体",
        target_type="合同草稿",
        target_name=supplier_name or str(contract_id or ""),
        result="success",
        extra_data={"contract_id": contract_id, "template_name": active_template.name if active_template else None},
    )

    return {
        "contract_id": contract_id,
        "supplier_name": supplier_name,
        "total_amount": total_amount,
        "risk_level": "high" if any(item["level"] == "high" for item in risk_items) else ("medium" if risk_items else "low"),
        "risk_items": risk_items,
        "summary": "AI 仅做结构化风控检查，最终条款仍需人工法务/采购确认。",
    }
