from fastapi import APIRouter, Body, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Any, Optional
from pydantic import BaseModel
import uuid
from datetime import datetime, date
from decimal import Decimal, ROUND_FLOOR

from models import (
    get_db, User, InquiryRequest, InquiryTask, InquiryTaskItem,
    Supplier, InquirySupplier, InquiryStatus, TaskStatus, LinkStatus, Quotation, Contract, ContractTemplate,
    ensure_runtime_schema_columns, CompareDraft
)
from schemas import (
    InquiryTaskCreate, InquiryTask as InquiryTaskSchema, StrategyConfig,
    InquiryRequest as InquiryRequestSchema, TaskClosePayload
)
from routers.auth import oauth2_scheme, login_access_token # reuse auth but simpler dependency
from services.negotiation_service import calculate_supplier_scores

# 简单的用户获取依赖
from jose import jwt, JWTError
from core.config import settings

router = APIRouter()

class ManualInterventionPayload(BaseModel):
    message: Optional[str] = None


def _load_link_quotes(db: Session, link: InquirySupplier):
    quotes = db.query(Quotation).filter(
        Quotation.inquiry_supplier_id == link.id,
        Quotation.round == link.current_round
    ).all()
    if not quotes:
        quotes = db.query(Quotation).filter(
            Quotation.inquiry_supplier_id == link.id
        ).order_by(Quotation.round.desc(), Quotation.id.asc()).all()
        if quotes:
            max_round = quotes[0].round
            quotes = [q for q in quotes if q.round == max_round]
    return quotes


def _parse_link_item_allocations(link: InquirySupplier) -> dict:
    parsed = {}
    for row in (link.item_allocations or []):
        if not isinstance(row, dict):
            continue
        try:
            item_id = int(row.get("item_id"))
        except (TypeError, ValueError):
            continue
        parsed[item_id] = {
            "allocated_ratio": float(row.get("allocated_ratio")) if row.get("allocated_ratio") is not None else None,
            "allocated_qty": float(row.get("allocated_qty")) if row.get("allocated_qty") is not None else None,
        }
    return parsed


def _build_link_quote_rows(db: Session, link: InquirySupplier) -> list:
    quote_rows = []
    for quote in _load_link_quotes(db, link):
        task_item = db.query(InquiryTaskItem).filter(InquiryTaskItem.id == quote.item_id).first()
        request = db.query(InquiryRequest).filter(InquiryRequest.id == task_item.request_id).first() if task_item else None
        base_qty = _to_decimal(request.qty if request and request.qty is not None else (quote.qty or 0))
        quote_rows.append({
            "quote": quote,
            "task_item": task_item,
            "request": request,
            "base_qty": base_qty,
        })
    return quote_rows


def _build_item_level_allocated_qty_map(task: InquiryTask, quote_rows: list, link: InquirySupplier) -> dict:
    current_item_allocations = _parse_link_item_allocations(link)
    if not current_item_allocations:
        return {}

    deal_links = [l for l in (task.suppliers or []) if l.status == LinkStatus.DEAL]
    parsed_by_link_id = {deal_link.id: _parse_link_item_allocations(deal_link) for deal_link in deal_links}
    result_for_current = {}

    for row in quote_rows:
        task_item = row["task_item"]
        item_id = int(task_item.id if task_item else row["quote"].item_id)
        current_cfg = current_item_allocations.get(item_id)
        if not current_cfg:
            continue

        quote_id = row["quote"].id
        base_qty = row["base_qty"]

        if current_cfg.get("allocated_qty") is not None:
            result_for_current[quote_id] = _to_decimal(current_cfg["allocated_qty"])
            continue

        item_level_configs = {}
        has_item_level_config = False
        has_explicit_qty = False
        for deal_link in deal_links:
            cfg = parsed_by_link_id.get(deal_link.id, {}).get(item_id)
            if not cfg:
                continue
            has_item_level_config = True
            if cfg.get("allocated_qty") is not None:
                has_explicit_qty = True
            item_level_configs[deal_link.id] = cfg

        if has_item_level_config:
            if has_explicit_qty:
                current_qty = item_level_configs.get(link.id, {}).get("allocated_qty")
                result_for_current[quote_id] = _to_decimal(current_qty)
                continue

            current_ratio = _to_decimal(item_level_configs.get(link.id, {}).get("allocated_ratio")) / Decimal("100")
            if current_ratio <= 0:
                result_for_current[quote_id] = Decimal("0")
                continue
            if base_qty != base_qty.to_integral_value():
                result_for_current[quote_id] = base_qty * current_ratio
                continue

            total_int = int(base_qty)
            floors = {}
            remainders = []
            sum_floor = 0
            for deal_link in deal_links:
                ratio = _to_decimal(item_level_configs.get(deal_link.id, {}).get("allocated_ratio")) / Decimal("100")
                exact = Decimal(str(total_int)) * ratio
                floor_val = int(exact.to_integral_value(rounding=ROUND_FLOOR))
                frac = exact - Decimal(str(floor_val))
                floors[deal_link.id] = floor_val
                remainders.append((frac, deal_link.id))
                sum_floor += floor_val

            leftover = total_int - sum_floor
            remainders.sort(key=lambda item: (item[0], -item[1]), reverse=True)
            for idx in range(leftover):
                _, deal_link_id = remainders[idx % len(remainders)]
                floors[deal_link_id] = floors.get(deal_link_id, 0) + 1

            result_for_current[quote_id] = Decimal(str(floors.get(link.id, 0)))
            continue

        ratio = _to_decimal(current_cfg.get("allocated_ratio")) / Decimal("100")
        result_for_current[quote_id] = base_qty * ratio

    return result_for_current


