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
from procurement_agent.risk_checker import recommend_suppliers_for_inquiry
from routers.inquiry import close_inquiry_task
from routers.system import log_operation


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
        "type": "manual",
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
        "status": "pending_confirmation",
        "preview": preview,
        "message": "已生成合同草稿待确认，确认后将创建合同草稿记录，不会自动提交合同。",
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
        status="in_process",
    )
    db.add(new_request)
    db.flush()

    strategy_config = {
        "source": "procurement_agent",
        "pending_supplier_ids": payload.get("supplier_ids") or [],
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
    db.commit()
    db.refresh(task)
    return {"task_id": task.id, "status": task.status, "title": task.title}


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


def confirm_pending_action(
    db: Session,
    user: User,
    action_id: int,
    request: Request | None = None,
) -> dict[str, Any]:
    _require_procurement_roles(user)
    action = db.query(AgentPendingAction).filter(AgentPendingAction.id == action_id).first()
    if not action:
        raise HTTPException(status_code=404, detail="Pending action not found")
    if action.status != "pending":
        raise HTTPException(status_code=400, detail="Pending action is already processed")
    if user.role == "buyer" and action.created_by != user.id:
        raise HTTPException(status_code=403, detail="You can only confirm your own pending actions")

    payload = dict(action.payload or {})
    if action.action_type == "create_inquiry_draft":
        result = _confirm_create_inquiry_draft(db, user, payload)
    elif action.action_type == "confirm_award":
        result = close_inquiry_task(
            task_id=int(payload.get("task_id")),
            payload=None,
            selected_link_id=int(payload.get("selected_link_id")),
            db=db,
            current_user=user,
        )
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
        extra_data={"action_id": action.id, "action_type": action.action_type, "result": result},
    )
    return {
        "id": action.id,
        "action_type": action.action_type,
        "status": action.status,
        "result": result,
    }
