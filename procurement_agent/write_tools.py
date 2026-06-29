from __future__ import annotations

from datetime import datetime
from statistics import mean
from typing import Any

from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from models import (
    AgentPendingAction,
    Contract,
    ContractTemplate,
    InquiryRequest,
    InquiryStatus,
    InquirySupplier,
    InquiryTask,
    InquiryTaskItem,
    LinkStatus,
    Material,
    Quotation,
    Supplier,
    TaskStatus,
    User,
)
from procurement_agent.risk_checker import analyze_quotation_compare, recommend_suppliers_for_inquiry
from routers.inquiry import (
    _get_task_activated_status,
    _send_task_invitation_notifications_background,
    close_inquiry_task,
)
from routers.system import log_operation
from schemas import TaskCloseAllocation, TaskClosePayload


def _require_procurement_roles(user: User) -> None:
    if user.role not in ["admin", "buyer", "buyer_manager"]:
        raise HTTPException(status_code=403, detail="Only procurement users can use write-capable agent tools")


def _parse_delivery_date(raw_value: str | None) -> datetime | None:
    value = str(raw_value or "").strip()
    if not value:
        return None
    for pattern in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(value, pattern)
        except ValueError:
            continue
    raise HTTPException(status_code=400, detail="delivery_date must be in YYYY-MM-DD or YYYY-MM-DDTHH:mm:ss format")


def _resolve_material(db: Session, material_code: str) -> Material | None:
    normalized_code = str(material_code or "").strip()
    if not normalized_code:
        return None
    return db.query(Material).filter(Material.code == normalized_code).first()