def _build_allocated_qty_map(db: Session, link: InquirySupplier, quotes: List[Quotation]) -> dict:
    quote_rows = []
    total_base_qty = 0.0
    item_level_map = _parse_link_item_allocations(link)
    if item_level_map:
        for q in quotes:
            task_item = db.query(InquiryTaskItem).filter(InquiryTaskItem.id == q.item_id).first()
            req = db.query(InquiryRequest).filter(InquiryRequest.id == task_item.request_id).first() if task_item else None
            base_qty = float(req.qty if req and req.qty is not None else (q.qty or 0))
            item_cfg = item_level_map.get(int(task_item.id if task_item else q.item_id))
            if not item_cfg:
                quote_rows.append({"quote_id": q.id, "allocated_qty": 0.0})
                continue
            if item_cfg.get("allocated_qty") is not None:
                quote_rows.append({"quote_id": q.id, "allocated_qty": float(item_cfg["allocated_qty"] or 0)})
            else:
                ratio = float(item_cfg.get("allocated_ratio") or 0) / 100.0
                quote_rows.append({"quote_id": q.id, "allocated_qty": base_qty * ratio})
        return {row["quote_id"]: row["allocated_qty"] for row in quote_rows}

    for q in quotes:
        task_item = db.query(InquiryTaskItem).filter(InquiryTaskItem.id == q.item_id).first()
        req = db.query(InquiryRequest).filter(InquiryRequest.id == task_item.request_id).first() if task_item else None
        base_qty = float(req.qty if req and req.qty is not None else (q.qty or 0))
        quote_rows.append({"quote_id": q.id, "base_qty": base_qty})
        total_base_qty += base_qty

    if link.allocated_qty is not None:
        allocated_total_qty = float(link.allocated_qty or 0)
        if len(quote_rows) <= 1:
            return {quote_rows[0]["quote_id"]: allocated_total_qty} if quote_rows else {}
        if total_base_qty > 0:
            allocated_qty_map = {}
            allocated_so_far = 0.0
            for index, row in enumerate(quote_rows):
                if index == len(quote_rows) - 1:
                    allocated_qty_map[row["quote_id"]] = max(allocated_total_qty - allocated_so_far, 0.0)
                else:
                    qty = allocated_total_qty * row["base_qty"] / total_base_qty
                    allocated_qty_map[row["quote_id"]] = qty
                    allocated_so_far += qty
            return allocated_qty_map
        average_qty = allocated_total_qty / len(quote_rows)
        return {row["quote_id"]: average_qty for row in quote_rows}

    if link.allocated_ratio is not None:
        ratio = float(link.allocated_ratio or 0) / 100.0
        return {
            row["quote_id"]: row["base_qty"] * ratio
            for row in quote_rows
        }

    return {row["quote_id"]: row["base_qty"] for row in quote_rows}


def _calc_link_total_amount(db: Session, link: InquirySupplier) -> float:
    task = db.query(InquiryTask).filter(InquiryTask.id == link.task_id).first()
    quote_rows = _build_link_quote_rows(db, link)
    allocated_qty_map = _build_task_split_allocated_qty_map(task, quote_rows, link) if task else {}
    if not allocated_qty_map:
        allocated_qty_map = {
            quote_id: _to_decimal(qty)
            for quote_id, qty in _build_allocated_qty_map(db, link, [row["quote"] for row in quote_rows]).items()
        }

    total_amount = Decimal("0")
    for row in quote_rows:
        qty = allocated_qty_map.get(row["quote"].id, Decimal("0"))
        total_amount += _to_decimal(row["quote"].price) * qty
    return float(total_amount)


def _to_decimal(value) -> Decimal:
    if value is None:
        return Decimal("0")
    return Decimal(str(value))


def _format_decimal_number(value: Decimal) -> float | int:
    if value == value.to_integral_value():
        return int(value)
    return float(value)


def _build_task_split_allocated_qty_map(task: InquiryTask, quote_rows: list, link: InquirySupplier) -> dict:
    item_level_allocated_qty_map = _build_item_level_allocated_qty_map(task, quote_rows, link)
    if item_level_allocated_qty_map:
        return item_level_allocated_qty_map

    deal_links = [l for l in (task.suppliers or []) if l.status == LinkStatus.DEAL]
    if len(deal_links) <= 1:
        return {}

    ratios = {}
    for deal_link in deal_links:
        if deal_link.allocated_ratio is None:
            ratios[deal_link.id] = Decimal("0")
        else:
            ratios[deal_link.id] = _to_decimal(deal_link.allocated_ratio) / Decimal("100")

    result_for_current = {}
    current_ratio = ratios.get(link.id, Decimal("0"))
    for row in quote_rows:
        quote_id = row["quote"].id
        base_qty = row["base_qty"]
        if current_ratio <= 0:
            result_for_current[quote_id] = Decimal("0")
            continue
        if base_qty != base_qty.to_integral_value():
            result_for_current[quote_id] = base_qty * current_ratio
            continue

        total_int = int(base_qty)
        floors = {}
        remainders = []
        sum_floor = 0
        for deal_link in deal_links:
            exact = Decimal(str(total_int)) * ratios.get(deal_link.id, Decimal("0"))
            floor_val = int(exact.to_integral_value(rounding=ROUND_FLOOR))
            frac = exact - Decimal(str(floor_val))
            floors[deal_link.id] = floor_val
            remainders.append((frac, deal_link.id))
            sum_floor += floor_val

        leftover = total_int - sum_floor
        remainders.sort(key=lambda item: (item[0], -item[1]), reverse=True)
        for idx in range(leftover):
            _, deal_link_id = remainders[idx % len(remainders)]
            floors[deal_link_id] = floors.get(deal_link_id, 0) + 1

        result_for_current[quote_id] = Decimal(str(floors.get(link.id, 0)))

    return result_for_current