def _collect_material_history(
    db: Session,
    normalized_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """收集勾选物料的历史采购信息，供手动比价卡片展示。

    对每个唯一 material_code 查询：
    - 价格历史汇总（按供应商维度：订单数、均价、最新价、最低/最高价）
    - 月度价格趋势
    - 最近采购订单明细

    查询失败不影响主流程，对应物料的历史字段为空。
    """
    seen_codes: set[str] = set()
    history_list: list[dict[str, Any]] = []
    # 延迟导入避免与 procurement_agent.tools 形成循环导入
    from procurement_agent.tools import get_material_price_history, search_purchase_orders

    for row in normalized_rows:
        material_code = str(row.get("material_code") or "").strip()
        if not material_code or material_code in seen_codes:
            continue
        seen_codes.add(material_code)

        entry: dict[str, Any] = {
            "material_code": material_code,
            "material_name": row.get("material_name"),
            "material_model": row.get("material_model"),
            "price_history": None,
            "monthly_trend": None,
            "recent_orders": None,
        }

        try:
            price_history = get_material_price_history(
                db,
                {"material_code": material_code, "limit": 8},
            )
            entry["price_history"] = price_history.get("items") or []
            entry["monthly_trend"] = price_history.get("monthly_trend") or []
        except Exception:
            pass

        try:
            orders = search_purchase_orders(
                db,
                {"material_code": material_code, "limit": 8},
            )
            entry["recent_orders"] = orders.get("items") or []
        except Exception:
            pass

        history_list.append(entry)
    return history_list


def _create_pending_action(
    db: Session,
    user: User,
    action_type: str,
    payload: dict[str, Any],
    preview: dict[str, Any],
) -> AgentPendingAction:
    pending_action = AgentPendingAction(
        action_type=action_type,
        payload=payload,
        preview=preview,
        status="pending",
        created_by=user.id,
    )
    db.add(pending_action)
    db.commit()
    db.refresh(pending_action)
    return pending_action


def _normalize_supplier_ids(raw_supplier_ids: list[Any] | None) -> list[int]:
    supplier_ids: list[int] = []
    seen_ids: set[int] = set()
    for raw_supplier_id in raw_supplier_ids or []:
        try:
            supplier_id = int(raw_supplier_id)
        except (TypeError, ValueError):
            continue
        if supplier_id <= 0 or supplier_id in seen_ids:
            continue
        seen_ids.add(supplier_id)
        supplier_ids.append(supplier_id)
    return supplier_ids


def _coerce_optional_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Invalid numeric value in payload overrides")


def _normalize_award_allocations(raw_allocations: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """规范化份额分配。

    份额为 0 的供应商会被跳过（不参与分配），允许用户保留未中标的供应商行。
    最终非零份额合计必须等于 100%。
    """
    normalized: list[dict[str, Any]] = []
    seen_link_ids: set[int] = set()
    ratio_total = 0.0
    for row in raw_allocations or []:
        if not isinstance(row, dict):
            continue
        try:
            link_id = int(row.get("link_id") or 0)
        except (TypeError, ValueError):
            continue
        if link_id <= 0 or link_id in seen_link_ids:
            continue
        ratio = _coerce_optional_float(row.get("allocated_ratio"))
        if ratio is None:
            raise HTTPException(status_code=400, detail="allocated_ratio is required for manual compare allocations")
        seen_link_ids.add(link_id)
        # 份额为 0 的供应商跳过，不参与分配但允许出现在列表中
        if ratio <= 0:
            continue
        ratio_total += float(ratio)
        normalized.append({
            "link_id": link_id,
            "allocated_ratio": float(ratio),
        })
    if not normalized:
        raise HTTPException(status_code=400, detail="allocations is required")
    if abs(ratio_total - 100.0) > 1e-6:
        raise HTTPException(status_code=400, detail="份额比例合计必须等于 100%")
    return normalized


def _normalize_manual_quote_entries(raw_entries: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    normalized_entries: list[dict[str, Any]] = []
    for row in raw_entries or []:
        if not isinstance(row, dict):
            continue

        material_code = str(row.get("material_code") or "").strip()
        request_id = row.get("request_id")
        erp_request_id = str(row.get("erp_request_id") or "").strip()
        suppliers_payload = row.get("suppliers") or []
        if not material_code and request_id in (None, "") and not erp_request_id:
            continue

        normalized_suppliers: list[dict[str, Any]] = []
        for supplier_row in suppliers_payload:
            if not isinstance(supplier_row, dict):
                continue
            supplier_name = str(supplier_row.get("supplier_name") or "").strip()
            supplier_code = str(supplier_row.get("supplier_code") or "").strip()
            supplier_id = supplier_row.get("supplier_id")
            price = _coerce_optional_float(supplier_row.get("price"))
            qty = _coerce_optional_float(supplier_row.get("qty"))
            if price is None or price <= 0 or qty is None or qty <= 0:
                continue
            normalized_suppliers.append({
                "supplier_id": int(supplier_id) if supplier_id not in (None, "") else None,
                "supplier_code": supplier_code,
                "supplier_name": supplier_name or supplier_code or "未命名供应商",
                "price": float(price),
                "qty": float(qty),
                "delivery_date": str(supplier_row.get("delivery_date") or "").strip() or None,
            })

        if not normalized_suppliers:
            continue

        normalized_entries.append({
            "request_id": int(request_id) if request_id not in (None, "") else None,
            "erp_request_id": erp_request_id or None,
            "material_code": material_code,
            "suppliers": normalized_suppliers,
        })
    return normalized_entries


def _apply_payload_overrides(action_type: str, payload: dict[str, Any], payload_overrides: dict[str, Any] | None) -> dict[str, Any]:
    if not payload_overrides:
        return payload

    merged_payload = dict(payload)
    overrides = dict(payload_overrides)

    if action_type == "create_inquiry_draft":
        if "title" in overrides:
            merged_payload["title"] = str(overrides.get("title") or "").strip() or merged_payload.get("title")
        if "qty" in overrides:
            qty = _coerce_optional_float(overrides.get("qty"))
            if qty is None or qty <= 0:
                raise HTTPException(status_code=400, detail="qty must be greater than 0")
            merged_payload["qty"] = qty
        if "delivery_date" in overrides:
            merged_payload["delivery_date"] = str(overrides.get("delivery_date") or "").strip() or None
        if "target_price" in overrides:
            merged_payload["target_price"] = _coerce_optional_float(overrides.get("target_price"))
        if "supplier_ids" in overrides:
            merged_payload["supplier_ids"] = _normalize_supplier_ids(overrides.get("supplier_ids"))
        return merged_payload

    if action_type == "create_inquiry_from_selected_requests":
        if "title" in overrides:
            merged_payload["title"] = str(overrides.get("title") or "").strip() or merged_payload.get("title")
        if "deadline" in overrides:
            merged_payload["deadline"] = str(overrides.get("deadline") or "").strip() or None
        if "supplier_ids" in overrides:
            merged_payload["supplier_ids"] = _normalize_supplier_ids(overrides.get("supplier_ids"))
        if "target_price" in overrides:
            merged_payload["target_price"] = _coerce_optional_float(overrides.get("target_price"))
        if "execution_mode" in overrides:
            execution_mode = str(overrides.get("execution_mode") or "").strip()
            if execution_mode not in {"send_now", "draft_only"}:
                raise HTTPException(status_code=400, detail="execution_mode must be send_now or draft_only")
            merged_payload["execution_mode"] = execution_mode
        return merged_payload

    if action_type == "create_contract_draft":
        if "template_id" in overrides:
            merged_payload["template_id"] = int(overrides.get("template_id")) if overrides.get("template_id") not in (None, "") else None
        return merged_payload

    if action_type == "save_manual_quotes":
        if "title" in overrides:
            merged_payload["title"] = str(overrides.get("title") or "").strip() or merged_payload.get("title")
        if "manual_quote_entries" in overrides:
            merged_payload["manual_quote_entries"] = _normalize_manual_quote_entries(overrides.get("manual_quote_entries"))
        return merged_payload

    if action_type == "confirm_award":
        if "allocations" in overrides:
            merged_payload["allocations"] = _normalize_award_allocations(overrides.get("allocations"))
        return merged_payload

    return merged_payload


def _build_pending_action_preview(
    db: Session,
    action_type: str,
    payload: dict[str, Any],
    current_preview: dict[str, Any] | None = None,
) -> dict[str, Any]:
    preview = dict(current_preview or {})

    if action_type == "create_inquiry_draft":
        supplier_ids = _normalize_supplier_ids(payload.get("supplier_ids"))
        suppliers = (
            db.query(Supplier)
            .filter(Supplier.id.in_(supplier_ids))
            .all()
            if supplier_ids
            else []
        )
        supplier_name_map = {int(item.id): item.name for item in suppliers}
        preview.update({
            "title": str(payload.get("title") or preview.get("title") or "").strip(),
            "qty": payload.get("qty"),
            "delivery_date": payload.get("delivery_date"),
            "supplier_ids": supplier_ids,
            "supplier_names": [
                supplier_name_map.get(supplier_id)
                for supplier_id in supplier_ids
                if supplier_name_map.get(supplier_id)
            ],
            "target_price_suggestion": payload.get("target_price"),
        })
        return preview

    if action_type == "create_inquiry_from_selected_requests":
        supplier_ids = _normalize_supplier_ids(payload.get("supplier_ids"))
        recommended_suppliers = list(preview.get("recommended_suppliers") or [])
        recommended_by_id = {
            int(item.get("supplier_id")): dict(item)
            for item in recommended_suppliers
            if int(item.get("supplier_id") or 0) > 0
        }
        missing_supplier_ids = [supplier_id for supplier_id in supplier_ids if supplier_id not in recommended_by_id]
        if missing_supplier_ids:
            supplier_rows = db.query(Supplier).filter(Supplier.id.in_(missing_supplier_ids)).all()
            for supplier in supplier_rows:
                recommended_by_id[int(supplier.id)] = {
                    "supplier_id": int(supplier.id),
                    "supplier_name": supplier.name,
                    "supplier_code": supplier.code,
                    "avg_price": None,
                    "latest_price": None,
                    "recommend_reason": "手动添加到当前询价草稿",
                }
        preview.update({
            "title": str(payload.get("title") or preview.get("title") or "").strip(),
            "deadline": payload.get("deadline"),
            "supplier_ids": supplier_ids,
            "supplier_names": [
                item.get("supplier_name")
                for supplier_id in supplier_ids
                for item in [recommended_by_id.get(supplier_id)]
                if item and item.get("supplier_name")
            ],
            "recommended_supplier_count": len(supplier_ids),
            "recommended_suppliers": list(recommended_by_id.values()),
            "target_price_suggestion": payload.get("target_price"),
        })
        return preview

    if action_type == "save_manual_quotes":
        preview.update({
            "title": str(payload.get("title") or preview.get("title") or "").strip(),
        })
        return preview

    if action_type == "confirm_award":
        preview.update({
            "allocations": payload.get("allocations") or [],
        })
        return preview

    return preview


def update_pending_action_payload(
    db: Session,
    user: User,
    action_id: int,
    payload_overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    _require_procurement_roles(user)
    action = db.query(AgentPendingAction).filter(AgentPendingAction.id == action_id).first()
    if not action:
        raise HTTPException(status_code=404, detail="Pending action not found")
    if action.status != "pending":
        raise HTTPException(status_code=400, detail="Pending action is already processed")
    if user.role == "buyer" and action.created_by != user.id:
        raise HTTPException(status_code=403, detail="You can only update your own pending actions")

    payload = _apply_payload_overrides(action.action_type, dict(action.payload or {}), payload_overrides)
    preview = _build_pending_action_preview(db, action.action_type, payload, action.preview or {})

    action.payload = payload
    action.preview = preview
    db.add(action)
    db.commit()
    db.refresh(action)
    return {
        "id": action.id,
        "action_type": action.action_type,
        "status": action.status,
        "payload": action.payload,
        "preview": action.preview,
    }


def _normalize_selected_request_rows(selected_requests: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    normalized_rows: list[dict[str, Any]] = []
    for row in selected_requests or []:
        if not isinstance(row, dict):
            continue
        erp_request_id = str(row.get("erp_request_id") or "").strip()
        bill_no = str(row.get("bill_no") or "").strip()
        material_code = str(row.get("material_code") or "").strip()
        if not erp_request_id and bill_no and material_code:
            erp_request_id = f"{bill_no}_{material_code}"
        if not erp_request_id:
            continue
        normalized_rows.append({
            "id": row.get("id"),
            "erp_request_id": erp_request_id,
            "bill_no": bill_no,
            "project_info": row.get("project_info") or {},
            "material_code": material_code,
            "material_name": str(row.get("material_name") or "").strip(),
            "material_model": str(row.get("material_model") or "").strip(),
            "price_unit_name": str(row.get("price_unit_name") or "").strip(),
            "qty": float(row.get("qty") or 0),
            "target_price": row.get("target_price"),
            "delivery_date": str(row.get("delivery_date") or "").strip(),
        })
    return normalized_rows


def _count_unique_material_items(selected_rows: list[dict[str, Any]]) -> int:
    material_keys = {
        (
            str(row.get("material_code") or "").strip(),
            str(row.get("material_model") or "").strip(),
            str(row.get("delivery_date") or "").strip(),
        )
        for row in (selected_rows or [])
    }
    return len([item for item in material_keys if any(item)])


def _pick_recommendation_basis(selected_rows: list[dict[str, Any]]) -> tuple[str, float, str | None]:
    if not selected_rows:
        return "", 0.0, None

    grouped_rows: dict[str, dict[str, Any]] = {}
    for row in selected_rows:
        material_code = str(row.get("material_code") or "").strip()
        if not material_code:
            continue
        current = grouped_rows.setdefault(material_code, {
            "qty": 0.0,
            "delivery_date": None,
            "count": 0,
        })
        current["qty"] += float(row.get("qty") or 0)
        current["count"] += 1
        delivery_date = str(row.get("delivery_date") or "").strip() or None
        if delivery_date and not current["delivery_date"]:
            current["delivery_date"] = delivery_date

    if not grouped_rows:
        return "", 0.0, None

    material_code, summary = max(
        grouped_rows.items(),
        key=lambda item: (item[1]["count"], item[1]["qty"]),
    )
    return material_code, float(summary["qty"] or 0), summary["delivery_date"]


def _find_existing_requests(
    db: Session,
    request_ids: list[Any] | None,
    selected_requests: list[dict[str, Any]] | None = None,
) -> tuple[list[InquiryRequest], dict[str, InquiryRequest]]:
    normalized_request_ids = [str(item).strip() for item in (request_ids or []) if str(item).strip()]
    numeric_ids = [int(item) for item in normalized_request_ids if item.isdigit()]
    erp_request_ids = [item for item in normalized_request_ids if not item.isdigit()]
    normalized_selected_rows = _normalize_selected_request_rows(selected_requests)
    for row in normalized_selected_rows:
        erp_request_id = str(row.get("erp_request_id") or "").strip()
        if erp_request_id and erp_request_id not in erp_request_ids:
            erp_request_ids.append(erp_request_id)

    query = db.query(InquiryRequest)
    filters = []
    if numeric_ids:
        filters.append(InquiryRequest.id.in_(numeric_ids))
    if erp_request_ids:
        filters.append(InquiryRequest.erp_request_id.in_(erp_request_ids))
    if not filters:
        return [], {}

    rows = query.filter(*filters).all() if len(filters) == 1 else query.filter(*filters[:1]).all()
    if len(filters) > 1:
        rows = query.filter((InquiryRequest.id.in_(numeric_ids)) | (InquiryRequest.erp_request_id.in_(erp_request_ids))).all()

    request_map: dict[str, InquiryRequest] = {}
    for row in rows:
        request_map[str(row.id)] = row
        if row.erp_request_id:
            request_map[str(row.erp_request_id)] = row
    return rows, request_map


def create_inquiry_from_selected_requests(
    db: Session,
    user: User,
    request_ids: list[Any],
    deadline: str | None = None,
    supplier_ids: list[int] | None = None,
    title: str | None = None,
    selected_requests: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    _require_procurement_roles(user)
    normalized_rows = _normalize_selected_request_rows(selected_requests)
    normalized_request_ids = [str(item).strip() for item in (request_ids or []) if str(item).strip()]
    if not normalized_request_ids and not normalized_rows:
        raise HTTPException(status_code=400, detail="request_ids is required")

    existing_requests, _request_map = _find_existing_requests(db, normalized_request_ids, normalized_rows)
    supplier_ids = _normalize_supplier_ids(supplier_ids)

    recommendation = None
    recommendation_material_code, recommendation_qty, recommendation_delivery_date = _pick_recommendation_basis(normalized_rows)
    if recommendation_material_code and recommendation_qty > 0:
        recommendation = recommend_suppliers_for_inquiry(
            db=db,
            user=user,
            material_code=recommendation_material_code,
            qty=recommendation_qty,
            delivery_date=recommendation_delivery_date,
            limit=3,
        )
        if not supplier_ids:
            supplier_ids = _normalize_supplier_ids([
                item.get("supplier_id")
                for item in (recommendation.get("recommended_suppliers") or [])
            ])

    preview_source = existing_requests[0] if existing_requests else None
    preview_material_name = (
        (preview_source.material_name if preview_source else "")
        or str((normalized_rows[0] or {}).get("material_name") if normalized_rows else "")
        or "已勾选采购申请"
    )
    request_count = len(normalized_rows)
    material_item_count = _count_unique_material_items(normalized_rows)
    draft_title = str(title or f"AI询价任务-{preview_material_name}-{datetime.now().strftime('%m%d%H%M')}").strip()
    price_reference = (recommendation or {}).get("price_reference") or {}
    target_price = price_reference.get("avg_price")
    has_price_reference = any(price_reference.get(key) is not None for key in ("min_price", "max_price", "avg_price"))
    has_recommended_suppliers = bool(supplier_ids)
    manual_input_required = not has_price_reference or not has_recommended_suppliers
    risk_notes = list((recommendation or {}).get("risk_notes") or [])
    if not has_price_reference:
        risk_notes.append("未查到可参考的历史价格，请人工补充目标价或最高限价。")
    if not has_recommended_suppliers:
        risk_notes.append("未生成可直接使用的推荐供应商，请人工补充供应商后再提交。")

    payload = {
        "request_ids": normalized_request_ids,
        "selected_requests": normalized_rows,
        "deadline": str(deadline or "").strip() or None,
        "supplier_ids": supplier_ids,
        "execution_mode": "draft_only" if manual_input_required else "send_now",
        "title": draft_title,
        "type": "auto",
        "price_reference": price_reference,
        "recommended_suppliers": (recommendation or {}).get("recommended_suppliers") or [],
        "recommendation_material_code": recommendation_material_code or None,
        "target_price": target_price,
    }
    preview = {
        "title": draft_title,
        "request_count": request_count,
        "selected_line_count": len(normalized_rows),
        "material_item_count": material_item_count,
        "recommended_supplier_count": len(supplier_ids),
        "bill_nos": [row.get("bill_no") for row in normalized_rows[:5] if row.get("bill_no")],
        "material_names": [row.get("material_name") for row in normalized_rows[:5] if row.get("material_name")],
        "material_codes": [
            row.material_code for row in existing_requests[:5] if getattr(row, "material_code", None)
        ] or [row.get("material_code") for row in normalized_rows[:5] if row.get("material_code")],
        "material_models": [row.get("material_model") for row in normalized_rows[:5] if row.get("material_model")],
        "qty_total": round(sum(float(row.get("qty") or 0) for row in normalized_rows), 4) if normalized_rows else None,
        "delivery_dates": [row.get("delivery_date") for row in normalized_rows[:5] if row.get("delivery_date")],
        "deadline": str(deadline or "").strip() or None,
        "supplier_ids": supplier_ids,
        "recommended_suppliers": (recommendation or {}).get("recommended_suppliers") or [],
        "supplier_names": [
            item.get("supplier_name")
            for item in ((recommendation or {}).get("recommended_suppliers") or [])
            if item.get("supplier_name")
        ],
        "price_reference": price_reference,
        "target_price_suggestion": target_price,
        "risk_notes": risk_notes,
        "recommendation_material_code": recommendation_material_code or None,
        "status": "ai_draft",
        "existing_request_count": len(existing_requests),
        "plan_mode": "auto_inquiry",
        "manual_input_required": manual_input_required,
        "expected_operation": "确认后将创建询价任务，并给供应商发送询价单",
    }
    pending_action = _create_pending_action(db, user, "create_inquiry_from_selected_requests", payload, preview)

    log_operation(
        db,
        user.id,
        "AGENT_CREATE_INQUIRY_FROM_SELECTED_REQUESTS",
        f"AI 生成勾选采购申请询价草稿待确认: {draft_title}",
        module="采购智能体",
        target_type="询价草稿",
        target_name=draft_title,
        result="success",
        extra_data={
            "pending_action_id": pending_action.id,
            "request_ids": normalized_request_ids,
            "selected_request_count": len(normalized_rows),
        },
    )
    return {
        "pending_action_id": pending_action.id,
        "action_type": "create_inquiry_from_selected_requests",
        "status": "pending_confirmation",
        "preview": preview,
        "message": "自动询价方案已生成，您可以确认发送询价单，或仅保存为草稿。",
    }


def save_manual_quotes(
    db: Session,
    user: User,
    request_ids: list[Any],
    selected_requests: list[dict[str, Any]] | None = None,
    title: str | None = None,
) -> dict[str, Any]:
    """手动比价模式：基于勾选采购申请生成手动询价任务草稿，并创建待确认的报价录入动作。

    与 auto_inquiry 的区别：
    - 不发送询价单给供应商
    - type=manual，status=ai_draft
    - 待确认动作类型为 save_manual_quotes，前端展示报价录入卡片
    - 确认后创建 InquirySupplier 链接（status=draft），等待采购员录入 Quotation
    """
    _require_procurement_roles(user)
    normalized_rows = _normalize_selected_request_rows(selected_requests)
    normalized_request_ids = [str(item).strip() for item in (request_ids or []) if str(item).strip()]
    if not normalized_request_ids and not normalized_rows:
        raise HTTPException(status_code=400, detail="request_ids is required")

    existing_requests, _request_map = _find_existing_requests(db, normalized_request_ids, normalized_rows)

    # 推荐供应商（仅作为参考，不发送询价单）
    recommendation = None
    recommendation_material_code, recommendation_qty, recommendation_delivery_date = _pick_recommendation_basis(normalized_rows)
    if recommendation_material_code and recommendation_qty > 0:
        try:
            recommendation = recommend_suppliers_for_inquiry(
                db=db,
                user=user,
                material_code=recommendation_material_code,
                qty=recommendation_qty,
                delivery_date=recommendation_delivery_date,
                limit=5,
            )
        except HTTPException:
            recommendation = None

    preview_source = existing_requests[0] if existing_requests else None
    preview_material_name = (
        (preview_source.material_name if preview_source else "")
        or str((normalized_rows[0] or {}).get("material_name") if normalized_rows else "")
        or "已勾选采购申请"
    )
    request_count = len(normalized_rows)
    material_item_count = _count_unique_material_items(normalized_rows)
    draft_title = str(title or f"手动比价任务-{preview_material_name}-{datetime.now().strftime('%m%d%H%M')}").strip()
    target_price = ((recommendation or {}).get("price_reference") or {}).get("avg_price")

    # 构造物料明细（供前端报价录入卡片展示）
    material_lines: list[dict[str, Any]] = []
    for row in normalized_rows:
        material_lines.append({
            "erp_request_id": row.get("erp_request_id"),
            "bill_no": row.get("bill_no"),
            "material_code": row.get("material_code"),
            "material_name": row.get("material_name"),
            "material_model": row.get("material_model"),
            "qty": row.get("qty"),
            "delivery_date": row.get("delivery_date"),
            "target_price": row.get("target_price"),
        })

    # 推荐供应商列表（供前端选择）
    recommended_suppliers = (recommendation or {}).get("recommended_suppliers") or []
    supplier_options = [
        {
            "supplier_id": item.get("supplier_id"),
            "supplier_name": item.get("supplier_name"),
            "supplier_code": item.get("supplier_code"),
            "avg_price": item.get("avg_price"),
            "latest_price": item.get("latest_price"),
            "rating_score": item.get("rating_score"),
            "recommend_reason": item.get("recommend_reason"),
        }
        for item in recommended_suppliers
        if item.get("supplier_id")
    ]

    # 收集勾选物料的历史采购信息（价格趋势、历史订单明细等），供卡片展示参考
    material_history = _collect_material_history(db, normalized_rows)

    payload = {
        "request_ids": normalized_request_ids,
        "selected_requests": normalized_rows,
        "title": draft_title,
        "type": "manual",
        "price_reference": (recommendation or {}).get("price_reference") or {},
        "recommended_suppliers": recommended_suppliers,
        "recommendation_material_code": recommendation_material_code or None,
        "target_price": target_price,
    }
    preview = {
        "title": draft_title,
        "request_count": request_count,
        "selected_line_count": len(normalized_rows),
        "material_item_count": material_item_count,
        "bill_nos": [row.get("bill_no") for row in normalized_rows[:5] if row.get("bill_no")],
        "material_names": [row.get("material_name") for row in normalized_rows[:5] if row.get("material_name")],
        "material_codes": [
            row.material_code for row in existing_requests[:5] if getattr(row, "material_code", None)
        ] or [row.get("material_code") for row in normalized_rows[:5] if row.get("material_code")],
        "material_models": [row.get("material_model") for row in normalized_rows[:5] if row.get("material_model")],
        "qty_total": round(sum(float(row.get("qty") or 0) for row in normalized_rows), 4) if normalized_rows else None,
        "delivery_dates": [row.get("delivery_date") for row in normalized_rows[:5] if row.get("delivery_date")],
        "material_lines": material_lines,
        "supplier_options": supplier_options,
        "price_reference": (recommendation or {}).get("price_reference") or {},
        "target_price_suggestion": target_price,
        "risk_notes": (recommendation or {}).get("risk_notes") or [],
        "material_history": material_history,
        "status": "ai_draft",
        "plan_mode": "manual_compare",
        "expected_operation": "确认后将创建手动比价任务，您可以录入供应商报价后进行比价分析",
    }
    pending_action = _create_pending_action(db, user, "save_manual_quotes", payload, preview)

    log_operation(
        db,
        user.id,
        "AGENT_SAVE_MANUAL_QUOTES",
        f"AI 生成手动比价任务待确认: {draft_title}",
        module="采购智能体",
        target_type="手动比价任务",
        target_name=draft_title,
        result="success",
        extra_data={
            "pending_action_id": pending_action.id,
            "request_ids": normalized_request_ids,
            "selected_request_count": len(normalized_rows),
        },
    )
    return {
        "pending_action_id": pending_action.id,
        "action_type": "save_manual_quotes",
        "status": "pending_confirmation",
        "preview": preview,
        "message": "手动比价方案已生成，确认后创建手动比价任务，您可以录入供应商报价。",
    }


def create_inquiry_draft(
    db: Session,
    user: User,
    material_code: str,
    qty: float,
    delivery_date: str,
    limit: int = 3,
) -> dict[str, Any]:
    _require_procurement_roles(user)
    if qty is None or float(qty) <= 0:
        raise HTTPException(status_code=400, detail="qty must be greater than 0")

    delivery_dt = _parse_delivery_date(delivery_date)
    material = _resolve_material(db, material_code)
    recommendation = recommend_suppliers_for_inquiry(
        db=db,
        user=user,
        material_code=material_code,
        qty=qty,
        delivery_date=delivery_date,
        limit=limit,
    )
    supplier_items = recommendation.get("recommended_suppliers") or []
    supplier_ids = [int(item["supplier_id"]) for item in supplier_items if item.get("supplier_id")]
    price_reference = recommendation.get("price_reference") or {}
    target_price = price_reference.get("avg_price") or price_reference.get("max_price")
    title = f"AI询价草稿-{material.name if material else material_code}-{datetime.now().strftime('%m%d%H%M')}"

    payload = {
        "title": title,
        "type": "auto",
        "deadline": delivery_dt.isoformat() if delivery_dt else None,
        "material_code": material_code,
        "material_name": material.name if material else "",
        "material_model": material.specification if material else "",
        "qty": float(qty),
        "delivery_date": delivery_dt.isoformat() if delivery_dt else None,
        "supplier_ids": supplier_ids,
        "price_reference": price_reference,
        "target_price": target_price,
        "price_unit_name": material.base_unit if material else None,
        "recommended_suppliers": supplier_items,
    }
    preview = {
        "title": title,
        "material_code": payload["material_code"],
        "material_name": payload["material_name"],
        "material_model": payload["material_model"],
        "qty": payload["qty"],
        "delivery_date": delivery_date,
        "supplier_ids": supplier_ids,
        "recommended_suppliers": supplier_items,
        "supplier_names": [item.get("supplier_name") for item in supplier_items],
        "price_reference": price_reference,
        "target_price_suggestion": target_price,
        "status": "ai_draft",
    }
    pending_action = _create_pending_action(db, user, "create_inquiry_draft", payload, preview)

    log_operation(
        db,
        user.id,
        "AGENT_CREATE_INQUIRY_DRAFT",
        f"AI 生成询价草稿待确认: {title}",
        module="采购智能体",
        target_type="询价草稿",
        target_name=title,
        result="success",
        extra_data={"pending_action_id": pending_action.id, "material_code": material_code},
    )

    return {
        "pending_action_id": pending_action.id,
        "action_type": "create_inquiry_draft",
        "status": "pending_confirmation",
        "preview": preview,
        "message": "已生成询价草稿，请人工确认后创建 ai_draft 询价单。",
    }


def generate_inquiry_message(
    db: Session,
    user: User,
    material_code: str,
    qty: float,
    delivery_date: str,
    supplier_names: list[str] | None = None,
) -> dict[str, Any]:
    _require_procurement_roles(user)
    material = _resolve_material(db, material_code)
    if qty is None or float(qty) <= 0:
        raise HTTPException(status_code=400, detail="qty must be greater than 0")

    material_name = material.name if material else material_code
    specification = material.specification if material else ""
    suppliers_text = ""
    if supplier_names:
        suppliers_text = f"建议询价对象：{'、'.join([str(item).strip() for item in supplier_names if str(item).strip()])}\n"
    message = (
        "您好，现有以下物料需要询价：\n\n"
        f"物料名称：{material_name}\n"
        f"物料编码：{material_code}\n"
        f"规格型号：{specification or '待确认'}\n"
        f"数量：{float(qty):g}\n"
        f"期望交期：{delivery_date}\n"
        f"{suppliers_text}"
        "请提供含税单价、交期、付款条件及报价有效期。\n\n"
        "谢谢。"
    )

    log_operation(
        db,
        user.id,
        "AGENT_GENERATE_INQUIRY_MESSAGE",
        f"AI 生成询价话术: {material_code}",
        module="采购智能体",
        target_type="询价话术",
        target_name=material_code,
        result="success",
        extra_data={"material_code": material_code, "qty": qty},
    )
    return {
        "material_code": material_code,
        "material_name": material_name,
        "message": message,
    }


def create_contract_draft_from_award(
    db: Session,
    user: User,
    inquiry_id: int,
    supplier_id: int,
    template_id: int | None = None,
) -> dict[str, Any]:
    _require_procurement_roles(user)
    task = db.query(InquiryTask).filter(InquiryTask.id == inquiry_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Inquiry task not found")

    link = (
        db.query(InquirySupplier)
        .filter(InquirySupplier.task_id == task.id, InquirySupplier.supplier_id == supplier_id)
        .first()
    )
    if not link:
        raise HTTPException(status_code=404, detail="Supplier is not part of the inquiry task")

    template = None
    if template_id is not None:
        template = db.query(ContractTemplate).filter(ContractTemplate.id == template_id).first()
        if not template:
            raise HTTPException(status_code=404, detail="Contract template not found")
    if template is None:
        template = (
            db.query(ContractTemplate)
            .filter(ContractTemplate.is_active == True)
            .order_by(ContractTemplate.id.desc())
            .first()
        )

    quotes = (
        db.query(Quotation)
        .filter(Quotation.inquiry_supplier_id == link.id)
        .order_by(Quotation.round.desc(), Quotation.created_at.desc())
        .all()
    )
    latest_by_item: dict[int, Quotation] = {}
    for quote in quotes:
        latest_by_item.setdefault(int(quote.item_id), quote)
    effective_quotes = list(latest_by_item.values())
    if task.type == "auto" and not effective_quotes:
        raise HTTPException(status_code=400, detail="Automatic inquiry has no supplier quotations yet, contract draft cannot be generated")
    total_amount = round(sum(float(item.qty or 0) * float(item.price or 0) for item in effective_quotes), 2)
    payload = {
        "task_id": task.id,
        "inquiry_supplier_id": link.id,
        "supplier_id": supplier_id,
        "template_id": template.id if template else None,
        "template_name": template.name if template else None,
        "buyer_company_name": template.default_buyer_name if template else None,
        "total_amount": total_amount,
    }
    preview = {
        "task_title": task.title,
        "supplier_name": link.supplier.name if link.supplier else f"Supplier-{supplier_id}",
        "template_name": template.name if template else "",
        "total_amount": total_amount,
        "quote_count": len(effective_quotes),
        "status": "draft",
    }
    pending_action = _create_pending_action(db, user, "create_contract_draft", payload, preview)

    log_operation(
        db,
        user.id,
        "AGENT_CREATE_CONTRACT_DRAFT",
        f"AI 生成合同草稿待确认: {task.title}",
        module="采购智能体",
        target_type="合同草稿",
        target_name=task.title,
        result="success",
        extra_data={"pending_action_id": pending_action.id, "task_id": task.id, "supplier_id": supplier_id},
    )
    return {
        "pending_action_id": pending_action.id,
        "action_type": "create_contract_draft",
        "status": "pending_confirmation",
        "preview": preview,
        "message": "已生成合同草稿待确认，确认后将创建合同草稿记录，不会自动提交合同。",
    }


def publish_inquiry_task(
    db: Session,
    user: User,
    inquiry_id: int,
) -> dict[str, Any]:
    _require_procurement_roles(user)
    task = db.query(InquiryTask).filter(InquiryTask.id == inquiry_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Inquiry task not found")
    if user.role == "buyer" and task.buyer_id != user.id:
        raise HTTPException(status_code=403, detail="You can only publish your own inquiry task drafts")
    if task.status != TaskStatus.AI_DRAFT:
        raise HTTPException(status_code=400, detail="Only ai_draft inquiry tasks can be published")

    supplier_links = db.query(InquirySupplier).filter(InquirySupplier.task_id == task.id).all()
    supplier_ids = _normalize_supplier_ids([link.supplier_id for link in supplier_links])
    if not supplier_ids:
        supplier_ids = _normalize_supplier_ids((task.strategy_config or {}).get("pending_supplier_ids"))
    if not supplier_ids:
        raise HTTPException(status_code=400, detail="No suppliers are associated with this inquiry draft")

    preview = {
        "task_id": task.id,
        "task_title": task.title,
        "supplier_ids": supplier_ids,
        "supplier_names": [
            link.supplier.name
            for link in supplier_links
            if getattr(link, "supplier", None) and link.supplier.name
        ],
        "supplier_count": len(supplier_ids),
        "status_before": task.status,
        "status_after": _get_task_activated_status(task),
        "deadline": task.deadline.strftime("%Y-%m-%d") if task.deadline else None,
        "type": task.type,
    }
    payload = {
        "task_id": task.id,
        "supplier_ids": supplier_ids,
    }
    pending_action = _create_pending_action(db, user, "publish_inquiry_task", payload, preview)

    log_operation(
        db,
        user.id,
        "AGENT_PUBLISH_INQUIRY_TASK",
        f"AI generated publish confirmation for inquiry task: {task.title}",
        module="procurement_agent",
        target_type="inquiry_task",
        target_name=task.title,
        result="success",
        extra_data={
            "pending_action_id": pending_action.id,
            "task_id": task.id,
            "supplier_ids": supplier_ids,
        },
    )
    return {
        "pending_action_id": pending_action.id,
        "action_type": "publish_inquiry_task",
        "status": "pending_confirmation",
        "preview": preview,
        "message": "The inquiry task is ready to publish. After confirmation, the system will reuse the existing supplier invitation flow.",
    }


def _confirm_create_inquiry_draft(db: Session, user: User, payload: dict[str, Any]) -> dict[str, Any]:
    delivery_dt = _parse_delivery_date(payload.get("delivery_date"))
    material_code = str(payload.get("material_code") or "").strip()
    qty = float(payload.get("qty") or 0)
    if not material_code or qty <= 0:
        raise HTTPException(status_code=400, detail="Invalid inquiry draft payload")

    new_request = InquiryRequest(
        erp_request_id=f"AI-DRAFT-{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
        bill_no=f"AI-DRAFT-{datetime.now().strftime('%H%M%S')}",
        project_info={"source": "procurement_agent"},
        material_code=material_code,
        material_name=str(payload.get("material_name") or ""),
        material_model=str(payload.get("material_model") or "") or None,
        price_unit_name=str(payload.get("price_unit_name") or "") or None,
        qty=qty,
        target_price=payload.get("target_price"),
        delivery_date=delivery_dt,
        status=InquiryStatus.IN_PROCESS,
    )
    db.add(new_request)
    db.flush()

    supplier_ids = _normalize_supplier_ids(payload.get("supplier_ids"))
    strategy_config = {
        "source": "procurement_agent",
        "pending_supplier_ids": supplier_ids,
        "price_reference": payload.get("price_reference") or {},
        "recommended_suppliers": payload.get("recommended_suppliers") or [],
    }
    task = InquiryTask(
        title=str(payload.get("title") or f"AI询价草稿-{material_code}"),
        type=str(payload.get("type") or "manual"),
        strategy_config=strategy_config,
        deadline=delivery_dt,
        status=TaskStatus.AI_DRAFT,
        buyer_id=user.id,
        created_by=user.id,
    )
    db.add(task)
    db.flush()

    db.add(InquiryTaskItem(task_id=task.id, request_id=new_request.id))
    for supplier_id in supplier_ids:
        supplier = db.query(Supplier).filter(Supplier.id == supplier_id).first()
        if not supplier:
            continue
        db.add(InquirySupplier(task_id=task.id, supplier_id=supplier.id, status=LinkStatus.SENT))
    db.commit()
    db.refresh(task)
    return {"task_id": task.id, "status": task.status, "title": task.title, "request_count": 1}


def _confirm_create_inquiry_from_selected_requests(db: Session, user: User, payload: dict[str, Any]) -> dict[str, Any]:
    supplier_ids = _normalize_supplier_ids(payload.get("supplier_ids"))
    execution_mode = str(payload.get("execution_mode") or "draft_only").strip() or "draft_only"
    if execution_mode not in {"send_now", "draft_only"}:
        raise HTTPException(status_code=400, detail="Invalid execution_mode")
    deadline_dt = _parse_delivery_date(payload.get("deadline"))
    selected_rows = _normalize_selected_request_rows(payload.get("selected_requests"))
    _existing_rows, request_map = _find_existing_requests(db, payload.get("request_ids"), selected_rows)

    request_records: list[InquiryRequest] = []
    seen_request_ids: set[int] = set()

    for row in selected_rows:
        request = None
        row_id = row.get("id")
        if row_id is not None:
            request = request_map.get(str(row_id))
        if request is None:
            request = request_map.get(str(row.get("erp_request_id") or "").strip())

        delivery_dt = _parse_delivery_date(row.get("delivery_date"))
        if request is None:
            request = InquiryRequest(
                erp_request_id=str(row.get("erp_request_id") or "").strip(),
                bill_no=str(row.get("bill_no") or "").strip() or None,
                project_info=row.get("project_info") or {},
                material_code=str(row.get("material_code") or "").strip(),
                material_name=str(row.get("material_name") or "").strip(),
                material_model=str(row.get("material_model") or "").strip() or None,
                price_unit_name=str(row.get("price_unit_name") or "").strip() or None,
                qty=float(row.get("qty") or 0),
                target_price=row.get("target_price"),
                delivery_date=delivery_dt,
                status=InquiryStatus.IN_PROCESS,
            )
            db.add(request)
            db.flush()
            request_map[str(request.id)] = request
            if request.erp_request_id:
                request_map[str(request.erp_request_id)] = request
        else:
            request.status = InquiryStatus.IN_PROCESS
            effective_target_price = row.get("target_price")
            if effective_target_price is None:
                effective_target_price = payload.get("target_price")
            if effective_target_price is not None:
                request.target_price = effective_target_price
            if row.get("qty") is not None:
                request.qty = float(row.get("qty") or 0)
            if row.get("material_model"):
                request.material_model = str(row.get("material_model") or "").strip()
            if row.get("price_unit_name"):
                request.price_unit_name = str(row.get("price_unit_name") or "").strip()
            if delivery_dt:
                request.delivery_date = delivery_dt

        if request.id not in seen_request_ids:
            seen_request_ids.add(request.id)
            request_records.append(request)

    for raw_request_id in payload.get("request_ids") or []:
        request = request_map.get(str(raw_request_id).strip())
        if not request:
            continue
        request.status = InquiryStatus.IN_PROCESS
        if request.target_price is None and payload.get("target_price") is not None:
            request.target_price = payload.get("target_price")
        if request.id not in seen_request_ids:
            seen_request_ids.add(request.id)
            request_records.append(request)

    if not request_records:
        raise HTTPException(status_code=400, detail="No valid selected requests were found")

    title = str(payload.get("title") or f"AI询价任务-{datetime.now().strftime('%m%d%H%M')}").strip()
    strategy_config = {
        "source": "procurement_agent",
        "pending_supplier_ids": supplier_ids,
        "selected_request_ids": [request.id for request in request_records],
        "selected_erp_request_ids": [request.erp_request_id for request in request_records if request.erp_request_id],
        "price_reference": payload.get("price_reference") or {},
        "recommended_suppliers": payload.get("recommended_suppliers") or [],
        "recommendation_material_code": payload.get("recommendation_material_code"),
    }
    task = InquiryTask(
        title=title,
        type=str(payload.get("type") or "manual"),
        strategy_config=strategy_config,
        deadline=deadline_dt,
        status=TaskStatus.AI_DRAFT,
        buyer_id=user.id,
        created_by=user.id,
    )
    db.add(task)
    db.flush()

    for request in request_records:
        db.add(InquiryTaskItem(task_id=task.id, request_id=request.id))

    for supplier_id in supplier_ids:
        supplier = db.query(Supplier).filter(Supplier.id == supplier_id).first()
        if not supplier:
            continue
        db.add(InquirySupplier(task_id=task.id, supplier_id=supplier.id, status=LinkStatus.SENT))

    db.commit()
    db.refresh(task)
    result = {
        "task_id": task.id,
        "status": task.status,
        "title": task.title,
        "request_count": len(request_records),
        "supplier_count": len(supplier_ids),
    }
    if execution_mode == "send_now":
        publish_result = _publish_inquiry_task_core(db, task, supplier_ids)
        result.update({
            "status": publish_result.get("status"),
            "published": True,
            "publish_result": publish_result,
        })
    else:
        result["published"] = False
    return result


def _resolve_task_item_for_manual_quote(
    task_items: list[InquiryTaskItem],
    entry: dict[str, Any],
) -> InquiryTaskItem | None:
    request_id = entry.get("request_id")
    erp_request_id = str(entry.get("erp_request_id") or "").strip()
    material_code = str(entry.get("material_code") or "").strip()

    for item in task_items:
        request = item.request
        if not request:
            continue
        if request_id not in (None, "") and int(request.id) == int(request_id):
            return item
        if erp_request_id and str(request.erp_request_id or "").strip() == erp_request_id:
            return item
    for item in task_items:
        request = item.request
        if request and material_code and str(request.material_code or "").strip() == material_code:
            return item
    return None


def _upsert_manual_quotes_for_task(
    db: Session,
    task: InquiryTask,
    quote_entries: list[dict[str, Any]],
) -> int:
    if not quote_entries:
        return 0

    task_items = list(task.items or [])
    saved_quote_count = 0
    for entry in quote_entries:
        item = _resolve_task_item_for_manual_quote(task_items, entry)
        if not item:
            continue

        for supplier_row in entry.get("suppliers") or []:
            supplier = None
            supplier_id = supplier_row.get("supplier_id")
            if supplier_id not in (None, ""):
                supplier = db.query(Supplier).filter(Supplier.id == int(supplier_id)).first()
            if supplier is None and supplier_row.get("supplier_code"):
                supplier = db.query(Supplier).filter(Supplier.code == supplier_row["supplier_code"]).first()
            if supplier is None and supplier_row.get("supplier_name"):
                supplier = db.query(Supplier).filter(Supplier.name == supplier_row["supplier_name"]).first()
            if supplier is None:
                supplier = Supplier(
                    code=str(supplier_row.get("supplier_code") or "").strip() or None,
                    name=str(supplier_row.get("supplier_name") or "").strip() or "未命名供应商",
                )
                db.add(supplier)
                db.flush()

            link = db.query(InquirySupplier).filter(
                InquirySupplier.task_id == task.id,
                InquirySupplier.supplier_id == supplier.id,
            ).first()
            if not link:
                link = InquirySupplier(task_id=task.id, supplier_id=supplier.id, status=LinkStatus.QUOTED)
                db.add(link)
                db.flush()
            else:
                link.status = LinkStatus.QUOTED

            target_round = int(link.current_round or 1)
            quote = db.query(Quotation).filter(
                Quotation.inquiry_supplier_id == link.id,
                Quotation.item_id == item.id,
                Quotation.round == target_round,
            ).first()
            if not quote:
                quote = Quotation(
                    inquiry_supplier_id=link.id,
                    item_id=item.id,
                    round=target_round,
                    price=float(supplier_row["price"]),
                    qty=float(supplier_row["qty"]),
                )
                db.add(quote)
            else:
                quote.price = float(supplier_row["price"])
                quote.qty = float(supplier_row["qty"])

            delivery_date = supplier_row.get("delivery_date")
            if delivery_date:
                quote.delivery_date = _parse_delivery_date(delivery_date)
            saved_quote_count += 1
    return saved_quote_count


def _confirm_save_manual_quotes(db: Session, user: User, payload: dict[str, Any]) -> dict[str, Any]:
    """确认手动比价任务：创建 type=manual 的 InquiryTask（不发送询价单）。

    与 auto_inquiry 的区别：
    - execution_mode 始终为 draft_only，不调用 _publish_inquiry_task_core
    - 不创建 InquirySupplier 链接（等待采购员录入报价时再创建）
    - 任务状态为 ai_draft，等待采购员录入报价后调用 analyze_quotation_compare
    """
    selected_rows = _normalize_selected_request_rows(payload.get("selected_requests"))
    _existing_rows, request_map = _find_existing_requests(db, payload.get("request_ids"), selected_rows)

    request_records: list[InquiryRequest] = []
    seen_request_ids: set[int] = set()

    for row in selected_rows:
        request = None
        row_id = row.get("id")
        if row_id is not None:
            request = request_map.get(str(row_id))
        if request is None:
            request = request_map.get(str(row.get("erp_request_id") or "").strip())

        delivery_dt = _parse_delivery_date(row.get("delivery_date"))
        if request is None:
            request = InquiryRequest(
                erp_request_id=str(row.get("erp_request_id") or "").strip(),
                bill_no=str(row.get("bill_no") or "").strip() or None,
                project_info=row.get("project_info") or {},
                material_code=str(row.get("material_code") or "").strip(),
                material_name=str(row.get("material_name") or "").strip(),
                material_model=str(row.get("material_model") or "").strip() or None,
                price_unit_name=str(row.get("price_unit_name") or "").strip() or None,
                qty=float(row.get("qty") or 0),
                target_price=row.get("target_price"),
                delivery_date=delivery_dt,
                status=InquiryStatus.IN_PROCESS,
            )
            db.add(request)
            db.flush()
            request_map[str(request.id)] = request
            if request.erp_request_id:
                request_map[str(request.erp_request_id)] = request
        else:
            request.status = InquiryStatus.IN_PROCESS
            effective_target_price = row.get("target_price")
            if effective_target_price is None:
                effective_target_price = payload.get("target_price")
            if effective_target_price is not None:
                request.target_price = effective_target_price
            if row.get("qty") is not None:
                request.qty = float(row.get("qty") or 0)
            if row.get("material_model"):
                request.material_model = str(row.get("material_model") or "").strip()
            if row.get("price_unit_name"):
                request.price_unit_name = str(row.get("price_unit_name") or "").strip()
            if delivery_dt:
                request.delivery_date = delivery_dt

        if request.id not in seen_request_ids:
            seen_request_ids.add(request.id)
            request_records.append(request)

    for raw_request_id in payload.get("request_ids") or []:
        request = request_map.get(str(raw_request_id).strip())
        if not request:
            continue
        request.status = InquiryStatus.IN_PROCESS
        if request.target_price is None and payload.get("target_price") is not None:
            request.target_price = payload.get("target_price")
        if request.id not in seen_request_ids:
            seen_request_ids.add(request.id)
            request_records.append(request)

    if not request_records:
        raise HTTPException(status_code=400, detail="No valid selected requests were found")

    title = str(payload.get("title") or f"手动比价任务-{datetime.now().strftime('%m%d%H%M')}").strip()
    strategy_config = {
        "source": "procurement_agent",
        "plan_mode": "manual_compare",
        "selected_request_ids": [request.id for request in request_records],
        "selected_erp_request_ids": [request.erp_request_id for request in request_records if request.erp_request_id],
        "price_reference": payload.get("price_reference") or {},
        "recommended_suppliers": payload.get("recommended_suppliers") or [],
        "recommendation_material_code": payload.get("recommendation_material_code"),
    }
    task = InquiryTask(
        title=title,
        type="manual",
        strategy_config=strategy_config,
        deadline=None,
        status=TaskStatus.AI_DRAFT,
        buyer_id=user.id,
        created_by=user.id,
    )
    db.add(task)
    db.flush()

    for request in request_records:
        db.add(InquiryTaskItem(task_id=task.id, request_id=request.id))

    db.commit()
    db.refresh(task)
    return {
        "task_id": task.id,
        "status": task.status,
        "title": task.title,
        "type": task.type,
        "request_count": len(request_records),
        "published": False,
        "message": "手动比价任务已创建，请录入供应商报价后进行比价分析。",
    }


def _confirm_save_manual_quotes_v2(db: Session, user: User, payload: dict[str, Any]) -> dict[str, Any]:
    selected_rows = _normalize_selected_request_rows(payload.get("selected_requests"))
    _existing_rows, request_map = _find_existing_requests(db, payload.get("request_ids"), selected_rows)

    request_records: list[InquiryRequest] = []
    seen_request_ids: set[int] = set()

    for row in selected_rows:
        request = None
        row_id = row.get("id")
        if row_id is not None:
            request = request_map.get(str(row_id))
        if request is None:
            request = request_map.get(str(row.get("erp_request_id") or "").strip())

        delivery_dt = _parse_delivery_date(row.get("delivery_date"))
        if request is None:
            request = InquiryRequest(
                erp_request_id=str(row.get("erp_request_id") or "").strip(),
                bill_no=str(row.get("bill_no") or "").strip() or None,
                project_info=row.get("project_info") or {},
                material_code=str(row.get("material_code") or "").strip(),
                material_name=str(row.get("material_name") or "").strip(),
                material_model=str(row.get("material_model") or "").strip() or None,
                price_unit_name=str(row.get("price_unit_name") or "").strip() or None,
                qty=float(row.get("qty") or 0),
                target_price=row.get("target_price"),
                delivery_date=delivery_dt,
                status=InquiryStatus.IN_PROCESS,
            )
            db.add(request)
            db.flush()
            request_map[str(request.id)] = request
            if request.erp_request_id:
                request_map[str(request.erp_request_id)] = request
        else:
            request.status = InquiryStatus.IN_PROCESS
            effective_target_price = row.get("target_price")
            if effective_target_price is None:
                effective_target_price = payload.get("target_price")
            if effective_target_price is not None:
                request.target_price = effective_target_price
            if row.get("qty") is not None:
                request.qty = float(row.get("qty") or 0)
            if row.get("material_model"):
                request.material_model = str(row.get("material_model") or "").strip()
            if row.get("price_unit_name"):
                request.price_unit_name = str(row.get("price_unit_name") or "").strip()
            if delivery_dt:
                request.delivery_date = delivery_dt

        if request.id not in seen_request_ids:
            seen_request_ids.add(request.id)
            request_records.append(request)

    for raw_request_id in payload.get("request_ids") or []:
        request = request_map.get(str(raw_request_id).strip())
        if not request:
            continue
        request.status = InquiryStatus.IN_PROCESS
        if request.target_price is None and payload.get("target_price") is not None:
            request.target_price = payload.get("target_price")
        if request.id not in seen_request_ids:
            seen_request_ids.add(request.id)
            request_records.append(request)

    if not request_records:
        raise HTTPException(status_code=400, detail="No valid selected requests were found")

    title = str(payload.get("title") or f"手动比价任务-{datetime.now().strftime('%m%d%H%M')}").strip()
    strategy_config = {
        "source": "procurement_agent",
        "plan_mode": "manual_compare",
        "selected_request_ids": [request.id for request in request_records],
        "selected_erp_request_ids": [request.erp_request_id for request in request_records if request.erp_request_id],
        "price_reference": payload.get("price_reference") or {},
        "recommended_suppliers": payload.get("recommended_suppliers") or [],
        "recommendation_material_code": payload.get("recommendation_material_code"),
    }
    task = InquiryTask(
        title=title,
        type="manual",
        strategy_config=strategy_config,
        deadline=None,
        status=TaskStatus.AI_DRAFT,
        buyer_id=user.id,
        created_by=user.id,
    )
    db.add(task)
    db.flush()

    for request in request_records:
        db.add(InquiryTaskItem(task_id=task.id, request_id=request.id))

    quote_entries = _normalize_manual_quote_entries(payload.get("manual_quote_entries"))
    db.commit()
    db.refresh(task)

    result = {
        "task_id": task.id,
        "status": task.status,
        "title": task.title,
        "type": task.type,
        "request_count": len(request_records),
        "published": False,
        "message": "手动比价任务已创建，请录入供应商报价后进行比价分析。",
    }
    if not quote_entries:
        return result

    saved_quote_count = _upsert_manual_quotes_for_task(db, task, quote_entries)
    db.commit()
    db.refresh(task)

    compare_result = analyze_quotation_compare(
        db=db,
        user=user,
        inquiry_id=task.id,
        request_ids=None,
        selected_requests=None,
        limit=5,
    )
    result.update({
        "saved_quote_count": saved_quote_count,
        "quote_entry_count": len(quote_entries),
        "compare_result": compare_result,
        "message": (
            "已创建手动比价任务并保存报价，系统已生成份额分配建议。"
            if compare_result.get("pending_action_id")
            else (compare_result.get("message") or "已创建手动比价任务并保存报价。")
        ),
    })
    if compare_result.get("pending_action_id"):
        result["next_pending_action"] = {
            "pending_action_id": compare_result.get("pending_action_id"),
            "action_type": compare_result.get("action_type"),
            "preview": compare_result.get("preview"),
            "message": compare_result.get("message"),
        }
    return result


def _confirm_create_contract_draft(db: Session, user: User, payload: dict[str, Any]) -> dict[str, Any]:
    task = db.query(InquiryTask).filter(InquiryTask.id == int(payload.get("task_id"))).first()
    link = db.query(InquirySupplier).filter(InquirySupplier.id == int(payload.get("inquiry_supplier_id"))).first()
    if not task or not link:
        raise HTTPException(status_code=404, detail="Inquiry or supplier link not found")

    contract = db.query(Contract).filter(Contract.inquiry_supplier_id == link.id).first()
    if not contract:
        contract = Contract(
            task_id=task.id,
            inquiry_supplier_id=link.id,
            status="draft",
        )
    contract.total_amount = payload.get("total_amount")
    contract.template_id = payload.get("template_id")
    contract.template_name = payload.get("template_name")
    contract.buyer_company_name = payload.get("buyer_company_name")
    db.add(contract)
    db.commit()
    db.refresh(contract)
    return {"contract_id": contract.id, "status": contract.status, "task_id": task.id}


def _publish_inquiry_task_core(db: Session, task: InquiryTask, supplier_ids: list[int]) -> dict[str, Any]:
    normalized_supplier_ids = _normalize_supplier_ids(supplier_ids)
    if not normalized_supplier_ids:
        normalized_supplier_ids = _normalize_supplier_ids([
            link.supplier_id
            for link in db.query(InquirySupplier).filter(InquirySupplier.task_id == task.id).all()
        ])
    if not normalized_supplier_ids:
        raise HTTPException(status_code=400, detail="No suppliers are associated with this inquiry task")

    existing_links = {
        int(link.supplier_id): link
        for link in db.query(InquirySupplier).filter(InquirySupplier.task_id == task.id).all()
        if link.supplier_id is not None
    }
    for supplier_id in normalized_supplier_ids:
        if supplier_id in existing_links:
            existing_links[supplier_id].status = LinkStatus.SENT
            continue
        supplier = db.query(Supplier).filter(Supplier.id == supplier_id).first()
        if not supplier:
            continue
        db.add(InquirySupplier(task_id=task.id, supplier_id=supplier.id, status=LinkStatus.SENT))

    strategy_config = dict(task.strategy_config or {})
    strategy_config["pending_supplier_ids"] = normalized_supplier_ids
    strategy_config["published_via_agent"] = True
    strategy_config["published_at"] = datetime.now().isoformat()
    task.strategy_config = strategy_config
    task.status = _get_task_activated_status(task)

    db.add(task)
    db.commit()
    db.refresh(task)

    _send_task_invitation_notifications_background(task.id, normalized_supplier_ids)
    return {
        "task_id": task.id,
        "title": task.title,
        "status": task.status,
        "supplier_count": len(normalized_supplier_ids),
        "notified_supplier_ids": normalized_supplier_ids,
    }


def _confirm_publish_inquiry_task(db: Session, user: User, payload: dict[str, Any]) -> dict[str, Any]:
    task_id = int(payload.get("task_id") or 0)
    task = db.query(InquiryTask).filter(InquiryTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Inquiry task not found")
    if user.role == "buyer" and task.buyer_id != user.id:
        raise HTTPException(status_code=403, detail="You can only publish your own inquiry task drafts")
    if task.status != TaskStatus.AI_DRAFT:
        raise HTTPException(status_code=400, detail="Only ai_draft inquiry tasks can be published")

    return _publish_inquiry_task_core(db, task, _normalize_supplier_ids(payload.get("supplier_ids")))


def confirm_pending_action(
    db: Session,
    user: User,
    action_id: int,
    request: Request | None = None,
    payload_overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    _require_procurement_roles(user)
    action = db.query(AgentPendingAction).filter(AgentPendingAction.id == action_id).first()
    if not action:
        raise HTTPException(status_code=404, detail="Pending action not found")
    if action.status != "pending":
        # 幂等返回：已确认的动作不重复执行，返回当前状态让前端优雅处理
        return {
            "id": action.id,
            "action_type": action.action_type,
            "status": action.status,
            "already_processed": True,
            "result": {"message": "该动作已处理，无需重复确认"},
        }
    if user.role == "buyer" and action.created_by != user.id:
        raise HTTPException(status_code=403, detail="You can only confirm your own pending actions")

    payload = _apply_payload_overrides(action.action_type, dict(action.payload or {}), payload_overrides)
    if payload != dict(action.payload or {}):
        action.payload = payload
        action.preview = _build_pending_action_preview(db, action.action_type, payload, action.preview or {})
    if action.action_type == "create_inquiry_draft":
        result = _confirm_create_inquiry_draft(db, user, payload)
    elif action.action_type == "create_inquiry_from_selected_requests":
        result = _confirm_create_inquiry_from_selected_requests(db, user, payload)
    elif action.action_type == "save_manual_quotes":
        result = _confirm_save_manual_quotes_v2(db, user, payload)
    elif action.action_type == "publish_inquiry_task":
        result = _confirm_publish_inquiry_task(db, user, payload)
    elif action.action_type == "confirm_award":
        allocations = payload.get("allocations") or []
        close_payload = None
        selected_link_id = payload.get("selected_link_id")
        normalized_allocations = []
        if allocations:
            normalized_allocations = _normalize_award_allocations(allocations)
            close_payload = TaskClosePayload(
                allocations=[
                    TaskCloseAllocation(
                        link_id=int(row["link_id"]),
                        allocated_ratio=float(row["allocated_ratio"]),
                        allocated_qty=None,
                        item_allocations=None,
                    )
                    for row in normalized_allocations
                ]
            )
            selected_link_id = None
        result = close_inquiry_task(
            task_id=int(payload.get("task_id")),
            payload=close_payload,
            selected_link_id=int(selected_link_id) if selected_link_id not in (None, "") else None,
            db=db,
            current_user=user,
        )
        if normalized_allocations:
            contract_rows = (
                db.query(Contract)
                .join(InquirySupplier, InquirySupplier.id == Contract.inquiry_supplier_id)
                .filter(
                    Contract.task_id == int(payload.get("task_id")),
                    InquirySupplier.id.in_([row["link_id"] for row in normalized_allocations]),
                )
                .all()
            )
            result["contract_count"] = len(contract_rows)
            result["contract_ids"] = [row.id for row in contract_rows]
    elif action.action_type == "create_contract_draft":
        result = _confirm_create_contract_draft(db, user, payload)
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported action_type: {action.action_type}")

    action.status = "confirmed"
    action.confirmed_by = user.id
    action.confirmed_at = datetime.now()
    db.add(action)
    db.commit()
    db.refresh(action)

    log_operation(
        db,
        user.id,
        "AGENT_CONFIRM_ACTION",
        f"确认 AI 待办动作: {action.action_type}",
        request=request,
        module="采购智能体",
        target_type="AI待确认动作",
        target_name=str(action.id),
        result="success",
        extra_data={
            "action_id": action.id,
            "action_type": action.action_type,
            "payload_overrides": payload_overrides or {},
            "result": result,
        },
    )
    return {
        "id": action.id,
        "action_type": action.action_type,
        "status": action.status,
        "result": result,
    }