def _build_link_material_allocations(db: Session, task: InquiryTask, link: InquirySupplier) -> list:
    if link.status != LinkStatus.DEAL:
        return []

    quote_rows = _build_link_quote_rows(db, link)
    if not quote_rows:
        return []

    allocated_qty_map = _build_task_split_allocated_qty_map(task, quote_rows, link)
    if not allocated_qty_map:
        allocated_qty_map = {
            quote_id: _to_decimal(qty)
            for quote_id, qty in _build_allocated_qty_map(db, link, [row["quote"] for row in quote_rows]).items()
        }

    material_allocations = []
    for row in quote_rows:
        quote = row["quote"]
        request = row["request"]
        base_qty = row["base_qty"]
        allocated_qty = allocated_qty_map.get(quote.id, Decimal("0"))
        if allocated_qty <= 0:
            continue

        price = _to_decimal(quote.price)
        amount = allocated_qty * price
        allocated_ratio = (allocated_qty / base_qty * Decimal("100")) if base_qty > 0 else Decimal("0")
        material_allocations.append({
            "item_id": row["task_item"].id if row["task_item"] else None,
            "request_id": row["task_item"].request_id if row["task_item"] else None,
            "material_code": request.material_code if request else "",
            "material_name": request.material_name if request else "",
            "base_qty": _format_decimal_number(base_qty),
            "allocated_qty": _format_decimal_number(allocated_qty),
            "allocated_ratio": round(float(allocated_ratio), 2),
            "price": float(price),
            "amount": round(float(amount), 2),
            "delivery_date": quote.delivery_date,
        })

    return material_allocations


def _get_task_total_requested_qty(task: InquiryTask) -> float:
    total_qty = 0.0
    for item in task.items:
        if item.request and item.request.qty is not None:
            total_qty += float(item.request.qty)
    return total_qty


def _build_auto_compare_meta(task: InquiryTask) -> dict:
    meta = {
        "compare_ready": False,
        "compare_ready_reason": None,
        "effective_status": task.status,
    }
    if task.type != "auto":
        return meta

    if task.status == TaskStatus.AWAITING_AWARD:
        meta["compare_ready"] = True
        meta["compare_ready_reason"] = "awaiting_award"
        meta["effective_status"] = TaskStatus.AWAITING_AWARD
        return meta

    if task.status != TaskStatus.ACTIVE:
        return meta

    strategy = task.strategy_config or {}
    try:
        max_rounds = int(strategy.get("max_rounds") or 0)
    except (TypeError, ValueError):
        max_rounds = 0
    if max_rounds <= 0:
        return meta

    active_links = [
        link for link in (task.suppliers or [])
        if link.status not in [LinkStatus.REJECT, LinkStatus.DEAL, LinkStatus.LOCKED]
    ]
    if not active_links:
        if any(link.status == LinkStatus.LOCKED for link in (task.suppliers or [])):
            meta["compare_ready"] = True
            meta["compare_ready_reason"] = "all_candidates_locked"
            meta["effective_status"] = TaskStatus.AWAITING_AWARD
        return meta

    if any(link.status in [LinkStatus.SENT, LinkStatus.NEGOTIATION] for link in active_links):
        return meta

    if all(int(link.current_round or 0) >= max_rounds for link in active_links):
        meta["compare_ready"] = True
        meta["compare_ready_reason"] = "max_rounds_reached"
        meta["effective_status"] = TaskStatus.AWAITING_AWARD

    return meta


def _normalize_close_allocations(
    task: InquiryTask,
    payload: Optional[TaskClosePayload],
    selected_link_id: Optional[int]
) -> List[dict]:
    if payload and payload.allocations:
        raw_allocations = payload.allocations
    elif selected_link_id is not None:
        raw_allocations = [{"link_id": selected_link_id, "allocated_ratio": 100.0, "allocated_qty": None}]
    else:
        raw_allocations = []

    task_link_map = {link.id: link for link in task.suppliers}
    task_item_map = {item.id: item for item in task.items}
    task_total_qty = _get_task_total_requested_qty(task)
    normalized_allocations = []
    seen_link_ids = set()
    effective_total_qty = 0.0
    has_item_level_allocations = False
    item_total_ratio_map = {item.id: 0.0 for item in task.items}
    item_total_qty_map = {item.id: 0.0 for item in task.items}
    item_allocation_mode_map = {item.id: None for item in task.items}

    for allocation in raw_allocations:
        link_id = allocation["link_id"] if isinstance(allocation, dict) else allocation.link_id
        allocated_ratio = allocation.get("allocated_ratio") if isinstance(allocation, dict) else allocation.allocated_ratio
        allocated_qty = allocation.get("allocated_qty") if isinstance(allocation, dict) else allocation.allocated_qty
        item_allocations = allocation.get("item_allocations") if isinstance(allocation, dict) else getattr(allocation, "item_allocations", None)

        if link_id in seen_link_ids:
            raise HTTPException(status_code=400, detail=f"Duplicate allocation for link_id={link_id}")
        if link_id not in task_link_map:
            raise HTTPException(status_code=404, detail=f"Supplier link {link_id} not found in this task")
        normalized_item_allocations = []

        if item_allocations:
            has_item_level_allocations = True
            if allocated_ratio is not None or allocated_qty is not None:
                raise HTTPException(status_code=400, detail=f"Allocation for link_id={link_id} cannot mix task-level and item-level values")
            for item_allocation in item_allocations:
                item_id = item_allocation.get("item_id") if isinstance(item_allocation, dict) else item_allocation.item_id
                item_ratio = item_allocation.get("allocated_ratio") if isinstance(item_allocation, dict) else item_allocation.allocated_ratio
                item_qty = item_allocation.get("allocated_qty") if isinstance(item_allocation, dict) else item_allocation.allocated_qty

                if item_id not in task_item_map:
                    raise HTTPException(status_code=404, detail=f"Task item {item_id} not found in this task")
                if item_ratio is None and item_qty is None:
                    raise HTTPException(status_code=400, detail=f"Item allocation for item_id={item_id} must provide ratio or quantity")
                if item_ratio is not None and item_qty is not None:
                    raise HTTPException(status_code=400, detail=f"Item allocation for item_id={item_id} cannot provide both ratio and quantity")
                if item_ratio is not None and item_ratio <= 0:
                    raise HTTPException(status_code=400, detail=f"Item allocation ratio for item_id={item_id} must be greater than 0")
                if item_qty is not None and item_qty <= 0:
                    raise HTTPException(status_code=400, detail=f"Item allocation quantity for item_id={item_id} must be greater than 0")

                current_mode = item_allocation_mode_map[item_id]
                next_mode = "qty" if item_qty is not None else "ratio"
                if current_mode and current_mode != next_mode:
                    raise HTTPException(status_code=400, detail=f"Item {item_id} allocation mode must be consistent across suppliers")
                item_allocation_mode_map[item_id] = next_mode

                if item_qty is not None:
                    item_total_qty_map[item_id] += float(item_qty)
                    effective_total_qty += float(item_qty)
                else:
                    item_total_ratio_map[item_id] += float(item_ratio)
                    base_qty = float(task_item_map[item_id].request.qty or 0) if task_item_map[item_id].request else 0.0
                    effective_total_qty += base_qty * float(item_ratio) / 100.0

                normalized_item_allocations.append({
                    "item_id": int(item_id),
                    "allocated_ratio": float(item_ratio) if item_ratio is not None else None,
                    "allocated_qty": float(item_qty) if item_qty is not None else None,
                })
        else:
            if allocated_ratio is None and allocated_qty is None:
                raise HTTPException(status_code=400, detail=f"Allocation for link_id={link_id} must provide ratio or quantity")
            if allocated_ratio is not None and allocated_qty is not None:
                raise HTTPException(status_code=400, detail=f"Allocation for link_id={link_id} cannot provide both ratio and quantity")
            if allocated_ratio is not None and allocated_ratio <= 0:
                raise HTTPException(status_code=400, detail=f"Allocation ratio for link_id={link_id} must be greater than 0")
            if allocated_qty is not None and allocated_qty <= 0:
                raise HTTPException(status_code=400, detail=f"Allocation quantity for link_id={link_id} must be greater than 0")

            effective_qty = float(allocated_qty) if allocated_qty is not None else (
                task_total_qty * float(allocated_ratio) / 100.0 if task_total_qty > 0 else 0.0
            )
            effective_total_qty += effective_qty
        seen_link_ids.add(link_id)
        normalized_allocations.append({
            "link_id": link_id,
            "allocated_ratio": float(allocated_ratio) if allocated_ratio is not None else None,
            "allocated_qty": float(allocated_qty) if allocated_qty is not None else None,
            "item_allocations": normalized_item_allocations,
        })

    if has_item_level_allocations:
        for item in task.items:
            item_id = item.id
            request_qty = float(item.request.qty or 0) if item.request else 0.0
            mode = item_allocation_mode_map[item_id]
            if mode == "ratio":
                if abs(item_total_ratio_map[item_id] - 100.0) > 1e-6:
                    raise HTTPException(status_code=400, detail=f"Item {item.request.material_name if item.request else item_id} allocation ratio must total 100%")
            elif mode == "qty":
                if request_qty > 0 and abs(item_total_qty_map[item_id] - request_qty) > 1e-6:
                    raise HTTPException(status_code=400, detail=f"Item {item.request.material_name if item.request else item_id} allocation quantity must equal requested quantity")
            else:
                raise HTTPException(status_code=400, detail=f"Item {item.request.material_name if item.request else item_id} has no allocation result")
    elif task_total_qty > 0 and effective_total_qty - task_total_qty > 1e-6:
        raise HTTPException(status_code=400, detail="Allocated quantity exceeds task requested quantity")

    return normalized_allocations


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise credentials_exception
    return user

@router.post("/tasks", response_model=InquiryTaskSchema)
def create_inquiry_task(
    task_in: InquiryTaskCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    创建询价任务：
    1. 接收原始需求列表（raw_requests）
    2. 将这些需求持久化到数据库（如果尚未存在）
    3. 创建任务并关联这些需求
    """
    request_ids = []
    raw_request_supplier_ids_by_erp_id = {}
    task_level_supplier_ids = set(int(sid) for sid in (getattr(task_in, "supplier_ids", None) or []) if sid)
    
    # 1. 处理原始需求数据（如果提供）
    if task_in.raw_requests:
        for raw_req in task_in.raw_requests:
            raw_supplier_ids = []
            for supplier_id in (getattr(raw_req, "supplier_ids", None) or []):
                try:
                    supplier_id_int = int(supplier_id)
                except (TypeError, ValueError):
                    continue
                raw_supplier_ids.append(supplier_id_int)
                task_level_supplier_ids.add(supplier_id_int)
            raw_request_supplier_ids_by_erp_id[str(raw_req.erp_request_id)] = raw_supplier_ids
            # 检查是否存在
            existing = db.query(InquiryRequest).filter(
                InquiryRequest.erp_request_id == raw_req.erp_request_id
            ).first()
            
            if existing:
                # 更新状态
                if existing.status == InquiryStatus.PENDING_POOL:
                    existing.status = InquiryStatus.IN_PROCESS
                # 更新期望价格（如果提供）
                if getattr(raw_req, 'target_price', None) is not None:
                    existing.target_price = raw_req.target_price
                if getattr(raw_req, 'material_model', None) is not None:
                    existing.material_model = raw_req.material_model
                request_ids.append(existing.id)
            else:
                # 创建新记录
                new_req = InquiryRequest(
                    erp_request_id=raw_req.erp_request_id,
                    bill_no=raw_req.bill_no,
                    project_info=raw_req.project_info,
                    material_code=raw_req.material_code,
                    material_name=raw_req.material_name,
                    material_model=getattr(raw_req, 'material_model', None),
                    qty=raw_req.qty,
                    target_price=getattr(raw_req, 'target_price', None),
                    delivery_date=raw_req.delivery_date,
                    status=InquiryStatus.IN_PROCESS
                )
                db.add(new_req)
                db.flush()
                request_ids.append(new_req.id)
    
    # 兼容旧逻辑：如果直接传了 request_ids
    if task_in.request_ids:
        for rid in task_in.request_ids:
            if rid not in request_ids:
                request_ids.append(rid)
    
    if not request_ids:
        raise HTTPException(status_code=400, detail="No valid requests provided")

    # 兼容历史数据库：确保任务表和供应商关联表新增字段已补齐
    ensure_runtime_schema_columns()

    # 2. 创建任务
    strategy_config = dict(task_in.strategy_config.dict()) if task_in.strategy_config else {}
    item_supplier_map = {}
    new_task = InquiryTask(
        title=task_in.title,
        type=task_in.type,
        strategy_config=strategy_config,
        deadline=task_in.deadline,
        status=TaskStatus.PENDING_FILL if task_in.type == "manual" else TaskStatus.ACTIVE,
        buyer_id=current_user.id,
        created_by=current_user.id
    )
    db.add(new_task)
    db.flush()

    # 3. 创建关联项
    for rid in request_ids:
        # 确保请求状态已更新（对于仅传ID的情况）
        req = db.query(InquiryRequest).get(rid)
        if req:
            if req.status == InquiryStatus.PENDING_POOL:
                req.status = InquiryStatus.IN_PROCESS
            
            # 如果在 task_in 的 raw_requests 中找到了对应的目标价格，更新它
            if task_in.raw_requests:
                for raw_req in task_in.raw_requests:
                    if (getattr(raw_req, 'id', None) == rid) or (raw_req.erp_request_id == req.erp_request_id):
                        if getattr(raw_req, 'target_price', None) is not None:
                            req.target_price = raw_req.target_price
                        if getattr(raw_req, 'qty', None) is not None:
                            req.qty = raw_req.qty
                        if getattr(raw_req, 'delivery_date', None) is not None:
                            req.delivery_date = raw_req.delivery_date
                        break
            
        item = InquiryTaskItem(
            task_id=new_task.id,
            request_id=rid
        )
        db.add(item)
        db.flush()

        if req:
            supplier_ids_for_item = raw_request_supplier_ids_by_erp_id.get(str(req.erp_request_id), [])
            if supplier_ids_for_item:
                item_supplier_map[str(item.id)] = supplier_ids_for_item
    
    # 4. 如果传了供应商ID，自动创建关联
    if item_supplier_map:
        new_task.strategy_config = {
            **(new_task.strategy_config or {}),
            "item_supplier_map": item_supplier_map
        }

    if task_level_supplier_ids:
        for sup_id in sorted(task_level_supplier_ids):
            supplier = db.query(Supplier).get(sup_id)
            if supplier:
                link = InquirySupplier(
                    task_id=new_task.id,
                    supplier_id=supplier.id,
                    status=LinkStatus.SENT
                )
                db.add(link)

    db.commit()
    db.refresh(new_task)
    
    from routers.system import log_operation
    log_operation(db, current_user.id, "CREATE_INQUIRY", f"创建了询价单: {new_task.title}")
    
    return new_task

@router.post("/tasks/{task_id}/suppliers")
def add_supplier_to_task(
    task_id: int,
    supplier_name: str,
    contact_person: str = None,
    phone: str = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    为询价任务添加供应商
    """
    task = db.query(InquiryTask).filter(InquiryTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # 1. 查找或创建供应商
    supplier = db.query(Supplier).filter(Supplier.name == supplier_name).first()
    if not supplier:
        supplier = Supplier(
            name=supplier_name,
            contact_person=contact_person,
            phone=phone
        )
        db.add(supplier)
        db.flush()

    # 2. 检查是否已经添加
    existing_link = db.query(InquirySupplier).filter(
        InquirySupplier.task_id == task_id,
        InquirySupplier.supplier_id == supplier.id
    ).first()
    if existing_link:
        raise HTTPException(status_code=400, detail="Supplier already added to this task")

    # 3. 创建关联
    new_link = InquirySupplier(
        task_id=task.id,
        supplier_id=supplier.id,
        status=LinkStatus.SENT
    )
    db.add(new_link)
    db.commit()
    
    return {
        "message": "Supplier added successfully",
        "link_id": new_link.id,
        "supplier_id": supplier.id,
        "supplier_name": supplier.name,
        "supplier_code": supplier.code,
        "supplier_grade": supplier.grade
    }

@router.get("/tasks")
def get_my_tasks(
    skip: int = 0,
    limit: int = 100,
    type: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    获取询价任务列表
    如果是 admin，获取所有；如果是 buyer，只获取自己负责的
    可以根据 type(auto/manual) 过滤
    """
    query = db.query(InquiryTask)
    if current_user.role == "buyer":
        query = query.filter(InquiryTask.buyer_id == current_user.id)
    if type:
        query = query.filter(InquiryTask.type == type)
    
    tasks = query.order_by(InquiryTask.id.desc()).offset(skip).limit(limit).all()
    
    result = []
    for task in tasks:
        compare_meta = _build_auto_compare_meta(task)
        task_dict = {
            "id": task.id,
            "title": task.title,
            "type": task.type,
            "status": task.status,
            "effective_status": compare_meta["effective_status"],
            "compare_ready": compare_meta["compare_ready"],
            "compare_ready_reason": compare_meta["compare_ready_reason"],
            "deadline": task.deadline,
            "created_at": task.created_at,
            "buyer_id": task.buyer_id,
            "buyer_name": task.buyer.username if task.buyer else None
        }
        result.append(task_dict)
    
    return result



@router.get("/tasks/{task_id}/details")
def get_task_details(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    获取任务的详细信息，包含需求项、供应商链接、以及每轮报价
    """
    task = db.query(InquiryTask).filter(InquiryTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    compare_meta = _build_auto_compare_meta(task)

    items = []
    for item in task.items:
        items.append({
            "id": item.id,
            "material_name": item.request.material_name,
            "material_code": item.request.material_code,
            "qty": item.request.qty,
            "target_price": item.request.target_price,
            "delivery_date": item.request.delivery_date
        })

    # 建立任务明细项(item_id)到期望单价(target_price)的映射
    target_price_map = {item.id: item.request.target_price for item in task.items if item.request.target_price is not None}

    today = datetime.now().date()
    score_input = []
    for link in task.suppliers:
        if link.status == LinkStatus.REJECT:
            continue
        current_round_quotes = [q for q in link.quotations if q.round == link.current_round]
        score_items = []
        for q in current_round_quotes:
            delivery_days = 0.0
            if isinstance(q.delivery_date, (datetime, date)):
                d_date = q.delivery_date.date() if isinstance(q.delivery_date, datetime) else q.delivery_date
                delivery_days = float((d_date - today).days)
                if delivery_days < 0:
                    delivery_days = 0.0
            elif q.delivery_date is not None:
                try:
                    delivery_days = float(q.delivery_date)
                    if delivery_days < 0:
                        delivery_days = 0.0
                except (TypeError, ValueError):
                    delivery_days = 0.0
            score_items.append({
                "price": float(q.price or 0),
                "qty": float(q.qty or 0),
                "delivery_days": delivery_days,
            })
        score_input.append({
            "supplier_id": link.id,
            "items": score_items,
        })

    score_rows = calculate_supplier_scores(score_input)
    score_map = {row.get("supplier_id"): row for row in score_rows}
    # 按照 1.综合得分(降序) 2.总价(升序) 3.交期(升序) 进行多级排序
    rank_candidates = sorted(
        score_rows,
        key=lambda row: (
            float(row.get("total_score", 0)),
            -float(row.get("total_price", 0)),
            -float(row.get("avg_delivery_days", 0))
        ),
        reverse=True
    )

    rank_map = {}
    for i, row in enumerate(rank_candidates):
        if i > 0:
            prev_row = rank_candidates[i - 1]
            # 如果三项核心指标完全一致，则赋予完全相同的名次（并列）
            if (float(row.get("total_score", 0)) == float(prev_row.get("total_score", 0)) and
                float(row.get("total_price", 0)) == float(prev_row.get("total_price", 0)) and
                float(row.get("avg_delivery_days", 0)) == float(prev_row.get("avg_delivery_days", 0))):
                rank_map[row.get("supplier_id")] = rank_map[prev_row.get("supplier_id")]
                continue
        # 否则按当前所处位置赋予标准名次（例如若有并列第一，下一个就是第三名）
        rank_map[row.get("supplier_id")] = i + 1

    links = []
    for link in task.suppliers:
        quotes_by_round = {}
        for q in link.quotations:
            if q.round not in quotes_by_round:
                quotes_by_round[q.round] = []
            
            target_p = target_price_map.get(q.item_id)
            is_anomaly = False
            anomaly_reason = ""
            
            # 完全以期望单价作为唯一基准进行异常检测
            if target_p is not None and target_p > 0:
                if q.price <= target_p * 0.5:
                    is_anomaly = True
                    anomaly_reason = "异常低价：低于期望单价 50% 以上，存在错报风险"
                elif q.price >= target_p * 1.5:
                    is_anomaly = True
                    anomaly_reason = "异常高价：大幅偏离期望单价，请警惕溢价风险"
            quotes_by_round[q.round].append({
                "item_id": q.item_id,
                "qty": q.qty,
                "price": q.price,
                "delivery_date": q.delivery_date,
                "remark": q.remark,
                "is_anomaly": is_anomaly,
                "anomaly_reason": anomaly_reason
            })

        score_info = score_map.get(link.id, {})
        material_allocations = _build_link_material_allocations(db, task, link)
        
        grade = "一般"
        if getattr(link.supplier, 'grade', None):
            grade = link.supplier.grade
        elif getattr(link.supplier, 'level', None) == 'core':
            grade = 'A级'
            
        links.append({
            "link_id": link.id,
            "supplier_id": link.supplier.id,
            "supplier_name": link.supplier.name,
            "supplier_code": link.supplier.code,
            "supplier_grade": grade,
            "status": link.status,
            "allocated_ratio": link.allocated_ratio,
            "allocated_qty": link.allocated_qty,
            "item_allocations": link.item_allocations or [],
            "material_allocations": material_allocations,
            "current_round": link.current_round,
            "quotes": quotes_by_round,
            "total_price": float(score_info.get("total_price", 0)),
            "avg_delivery_days": float(score_info.get("avg_delivery_days", 0)),
            "price_score": float(score_info.get("price_score", 0)),
            "delivery_score": float(score_info.get("delivery_score", 0)),
            "total_score": float(score_info.get("total_score", 0)),
            "score_rank": rank_map.get(link.id)
        })

    return {
        "id": task.id,
        "title": task.title,
        "type": task.type,
        "deadline": task.deadline,
        "status": task.status,
        "effective_status": compare_meta["effective_status"],
        "compare_ready": compare_meta["compare_ready"],
        "compare_ready_reason": compare_meta["compare_ready_reason"],
        "strategy_config": task.strategy_config,
        "items": items,
        "links": links
    }

@router.delete("/tasks/{task_id}")
def delete_inquiry_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    删除已关闭的询价任务
    """
    task = db.query(InquiryTask).filter(InquiryTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
        
    if task.status != TaskStatus.CLOSED:
        raise HTTPException(status_code=400, detail="Only closed tasks can be deleted")

    # === 新增：先删除关联的电子合同记录 ===
    from models import Quotation, Contract
    db.query(Contract).filter(Contract.task_id == task_id).delete()

    # 先删除相关的报价记录和供应商关联
    for link in task.suppliers:
        # 删除相关的 quotations
        db.query(Quotation).filter(Quotation.inquiry_supplier_id == link.id).delete()
        db.delete(link)
        
    # 删除相关的 task items
    for item in task.items:
        # 将关联的需求池状态重置
        if item.request:
            item.request.status = InquiryStatus.PENDING_POOL
        db.delete(item)
        
    # 删除任务本身
    db.delete(task)
    db.commit()
    return {"message": "Task deleted successfully"}
@router.put("/tasks/{task_id}/status")
def update_task_status(
    task_id: int,
    status: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    更新任务状态（主要用于手动询价状态流转）
    """
    task = db.query(InquiryTask).filter(InquiryTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
        
    task.status = status
    db.commit()
    return {"message": "Status updated successfully"}

class ManualQuoteItem(BaseModel):
    supplier_code: str
    supplier_name: str
    price: float
    tax_net_price: Optional[float] = None
    qty: float

class ManualQuotePayload(BaseModel):
    material_code: str
    suppliers: List[ManualQuoteItem]


class CompareDraftPayload(BaseModel):
    material_code: str
    material_name: Optional[str] = None
    supplier_count: int = 0
    task_title: Optional[str] = None

@router.post("/tasks/{task_id}/save-manual-quotes")
def save_manual_quotes(
    task_id: int,
    payload: ManualQuotePayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    保存手动询价的报价数据
    """
    task = db.query(InquiryTask).filter(InquiryTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # 找到对应的 task item
    item = db.query(InquiryTaskItem).join(InquiryRequest).filter(
        InquiryTaskItem.task_id == task_id,
        InquiryRequest.material_code == payload.material_code
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Material not found in this task")

    for supp in payload.suppliers:
        # 1. 查找或创建供应商
        supplier = db.query(Supplier).filter(Supplier.code == supp.supplier_code).first()
        if not supplier:
            supplier = db.query(Supplier).filter(Supplier.name == supp.supplier_name).first()
        if not supplier:
            supplier = Supplier(code=supp.supplier_code, name=supp.supplier_name)
            db.add(supplier)
            db.flush()

        # 2. 查找或创建关联 (InquirySupplier)
        link = db.query(InquirySupplier).filter(
            InquirySupplier.task_id == task_id,
            InquirySupplier.supplier_id == supplier.id
        ).first()
        if not link:
            link = InquirySupplier(task_id=task_id, supplier_id=supplier.id, status=LinkStatus.QUOTED)
            db.add(link)
            db.flush()
        else:
            link.status = LinkStatus.QUOTED
        target_round = int(link.current_round or 1)

        # 3. 查找或创建报价记录
        quote = db.query(Quotation).filter(
            Quotation.inquiry_supplier_id == link.id,
            Quotation.item_id == item.id,
            Quotation.round == target_round
        ).first()
        
        if quote:
            quote.price = supp.price
            quote.qty = supp.qty
        else:
            quote = Quotation(
                inquiry_supplier_id=link.id,
                item_id=item.id,
                round=target_round,
                price=supp.price,
                qty=supp.qty
            )
            db.add(quote)
            
    db.commit()
    return {"message": "Quotes saved successfully"}


@router.post("/tasks/{task_id}/compare-draft")
def upsert_compare_draft(
    task_id: int,
    payload: CompareDraftPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    保存/更新智能比价草稿（服务端持久化，多端共享）
    """
    task = db.query(InquiryTask).filter(InquiryTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    draft = db.query(CompareDraft).filter(
        CompareDraft.task_id == task_id,
        CompareDraft.buyer_id == current_user.id,
        CompareDraft.material_code == payload.material_code
    ).first()

    if not draft:
        draft = CompareDraft(
            task_id=task_id,
            buyer_id=current_user.id,
            material_code=payload.material_code
        )
        db.add(draft)

    draft.task_title = payload.task_title or task.title
    draft.material_name = payload.material_name
    draft.supplier_count = max(int(payload.supplier_count or 0), 0)
    draft.updated_at = datetime.now()

    db.commit()
    db.refresh(draft)
    return {
        "id": draft.id,
        "task_id": draft.task_id,
        "task_title": draft.task_title,
        "material_code": draft.material_code,
        "material_name": draft.material_name,
        "supplier_count": draft.supplier_count,
        "updated_at": draft.updated_at
    }


@router.get("/compare-drafts")
def get_compare_drafts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    获取当前采购员的智能比价草稿列表
    """
    query = db.query(CompareDraft)
    if current_user.role != "admin":
        query = query.filter(CompareDraft.buyer_id == current_user.id)
    drafts = query.order_by(CompareDraft.updated_at.desc(), CompareDraft.id.desc()).all()
    return [
        {
            "id": d.id,
            "task_id": d.task_id,
            "task_title": d.task_title,
            "material_code": d.material_code,
            "material_name": d.material_name,
            "supplier_count": d.supplier_count,
            "updated_at": d.updated_at
        }
        for d in drafts
    ]


@router.delete("/compare-drafts/{draft_id}")
def delete_compare_draft(
    draft_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    draft = db.query(CompareDraft).filter(CompareDraft.id == draft_id).first()
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    if current_user.role != "admin" and draft.buyer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    db.delete(draft)
    db.commit()
    return {"message": "Draft deleted successfully"}


@router.delete("/compare-drafts/by-task/{task_id}")
def delete_compare_drafts_by_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    query = db.query(CompareDraft).filter(CompareDraft.task_id == task_id)
    if current_user.role != "admin":
        query = query.filter(CompareDraft.buyer_id == current_user.id)

    deleted = query.delete()
    db.commit()
    return {"message": "Drafts deleted successfully", "deleted_count": deleted}

@router.post("/tasks/{task_id}/close")
def close_inquiry_task(
    task_id: int,
    payload: Optional[TaskClosePayload] = Body(default=None),
    selected_link_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    手动关闭询价任务，支持单供应商整单中标或多供应商拆单中标。
    兼容旧逻辑：如果仍通过 selected_link_id 传参，则按 100% 分配处理。
    """
    task = db.query(InquiryTask).filter(InquiryTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    normalized_allocations = _normalize_close_allocations(task, payload, selected_link_id)
    allocation_map = {allocation["link_id"]: allocation for allocation in normalized_allocations}
    task_total_qty = _get_task_total_requested_qty(task)
    task_item_map = {item.id: item for item in task.items}

    task.status = TaskStatus.CLOSED
    for link in task.suppliers:
        allocation = allocation_map.get(link.id)
        if allocation:
            link.status = LinkStatus.DEAL
            if allocation.get("item_allocations"):
                allocated_total_qty = 0.0
                for item_allocation in allocation["item_allocations"]:
                    task_item = task_item_map.get(item_allocation["item_id"])
                    base_qty = float(task_item.request.qty or 0) if task_item and task_item.request else 0.0
                    if item_allocation["allocated_qty"] is not None:
                        allocated_total_qty += float(item_allocation["allocated_qty"] or 0)
                    else:
                        allocated_total_qty += base_qty * float(item_allocation["allocated_ratio"] or 0) / 100.0
                link.allocated_qty = allocated_total_qty
                link.allocated_ratio = (
                    allocated_total_qty / task_total_qty * 100.0
                    if task_total_qty > 0 else None
                )
                link.item_allocations = allocation["item_allocations"]
            elif allocation["allocated_ratio"] is not None:
                link.allocated_ratio = allocation["allocated_ratio"]
                link.allocated_qty = (
                    task_total_qty * allocation["allocated_ratio"] / 100.0
                    if task_total_qty > 0 else None
                )
                link.item_allocations = None
            else:
                link.allocated_qty = allocation["allocated_qty"]
                link.allocated_ratio = (
                    allocation["allocated_qty"] / task_total_qty * 100.0
                    if task_total_qty > 0 else None
                )
                link.item_allocations = None
            link.latest_ai_feedback = "恭喜，采购员已确认您中标，本次询价已达成合作。"
        else:
            link.status = LinkStatus.REJECT
            link.allocated_ratio = None
            link.allocated_qty = None
            link.item_allocations = None
            if not allocation_map:
                link.latest_ai_feedback = "本次询价任务已终止（流标），所有报价已作废，感谢您的参与。"
            else:
                link.latest_ai_feedback = "很遗憾，采购员最终选择了其他供应商，本次询价已结束。"
            contract_record = db.query(Contract).filter(
                Contract.inquiry_supplier_id == link.id
            ).first()
            if contract_record:
                db.delete(contract_record)

    if allocation_map:
        active_template = db.query(ContractTemplate).filter(
            ContractTemplate.is_active == True
        ).order_by(ContractTemplate.id.desc()).first()
        for link in task.suppliers:
            if link.status != LinkStatus.DEAL:
                continue
            total_amount = _calc_link_total_amount(db, link)
            contract_record = db.query(Contract).filter(
                Contract.inquiry_supplier_id == link.id
            ).first()
            if not contract_record:
                contract_record = Contract(
                    task_id=task.id,
                    inquiry_supplier_id=link.id,
                    status="待供应商填写"
                )
            contract_record.total_amount = total_amount
            if active_template and active_template.default_buyer_name and not contract_record.buyer_company_name:
                contract_record.buyer_company_name = active_template.default_buyer_name
            db.add(contract_record)

    db.commit()
    return {
        "message": "Task closed successfully.",
        "deal_link_ids": sorted(allocation_map.keys()),
        "is_split_award": len(allocation_map) > 1
    }

@router.post("/tasks/{task_id}/links/{link_id}/manual-continue")
def manual_continue_negotiation(
    task_id: int,
    link_id: int,
    payload: ManualInterventionPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    if current_user.role not in ["admin", "buyer"]:
        raise HTTPException(status_code=403, detail="Not authorized")

    task = db.query(InquiryTask).filter(InquiryTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    link = db.query(InquirySupplier).filter(
        InquirySupplier.id == link_id,
        InquirySupplier.task_id == task_id
    ).first()
    if not link:
        raise HTTPException(status_code=404, detail="Supplier link not found")

    if task.status != TaskStatus.ACTIVE:
        raise HTTPException(status_code=400, detail="Task is not active")

    link.status = LinkStatus.NEGOTIATION
    link.latest_ai_feedback = payload.message or "采购员已人工复核报价，请基于目标区间重新提交报价。"
    db.commit()
    return {"message": "已人工确认，供应商可继续谈判。"}

@router.post("/tasks/{task_id}/links/{link_id}/manual-reject")
def manual_reject_link(
    task_id: int,
    link_id: int,
    payload: ManualInterventionPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    if current_user.role not in ["admin", "buyer"]:
        raise HTTPException(status_code=403, detail="Not authorized")

    task = db.query(InquiryTask).filter(InquiryTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    link = db.query(InquirySupplier).filter(
        InquirySupplier.id == link_id,
        InquirySupplier.task_id == task_id
    ).first()
    if not link:
        raise HTTPException(status_code=404, detail="Supplier link not found")

    link.status = LinkStatus.REJECT
    link.latest_ai_feedback = payload.message or "经采购员人工复核，当前报价不满足要求，本轮已终止。"
    db.commit()
    return {"message": "已人工淘汰该供应商。"}
