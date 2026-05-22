from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, extract
from typing import Any
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
import asyncio

from models import (
    get_db, SessionLocal, InquirySupplier, InquiryTaskItem,
    Quotation, LinkStatus, InquiryRequest, TaskStatus, InquiryTask, Supplier, SupplierMember, User, Contract, SupplierMetric, PurchaseOrderHistory
)
from schemas_supplier import (
    QuoteSubmission,
    SupplierQuoteResponse,
    SupplierUpdate,
    SupplierContractInfoSubmit,
    SupplierCreatePayload,
    SupplierAccountUpdatePayload,
    SupplierChangePasswordPayload,
    SupplierProfileUpdatePayload,
)
from services.contract_service import generate_contract_pdf
from services.negotiation_service import calculate_bargain_feedback, calculate_supplier_scores
from services.supplier_access import get_supplier_context_for_portal, get_supplier_context_for_user
import logging
from routers.inquiry import get_current_user
from core.security import get_password_hash
from core.redis_client import cache_get, cache_set, cache_delete, cache_clear_pattern

logger = logging.getLogger(__name__)

router = APIRouter()
BASE_DIR = Path(__file__).resolve().parents[1]
SUPPLIER_SURVEY_TEMPLATE_PATH = BASE_DIR.parent / "供应商评价" / "俊郎电气供应商调查表.doc"


def _require_admin_or_buyer(current_user: User) -> None:
    if current_user.role not in ["admin", "buyer", "buyer_manager"]:
        raise HTTPException(status_code=403, detail="Not authorized")


def _get_supplier_context(db: Session, current_user: User) -> tuple[Supplier, SupplierMember]:
    return get_supplier_context_for_user(db, current_user)


def _get_supplier_portal_context(db: Session, current_user: User) -> tuple[Supplier, SupplierMember]:
    return get_supplier_context_for_portal(db, current_user)


def _invalidate_supplier_cache():
    """清除供应商相关所有缓存"""
    try:
        cache_clear_pattern("supplier:*")
    except Exception:
        pass


def _get_allowed_task_items_for_supplier(task: InquiryTask, link: InquirySupplier) -> list[InquiryTaskItem]:
    item_supplier_map = (task.strategy_config or {}).get("item_supplier_map") or {}
    supplier_id = int(link.supplier_id)
    allowed_items = []

    for item in (task.items or []):
        has_quote = any(q.item_id == item.id for q in (link.quotations or []))
        has_allocation = any(
            int(allocation.get("item_id") or 0) == int(item.id)
            for allocation in (link.item_allocations or [])
            if isinstance(allocation, dict)
        )

        supplier_ids = item_supplier_map.get(str(item.id))
        if isinstance(supplier_ids, list) and supplier_ids:
            normalized_ids = set()
            for raw_supplier_id in supplier_ids:
                try:
                    normalized_ids.add(int(raw_supplier_id))
                except (TypeError, ValueError):
                    continue
            if supplier_id in normalized_ids:
                allowed_items.append(item)
            elif has_quote or has_allocation:
                # 兼容旧任务/历史任务：即便映射缺失，只要该供应商确实报过该物料或有分配记录，仍允许查看自身物料明细
                allowed_items.append(item)
            continue

        if has_quote or has_allocation or not item_supplier_map:
            allowed_items.append(item)

    return allowed_items


def _get_task_attachments(task: InquiryTask) -> list[dict]:
    strategy = task.strategy_config or {}
    attachments = strategy.get("attachments") or []
    normalized_attachments = []
    for item in attachments:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or item.get("filename") or "").strip()
        file_path = str(item.get("file_path") or "").strip()
        if not name or not file_path:
            continue
        preview_file_path = str(item.get("preview_file_path") or "").strip() or None
        if not preview_file_path:
            file_path_obj = Path(file_path)
            relative_path = file_path_obj.as_posix().lstrip("/")
            source_path = Path(__file__).resolve().parents[1] / relative_path
            preview_candidate = source_path.parent / "preview" / f"{source_path.stem}_preview.pdf"
            if preview_candidate.exists():
                preview_file_path = f"/{preview_candidate.relative_to(Path(__file__).resolve().parents[1]).as_posix()}"

        normalized_attachments.append({
            "name": name,
            "file_path": file_path,
            "preview_file_path": preview_file_path,
            "size": item.get("size"),
            "uploaded_at": item.get("uploaded_at")
        })
    return normalized_attachments


def _generate_contract_pdf_background(inquiry_id: int) -> None:
    db = SessionLocal()
    try:
        asyncio.run(generate_contract_pdf(db, inquiry_id))
    except Exception:
        logger.exception("合同生成失败, inquiry_id=%s", inquiry_id)
        try:
            contract_record = db.query(Contract).filter(Contract.inquiry_supplier_id == inquiry_id).first()
            if contract_record:
                contract_record.status = "failed"
                db.add(contract_record)
                db.commit()
        except Exception:
            logger.exception("更新合同失败状态失败, inquiry_id=%s", inquiry_id)
    finally:
        db.close()

@router.get("/{supplier_id}/analysis")
def get_supplier_analysis(
    supplier_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    采购员获取单个供应商的综合数据画像 (基于真实ERP历史采购订单)
    """
    if current_user.role not in ["admin", "buyer"]:
        raise HTTPException(status_code=403, detail="Not authorized")

    supplier = db.query(Supplier).filter(Supplier.id == supplier_id).first()
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
        
    if not supplier.code:
        # 如果没有ERP编码，无法关联数据
        return {
            "coreStats": {
                "totalAmount": 0.0,
                "orderCount": 0,
                "materialCount": 0,
                "avgTaxNetPrice": 0.0,
                "maxQty": 0,
                "daysSinceLastOrder": 0
            },
            "trend": { "data": [], "topMaterials": [], "allMaterials": [] },
            "radar": [70, 70, 70, 70, 70],
            "tableData": []
        }

    from models import PurchaseOrderHistory
    
    # 获取该供应商的所有历史订单明细
    history_records = db.query(PurchaseOrderHistory).filter(
        PurchaseOrderHistory.supplier_code == supplier.code
    ).order_by(PurchaseOrderHistory.date.desc()).all()
    
    if not history_records:
        return {
            "coreStats": {
                "totalAmount": 0.0,
                "orderCount": 0,
                "materialCount": 0,
                "avgTaxNetPrice": 0.0,
                "maxQty": 0,
                "daysSinceLastOrder": 0
            },
            "trend": { "data": [], "topMaterials": [], "allMaterials": [] },
            "radar": [70, 70, 70, 70, 70],
            "tableData": []
        }

    # 1. 核心指标统计
    total_amount = sum(r.qty * r.tax_net_price for r in history_records if r.qty and r.tax_net_price)
    order_count = len(set(r.bill_no for r in history_records))
    material_count = len(set(r.material_code for r in history_records))
    
    # 平均含税单价 (简单平均)
    valid_prices = [r.tax_net_price for r in history_records if r.tax_net_price and r.tax_net_price > 0]
    avg_tax_net_price = sum(valid_prices) / len(valid_prices) if valid_prices else 0.0
    
    # 最大单笔采购量
    max_qty = max((r.qty for r in history_records if r.qty), default=0)
    
    # 最近交易距今(天)
    latest_record = history_records[0] # 因为已经按 date.desc() 排序
    days_since_last_order = (datetime.now() - latest_record.date).days if latest_record.date else 0

    # 2. 过去6个月的成交趋势（折线图/散点图：按物料分类）
    six_months_ago = datetime.now() - relativedelta(months=6)
    recent_records = [r for r in history_records if r.date and r.date >= six_months_ago]
    
    from collections import defaultdict
    material_order_counts = defaultdict(int)
    for r in history_records:
        if r.material_name:
            material_order_counts[r.material_name] += 1
            
    sorted_materials = sorted(material_order_counts.items(), key=lambda x: x[1], reverse=True)
    top_5_materials = [m[0] for m in sorted_materials[:5]]
    all_materials = [m[0] for m in sorted_materials]

    trend_data = []
    for r in recent_records:
        trend_data.append({
            "date": r.date.strftime("%Y-%m-%d"),
            "price": float(r.tax_net_price) if r.tax_net_price else 0.0,
            "material": r.material_name or "未知物料",
            "bill_no": r.bill_no
        })

    # 3. 交易明细 (按订单聚合，供前端过滤)
    orders_dict = defaultdict(lambda: {"date": "", "bill_no": "", "total_amount": 0.0, "items": []})
    for r in history_records:
        date_str = r.date.strftime("%Y-%m-%d") if r.date else ""
        key = (date_str, r.bill_no)
        if not orders_dict[key]["bill_no"]:
            orders_dict[key]["date"] = key[0]
            orders_dict[key]["bill_no"] = key[1]
        
        amount = (r.qty or 0) * (r.tax_net_price or 0)
        orders_dict[key]["total_amount"] += amount
        orders_dict[key]["items"].append({
            "material": r.material_name,
            "quantity": float(r.qty) if r.qty else 0,
            "price": float(r.price) if r.price else 0.0,
            "taxNetPrice": float(r.tax_net_price) if r.tax_net_price else 0.0
        })
        
    table_data = list(orders_dict.values())
    table_data.sort(key=lambda x: x["date"], reverse=True)

    # 雷达图 (暂时保持随机，后续可以根据预警数据做真实评价)
    base_score = 80
    radar_scores = [
        min(100, max(60, round(base_score + (hash(supplier.name + "price") % 15 - 5)))),
        min(100, max(60, round(base_score + (hash(supplier.name + "speed") % 15 - 5)))),
        min(100, max(60, round(base_score + (hash(supplier.name + "delivery") % 15 - 5)))),
        min(100, max(60, round(base_score + (hash(supplier.name + "quality") % 15 - 5)))),
        min(100, max(60, round(base_score + (hash(supplier.name + "service") % 15 - 5))))
    ]

    return {
        "coreStats": {
            "totalAmount": round(total_amount, 2),
            "orderCount": order_count,
            "materialCount": material_count,
            "avgTaxNetPrice": round(avg_tax_net_price, 2),
            "maxQty": round(max_qty, 2),
            "daysSinceLastOrder": days_since_last_order
        },
        "trend": {
            "data": trend_data,
            "topMaterials": top_5_materials,
            "allMaterials": all_materials
        },
        "radar": radar_scores,
        "tableData": table_data
    }

@router.get("/list")
def get_supplier_list(
    page: int = 1,
    page_size: int = 20,
    keyword: str = "",
    db: Session = Depends(get_db),
):
    """
    采购员获取供应商列表（分页）
    """
    CACHE_KEY = f"supplier:list:p{page}:s{page_size}:k{keyword}"
    cached = cache_get(CACHE_KEY)
    if cached is not None:
        return cached

    query = db.query(
        Supplier,
        func.count(PurchaseOrderHistory.id).label("transaction_count"),
    ).outerjoin(
        PurchaseOrderHistory, Supplier.code == PurchaseOrderHistory.supplier_code
    )

    if keyword:
        kw = f"%{keyword}%"
        query = query.filter(
            Supplier.name.ilike(kw) | Supplier.code.ilike(kw) | Supplier.contact_person.ilike(kw)
        )

    base_query = query.group_by(Supplier.id)

    total = base_query.count()

    def sort_key(item):
        supplier, count = item
        grade = "一般"
        if getattr(supplier, "grade", None):
            grade = supplier.grade
        elif getattr(supplier, "level", None) == "core":
            grade = "A级"
        return (-count, grade)

    all_items = sorted(base_query.all(), key=sort_key)
    start = (page - 1) * page_size
    paged_items = all_items[start : start + page_size]

    result = []
    for s, count in paged_items:
        grade = "一般"
        if getattr(s, "grade", None):
            grade = s.grade
        elif getattr(s, "level", None) == "core":
            grade = "A级"
        result.append({
            "id": s.id,
            "code": s.code,
            "name": s.name,
            "short_name": s.short_name,
            "social_credit_code": s.social_credit_code,
            "grade": grade,
            "contact_person": s.contact_person,
            "phone": s.phone,
            "email": s.email,
            "level": s.level,
            "status": s.status,
            "application_attachments": s.application_attachments or [],
            "onboarding_note": s.onboarding_note,
            "review_comment": s.review_comment,
            "rating_score": s.rating_score,
            "reviewer_id": s.reviewer_id,
            "reviewed_at": s.reviewed_at.strftime("%Y-%m-%d %H:%M:%S") if s.reviewed_at else None,
            "reviewer_name": s.reviewer.username if s.reviewer else None,
            "transaction_count": count,
            "user_id": s.user_id,
            "account_username": s.user.username if s.user else None,
        })

    response = {"total": total, "list": result}
    cache_set(CACHE_KEY, response)
    return response


@router.get("/pending")
def get_pending_suppliers(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    _require_admin_or_buyer(current_user)

    suppliers = (
        db.query(Supplier)
        .filter(Supplier.status == "pending")
        .order_by(Supplier.id.desc())
        .all()
    )

    return [
        {
            "id": supplier.id,
            "code": supplier.code,
            "name": supplier.name,
            "short_name": supplier.short_name,
            "social_credit_code": supplier.social_credit_code,
            "contact_person": supplier.contact_person,
            "phone": supplier.phone,
            "email": supplier.email,
            "level": supplier.level,
            "status": supplier.status,
            "application_attachments": supplier.application_attachments or [],
            "onboarding_note": supplier.onboarding_note,
            "review_comment": supplier.review_comment,
            "reviewer_id": supplier.reviewer_id,
            "reviewed_at": supplier.reviewed_at.strftime("%Y-%m-%d %H:%M:%S") if supplier.reviewed_at else None,
            "reviewer_name": supplier.reviewer.username if supplier.reviewer else None,
            "user_id": supplier.user_id,
            "account_username": supplier.user.username if supplier.user else None,
        }
        for supplier in suppliers
    ]


@router.get("/{supplier_id}/members")
def get_supplier_members(
    supplier_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    _require_admin_or_buyer(current_user)

    CACHE_KEY = f"supplier:members:{supplier_id}"
    cached = cache_get(CACHE_KEY)
    if cached is not None:
        return cached

    supplier = db.query(Supplier).filter(Supplier.id == supplier_id).first()
    if not supplier:
        raise HTTPException(status_code=404, detail="供应商不存在")

    members = (
        db.query(SupplierMember)
        .filter(SupplierMember.supplier_id == supplier_id)
        .order_by(
            SupplierMember.status.asc(),
            SupplierMember.role.desc(),
            SupplierMember.created_at.desc(),
        )
        .all()
    )

    result = []
    for m in members:
        user = db.query(User).filter(User.id == m.user_id).first()
        reviewer = db.query(User).filter(User.id == m.reviewed_by).first() if m.reviewed_by else None
        result.append({
            "id": m.id,
            "user_id": m.user_id,
            "phone": user.phone if user else "",
            "member_name": m.member_name,
            "position": m.position,
            "role": m.role,
            "status": m.status,
            "approval_mode": m.approval_mode,
            "application_note": m.application_note,
            "application_attachments": m.application_attachments or [],
            "review_comment": m.review_comment,
            "reviewed_by_name": reviewer.username if reviewer else None,
            "reviewed_at": m.reviewed_at.strftime("%Y-%m-%d %H:%M:%S") if m.reviewed_at else None,
            "created_at": m.created_at.strftime("%Y-%m-%d %H:%M:%S") if m.created_at else None,
        })

    cache_set(CACHE_KEY, result)
    return result


@router.get("/{supplier_id}/detail")
def get_supplier_detail(
    supplier_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    _require_admin_or_buyer(current_user)

    CACHE_KEY = f"supplier:detail:{supplier_id}"
    cached = cache_get(CACHE_KEY)
    if cached is not None:
        return cached

    supplier = db.query(Supplier).filter(Supplier.id == supplier_id).first()
    if not supplier:
        raise HTTPException(status_code=404, detail="供应商不存在")

    result = {
        "id": supplier.id,
        "application_attachments": supplier.application_attachments or [],
    }

    cache_set(CACHE_KEY, result)
    return result


@router.get("/my-profile")
def get_my_supplier_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    supplier, member = _get_supplier_portal_context(db, current_user)
    return {
        "id": supplier.id,
        "name": supplier.name,
        "code": supplier.code,
        "short_name": supplier.short_name,
        "contact_person": supplier.contact_person,
        "phone": supplier.phone,
        "email": supplier.email,
        "social_credit_code": supplier.social_credit_code,
        "grade": supplier.grade,
        "status": supplier.status,
        "application_attachments": supplier.application_attachments or [],
        "onboarding_note": supplier.onboarding_note,
        "review_comment": supplier.review_comment,
        "role": member.role,
        "member_status": member.status,
    }


@router.put("/my-profile")
def update_my_supplier_profile(
    payload: SupplierProfileUpdatePayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    supplier, member = _get_supplier_portal_context(db, current_user)
    if member.role not in ("admin", "owner"):
        raise HTTPException(status_code=403, detail="仅管理员可修改公司信息")

    update_data = payload.model_dump(exclude_unset=True)
    if "social_credit_code" in update_data:
        social_credit_code = (update_data.get("social_credit_code") or "").strip() or None
        if social_credit_code:
            duplicated = (
                db.query(Supplier)
                .filter(Supplier.social_credit_code == social_credit_code, Supplier.id != supplier.id)
                .first()
            )
            if duplicated:
                raise HTTPException(status_code=400, detail="该统一社会信用代码已存在")
        update_data["social_credit_code"] = social_credit_code
    for field, value in update_data.items():
        setattr(supplier, field, value)

    db.commit()
    db.refresh(supplier)
    _invalidate_supplier_cache()
    return {"detail": "公司信息更新成功"}


@router.get("/onboarding-template")
def download_supplier_onboarding_template(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _get_supplier_portal_context(db, current_user)
    if not SUPPLIER_SURVEY_TEMPLATE_PATH.exists():
        raise HTTPException(status_code=404, detail="供应商调查表模板不存在")
    return FileResponse(
        path=SUPPLIER_SURVEY_TEMPLATE_PATH,
        filename=SUPPLIER_SURVEY_TEMPLATE_PATH.name,
        media_type="application/msword",
    )


@router.post("/manage")
def create_supplier_with_optional_account(
    payload: SupplierCreatePayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    采购员/管理员创建供应商，可选同时创建登录账号。
    """
    _require_admin_or_buyer(current_user)

    supplier_name = (payload.name or "").strip()
    if not supplier_name:
        raise HTTPException(status_code=400, detail="供应商名称不能为空")

    existing_supplier = db.query(Supplier).filter(Supplier.name == supplier_name).first()
    if existing_supplier:
        raise HTTPException(status_code=400, detail="供应商名称已存在")

    supplier_code = (payload.code or "").strip() or None
    if supplier_code:
        existing_code = db.query(Supplier).filter(Supplier.code == supplier_code).first()
        if existing_code:
            raise HTTPException(status_code=400, detail="供应商编码已存在")

    username = (payload.username or "").strip() or None
    password = payload.password
    user = None
    if username or password:
        if not username or not password:
            raise HTTPException(status_code=400, detail="如需创建登录账号，请同时填写账号和密码")
        if len(password) < 6:
            raise HTTPException(status_code=400, detail="账号密码长度至少6位")
        existing_user = db.query(User).filter(User.username == username).first()
        if existing_user:
            raise HTTPException(status_code=400, detail="该登录账号已存在")
        user = User(
            username=username,
            password_hash=get_password_hash(password),
            role="supplier"
        )
        db.add(user)
        db.flush()

    supplier = Supplier(
        name=supplier_name,
        code=supplier_code,
        contact_person=(payload.contact_person or "").strip() or None,
        phone=(payload.phone or "").strip() or None,
        email=(payload.email or "").strip() or None,
        status=payload.status or "approved",
        grade=payload.grade or "一般",
        level=payload.level or "general",
        user_id=user.id if user else None
    )
    db.add(supplier)
    db.commit()
    db.refresh(supplier)
    _invalidate_supplier_cache()
    return {
        "id": supplier.id,
        "name": supplier.name,
        "status": supplier.status,
        "grade": supplier.grade,
        "user_id": supplier.user_id,
        "account_username": user.username if user else None
    }

@router.post("/reset-all-accounts")
def reset_all_supplier_accounts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    request: Request = None
) -> Any:
    _require_admin_or_buyer(current_user)

    suppliers = db.query(Supplier).filter(Supplier.status == "approved").all()
    updated_count = 0
    errors = []

    for supplier in suppliers:
        try:
            new_username = supplier.name
            new_password = "123456"

            if supplier.user_id:
                user = db.query(User).filter(User.id == supplier.user_id).first()
                if user:
                    existing_user = db.query(User).filter(
                        User.username == new_username,
                        User.id != user.id
                    ).first()
                    if existing_user:
                        errors.append(f"供应商 {supplier.name}: 账号 {new_username} 已被占用")
                        continue

                    user.username = new_username
                    user.password_hash = get_password_hash(new_password)
                    db.add(user)
                    updated_count += 1
            else:
                existing_user = db.query(User).filter(User.username == new_username).first()
                if existing_user:
                    errors.append(f"供应商 {supplier.name}: 账号 {new_username} 已被占用")
                    continue

                user = User(
                    username=new_username,
                    password_hash=get_password_hash(new_password),
                    role="supplier"
                )
                db.add(user)
                db.flush()
                supplier.user_id = user.id
                updated_count += 1

        except Exception as e:
            errors.append(f"供应商 {supplier.name}: {str(e)}")

    db.commit()

    from routers.system import log_operation
    log_operation(
        db,
        current_user.id,
        "RESET_SUPPLIER_ACCOUNTS",
        f"批量重置供应商账号密码: 成功{updated_count}个, 失败{len(errors)}个",
        request=request,
        module="供应商管理",
        target_type="供应商账号",
        target_name="批量重置",
        result="partial" if errors else "success",
        extra_data={
            "updated_count": updated_count,
            "failed_count": len(errors),
            "total_count": len(suppliers),
            "errors": errors[:10]
        }
    )

    return {
        "message": f"批量重置完成: 成功更新 {updated_count} 个供应商账号",
        "updated_count": updated_count,
        "total_count": len(suppliers),
        "errors": errors[:10] if len(errors) > 10 else errors,
        "errors_count": len(errors)
    }

@router.put("/change-password")
def change_password(
    payload: SupplierChangePasswordPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    request: Request = None
) -> Any:
    if current_user.role != "supplier":
        raise HTTPException(status_code=403, detail="仅供应商可修改密码")

    from core.security import verify_password

    supplier, _ = _get_supplier_portal_context(db, current_user)
    if not supplier:
        raise HTTPException(status_code=404, detail="未找到供应商信息")

    if not verify_password(payload.old_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="原密码不正确")

    current_user.password_hash = get_password_hash(payload.new_password)
    db.add(current_user)
    db.commit()

    from routers.system import log_operation
    log_operation(
        db,
        current_user.id,
        "CHANGE_PASSWORD",
        f"供应商 {supplier.name} 修改了登录密码",
        request=request,
        module="账号安全",
        target_type="供应商账号",
        target_name=supplier.name,
        result="success"
    )

    return {"message": "密码修改成功"}

@router.put("/{supplier_id}")
def update_supplier(
    supplier_id: int, 
    supplier_update: SupplierUpdate, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    request: Request = None
):
    """
    采购员审核/定级供应商
    """
    _require_admin_or_buyer(current_user)
        
    supplier = db.query(Supplier).filter(Supplier.id == supplier_id).first()
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")

    review_comment = (
        supplier_update.review_comment.strip()
        if isinstance(supplier_update.review_comment, str)
        else None
    ) or None

    if supplier_update.status:
        supplier.status = supplier_update.status
        supplier.review_comment = review_comment
        if supplier_update.status in ["approved", "rejected", "pending"]:
            supplier.reviewer_id = current_user.id
            supplier.reviewed_at = datetime.now()
        if supplier_update.status == "approved":
            supplier.review_comment = None
            db.query(SupplierMember).filter(
                SupplierMember.supplier_id == supplier.id,
                SupplierMember.status == "pending"
            ).update(
                {
                    "status": "active",
                    "reviewed_by": current_user.id,
                    "reviewed_at": datetime.now(),
                },
                synchronize_session=False,
            )
        elif supplier_update.status == "pending":
            db.query(SupplierMember).filter(
                SupplierMember.supplier_id == supplier.id,
                SupplierMember.status.in_(["pending", "active"])
            ).update(
                {
                    "status": "pending",
                    "reviewed_by": current_user.id,
                    "reviewed_at": datetime.now(),
                    "review_comment": supplier.review_comment,
                },
                synchronize_session=False,
            )
        elif supplier_update.status == "rejected":
            db.query(SupplierMember).filter(
                SupplierMember.supplier_id == supplier.id,
                SupplierMember.status.in_(["pending", "active"])
            ).update(
                {
                    "status": "disabled",
                    "reviewed_by": current_user.id,
                    "reviewed_at": datetime.now(),
                    "review_comment": supplier.review_comment or "企业审核未通过",
                },
                synchronize_session=False,
            )
    if supplier_update.level:
        supplier.level = supplier_update.level

    if supplier_update.grade:
        supplier.grade = supplier_update.grade
        
    db.commit()
    db.refresh(supplier)
    
    from routers.system import log_operation
    log_operation(
        db,
        current_user.id,
        "UPDATE_SUPPLIER",
        f"更新供应商 {supplier.name} 状态为 {supplier.status}, 评级为 {supplier.grade}",
        request=request,
        module="供应商管理",
        target_type="供应商",
        target_name=supplier.name,
        result="success",
        extra_data={
            "status": supplier.status,
            "grade": supplier.grade,
            "level": supplier.level
        }
    )
    
    _invalidate_supplier_cache()
    return {"message": "Supplier updated successfully", "id": supplier.id, "status": supplier.status, "grade": supplier.grade}


@router.put("/{supplier_id}/account")
def update_supplier_account(
    supplier_id: int,
    payload: SupplierAccountUpdatePayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    采购员/管理员更新供应商登录账号；若供应商尚无账号，可通过账号+密码创建并绑定。
    """
    _require_admin_or_buyer(current_user)

    supplier = db.query(Supplier).filter(Supplier.id == supplier_id).first()
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")

    username = (payload.username or "").strip() or None
    password = payload.password
    if not username and not password:
        raise HTTPException(status_code=400, detail="请至少填写一个账号信息字段")
    if password and len(password) < 6:
        raise HTTPException(status_code=400, detail="账号密码长度至少6位")

    account_user = db.query(User).filter(User.id == supplier.user_id).first() if supplier.user_id else None
    if not account_user:
        if not username or not password:
            raise HTTPException(status_code=400, detail="当前供应商无登录账号，请同时填写账号和密码进行创建")
        existing = db.query(User).filter(User.username == username).first()
        if existing:
            raise HTTPException(status_code=400, detail="该登录账号已存在")
        account_user = User(
            username=username,
            password_hash=get_password_hash(password),
            role="supplier"
        )
        db.add(account_user)
        db.flush()
        supplier.user_id = account_user.id
    else:
        if username and username != account_user.username:
            existing = db.query(User).filter(User.username == username, User.id != account_user.id).first()
            if existing:
                raise HTTPException(status_code=400, detail="该登录账号已存在")
            account_user.username = username
        if password:
            account_user.password_hash = get_password_hash(password)

    db.add(supplier)
    db.commit()
    db.refresh(supplier)
    return {
        "message": "Supplier account updated successfully",
        "supplier_id": supplier.id,
        "user_id": supplier.user_id,
        "account_username": account_user.username if account_user else None
    }

@router.delete("/{supplier_id}")
def delete_supplier(
    supplier_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    request: Request = None
):
    """
    删除供应商（仅超级管理员可操作）
    """
    if current_user.role not in ["admin", "buyer_manager"]:
        raise HTTPException(status_code=403, detail="只有超级管理员或采购部经理可以删除供应商")
        
    supplier = db.query(Supplier).filter(Supplier.id == supplier_id).first()
    if not supplier:
        raise HTTPException(status_code=404, detail="供应商不存在")
        
    try:
        from models import WarningMessage, Quotation, Contract
        
        # 1. 删除关联的预警消息
        db.query(WarningMessage).filter(WarningMessage.supplier_id == supplier.id).delete()
        
        # 2. 删除询价关联及子记录
        inquiry_links = db.query(InquirySupplier).filter(InquirySupplier.supplier_id == supplier.id).all()
        for link in inquiry_links:
            db.query(Quotation).filter(Quotation.inquiry_supplier_id == link.id).delete()
            db.query(Contract).filter(Contract.inquiry_supplier_id == link.id).delete()
            db.delete(link)
            
        user_id_to_delete = supplier.user_id
        supplier_name = supplier.name
        
        # 3. 删除供应商主表记录
        db.delete(supplier)
        
        # 4. 如果有绑定的 User 账号，一并删除
        if user_id_to_delete:
            user_account = db.query(User).filter(User.id == user_id_to_delete).first()
            if user_account:
                db.delete(user_account)
                
        # 5. 记录日志
        from routers.system import log_operation
        log_operation(
            db,
            current_user.id,
            "DELETE_SUPPLIER",
            f"删除了供应商及其关联账号和数据: {supplier_name}",
            request=request,
            module="供应商管理",
            target_type="供应商",
            target_name=supplier_name,
            result="success"
        )
        
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"删除供应商失败: {str(e)}")
        
    _invalidate_supplier_cache()
    return {"message": "供应商已成功删除"}

@router.get("/my-inquiries")
def get_my_inquiries(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    供应商登录后获取自己的询价任务列表
    """
    if current_user.role != "supplier":
        raise HTTPException(status_code=403, detail="Not authorized")
        
    supplier, member = _get_supplier_portal_context(db, current_user)
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier profile not found")
        
    inquiries = db.query(InquirySupplier).filter(
        InquirySupplier.supplier_id == supplier.id
    ).order_by(InquirySupplier.id.desc()).all()
    
    result = []
    for link in inquiries:
        task = db.query(InquiryTask).filter(InquiryTask.id == link.task_id).first()
        if not task:
            continue
        contract_record = db.query(Contract).filter(Contract.inquiry_supplier_id == link.id).first()
        contract_pdf_path = contract_record.pdf_path if contract_record else None
        contract_status = contract_record.status if contract_record else None
        contract_no = f"HT-{task.id}-{link.id}" if contract_record else None
            
        result.append({
            "inquiry_supplier_id": link.id,
            "task_id": task.id,
            "task_title": task.title,
            "status": link.status,
            "task_status": task.status,
            "current_round": link.current_round,
            "contract_pdf": contract_pdf_path,
            "contract_pdf_path": contract_pdf_path,
            "contract_status": contract_status,
            "contract_no": contract_no,
            "created_at": link.created_at
        })
        
    return result

@router.get("/me")
def get_my_supplier_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    获取当前登录供应商的基础信息（用于前端展示公司名称）
    """
    if current_user.role != "supplier":
        raise HTTPException(status_code=403, detail="Not authorized")

    supplier, member = _get_supplier_portal_context(db, current_user)
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier profile not found")

    return {
        "id": supplier.id,
        "company_name": supplier.name,
        "contact_person": supplier.contact_person,
        "phone": supplier.phone,
        "email": supplier.email,
        "status": supplier.status,
        "member_status": member.status,
    }

@router.get("/inquiry/{inquiry_supplier_id}")
def get_inquiry_details(
    inquiry_supplier_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    供应商获取特定询价单的明细（用于报价）
    """
    if current_user.role != "supplier":
        raise HTTPException(status_code=403, detail="Not authorized")
        
    supplier, _ = _get_supplier_context(db, current_user)
    
    link = db.query(InquirySupplier).filter(
        InquirySupplier.id == inquiry_supplier_id,
        InquirySupplier.supplier_id == supplier.id
    ).first()
    
    if not link:
        raise HTTPException(status_code=404, detail="Inquiry not found")
        
    task = db.query(InquiryTask).filter(InquiryTask.id == link.task_id).first()
    contract_record = db.query(Contract).filter(Contract.inquiry_supplier_id == link.id).first()
    contract_pdf_path = contract_record.pdf_path if contract_record else None
    contract_no = f"HT-{task.id}-{link.id}" if contract_record else None
    
    last_round_quotes = {}
    preload_round = None
    if link.status in [LinkStatus.QUOTED, LinkStatus.LOCKED]:
        preload_round = link.current_round
    elif link.current_round > 1:
        preload_round = link.current_round - 1

    if preload_round is not None:
        prev_quotes = db.query(Quotation).filter(
            Quotation.inquiry_supplier_id == link.id,
            Quotation.round == preload_round
        ).all()
        for q in prev_quotes:
            last_round_quotes[q.item_id] = q

    allowed_task_items = _get_allowed_task_items_for_supplier(task, link)

    items = []
    for item in allowed_task_items:
        prev_q = last_round_quotes.get(item.id)
        default_delivery = prev_q.delivery_date if prev_q and prev_q.delivery_date else item.request.delivery_date

        items.append({
            "request_id": item.request_id,
            "material_name": item.request.material_name,
            "material_code": item.request.material_code,
            "material_model": item.request.material_model,
            "qty": item.request.qty,
            "target_delivery_date": item.request.delivery_date,
            "delivery_date": default_delivery,
            "price": float(prev_q.price) if prev_q and prev_q.price is not None else None,
            "remark": prev_q.remark if prev_q else "",
            "project_name": item.request.project_info.get("name") if item.request.project_info else ""
        })
        
    return {
        "task_title": task.title,
        "task_status": task.status,
        "deadline": task.deadline,
        "round": link.current_round,
        "status": link.status,
        "latest_ai_feedback": link.latest_ai_feedback,
        "contract_pdf": contract_pdf_path,
        "contract_pdf_path": contract_pdf_path,
        "contract_no": contract_no,
        "attachments": _get_task_attachments(task),
        "items": items
    }


@router.post("/inquiries/{inquiry_id}/confirm-contract")
def confirm_contract(
    inquiry_id: int,
    payload: SupplierContractInfoSubmit,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    if current_user.role != "supplier":
        raise HTTPException(status_code=403, detail="Not authorized")

    supplier, _ = _get_supplier_context(db, current_user)
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier profile not found")

    link = db.query(InquirySupplier).filter(
        InquirySupplier.id == inquiry_id,
        InquirySupplier.supplier_id == supplier.id
    ).first()
    if not link:
        raise HTTPException(status_code=404, detail="Inquiry not found")
    if link.status != LinkStatus.DEAL:
        raise HTTPException(status_code=400, detail="Only deal inquiry can confirm contract")

    contract_record = db.query(Contract).filter(Contract.inquiry_supplier_id == link.id).first()
    if not contract_record:
        contract_record = Contract(
            task_id=link.task_id,
            inquiry_supplier_id=link.id,
            status="pending"
        )
    contract_record.address = payload.address
    contract_record.legal_representative = payload.legal_representative
    contract_record.agent = payload.agent
    contract_record.contact_phone = payload.contact_phone
    contract_record.bank_name = payload.bank_name
    contract_record.bank_account = payload.bank_account
    contract_record.tax_id = payload.tax_id
    contract_record.fax = payload.fax
    contract_record.postal_code = payload.postal_code
    if payload.buyer_company_name:
        contract_record.buyer_company_name = payload.buyer_company_name
    if contract_record.pdf_path:
        history_versions = list(contract_record.history_versions or [])
        history_versions.append({
            "pdf_path": contract_record.pdf_path,
            "generated_at": datetime.now().isoformat(),
            "event": "supplier_resubmitted"
        })
        contract_record.history_versions = history_versions
        contract_record.pdf_path = None
    contract_record.status = "generating"
    db.add(contract_record)
    db.commit()
    db.refresh(contract_record)

    background_tasks.add_task(_generate_contract_pdf_background, link.id)
    return {"message": "合同信息已提交，正在生成合同", "inquiry_id": link.id}

@router.get("/last-contract-info")
def get_last_contract_info(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    if current_user.role != "supplier":
        raise HTTPException(status_code=403, detail="Not authorized")

    supplier, _ = _get_supplier_context(db, current_user)
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier profile not found")

    last_contract = db.query(Contract).filter(
        Contract.inquiry_supplier_id.in_(
            db.query(InquirySupplier.id).filter(InquirySupplier.supplier_id == supplier.id)
        ),
        Contract.address.isnot(None)
    ).order_by(Contract.updated_at.desc()).first()

    if not last_contract:
        return {}

    return {
        "address": last_contract.address or "",
        "legal_representative": last_contract.legal_representative or "",
        "agent": last_contract.agent or "",
        "contact_phone": last_contract.contact_phone or "",
        "bank_name": last_contract.bank_name or "",
        "bank_account": last_contract.bank_account or "",
        "tax_id": last_contract.tax_id or "",
        "fax": last_contract.fax or "",
        "postal_code": last_contract.postal_code or ""
    }

@router.post("/inquiry/{inquiry_supplier_id}/quote", response_model=SupplierQuoteResponse)
async def submit_quote(
    inquiry_supplier_id: int,
    submission: QuoteSubmission,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    供应商提交报价
    """
    if current_user.role != "supplier":
        raise HTTPException(status_code=403, detail="Not authorized")
        
    supplier, _ = _get_supplier_context(db, current_user)
    
    link = db.query(InquirySupplier).filter(
        InquirySupplier.id == inquiry_supplier_id,
        InquirySupplier.supplier_id == supplier.id
    ).first()
    
    if not link:
        raise HTTPException(status_code=404, detail="Inquiry not found")

    link_task = db.query(InquiryTask).filter(InquiryTask.id == link.task_id).first()
    if not link_task:
        raise HTTPException(status_code=404, detail="Inquiry task not found")

    allowed_task_items = _get_allowed_task_items_for_supplier(link_task, link)
    allowed_request_ids = {
        int(item.request_id)
        for item in allowed_task_items
        if item and item.request_id is not None
    }
    if not allowed_request_ids:
        raise HTTPException(status_code=400, detail="No materials are assigned to this supplier in the current inquiry.")

    if link_task.deadline and datetime.now() > link_task.deadline:
        raise HTTPException(status_code=400, detail="Inquiry deadline has passed. Quotation submission is closed.")
        
    if link.status in [LinkStatus.DEAL, LinkStatus.REJECT, LinkStatus.LOCKED]:
        raise HTTPException(status_code=400, detail="Inquiry is already closed for you.")

    if link.status == LinkStatus.QUOTED:
        quote_items = db.query(Quotation).filter(
            Quotation.inquiry_supplier_id == link.id,
            Quotation.round == link.current_round
        ).all()
    elif link.status in [LinkStatus.SENT, LinkStatus.NEGOTIATION]:
        # === 新增：异常报价前置预检 ===
        if not getattr(submission, 'force_submit', False):
            anomaly_names = []
            for item in submission.items:
                # 预查期望价
                t_item = db.query(InquiryTaskItem).filter(
                    InquiryTaskItem.task_id == link.task_id,
                    InquiryTaskItem.request_id == item.request_id
                ).first()
                r_item = db.query(InquiryRequest).filter(InquiryRequest.id == t_item.request_id).first() if t_item else None
                
                if r_item and r_item.target_price and r_item.target_price > 0:
                    # 如果报价偏离期望价 50% 以上，记录异常
                    if item.price <= r_item.target_price * 0.5 or item.price >= r_item.target_price * 1.5:
                        anomaly_names.append(r_item.material_name)
            
            # 如果发现异常，拦截提交并返回特定 action 让前端弹窗
            if anomaly_names:
                names_str = ", ".join(anomaly_names[:3]) + (" 等" if len(anomaly_names) > 3 else "")
                return {
                    "message": f"预警：系统检测到【{names_str}】的报价大幅偏离常规预期，请仔细核对是否报错了规格或单位。如确认无误，请在弹窗中强行提交。",
                    "next_action": "confirm_anomaly",
                    "ai_feedback": ""
                }
        # === 预检结束 ===

        quote_items = []
        for item in submission.items:
            if int(item.request_id) not in allowed_request_ids:
                raise HTTPException(status_code=400, detail="You can only quote for materials assigned to you.")
            task_item = db.query(InquiryTaskItem).filter(
                InquiryTaskItem.task_id == link.task_id,
                InquiryTaskItem.request_id == item.request_id
            ).first()
            
            if task_item:
                quote = Quotation(
                    inquiry_supplier_id=link.id,
                    round=link.current_round,
                    item_id=task_item.id,
                    qty=item.qty,
                    price=item.price,
                    delivery_date=item.delivery_date,
                    remark=item.remark
                )
                db.add(quote)
                quote_items.append(quote)
        
        link.status = LinkStatus.QUOTED
        db.commit() # 先提交报价记录
    else:
        raise HTTPException(status_code=400, detail="Current link status does not allow quoting.")

    # 2. 检查是否所有活跃的供应商都已完成本轮报价
    all_links = db.query(InquirySupplier).filter(InquirySupplier.task_id == link.task_id).all()
    
    # 获取本轮还在参与的供应商 (状态是 SENT, NEGOTIATION 或 QUOTED)
    # 如果有人还是 SENT 或 NEGOTIATION，说明他还没报完
    all_quoted = True
    for l in all_links:
        if l.status in [LinkStatus.SENT, LinkStatus.NEGOTIATION]:
            all_quoted = False
            break
            
    if not all_quoted:
        link.latest_ai_feedback = "已收到您的报价。目前正在等待其他供应商完成本轮报价，待所有供应商报价完成后，系统将统一下发反馈，请耐心等待。"
        db.commit()
        return {
            "message": "报价已收到，等待其他供应商完成。",
            "next_action": "wait",
            "ai_feedback": link.latest_ai_feedback
        }

    # === 达到目标价的供应商会被锁定，剩余供应商继续进入后续轮次 ===
    locked_candidates = []
    for l in all_links:
        if l.status != LinkStatus.QUOTED:
            continue
        l_quotes = db.query(Quotation).filter(
            Quotation.inquiry_supplier_id == l.id,
            Quotation.round == l.current_round
        ).all()
        is_kill = True
        has_target = False
        for q in l_quotes:
            t_item = db.query(InquiryTaskItem).filter(InquiryTaskItem.id == q.item_id).first()
            r_item = db.query(InquiryRequest).filter(InquiryRequest.id == t_item.request_id).first() if t_item else None
            target_p = r_item.target_price if r_item else None

            if target_p is None:
                is_kill = False
                break
            has_target = True
            if q.price > target_p or (target_p > 0 and q.price <= target_p * 0.5):
                is_kill = False
                break
        if has_target and is_kill:
            locked_candidates.append(l)

    locked_supplier_names = []
    for locked_link in locked_candidates:
        locked_link.status = LinkStatus.LOCKED
        if locked_link.supplier and locked_link.supplier.name:
            locked_supplier_names.append(locked_link.supplier.name)
        locked_link.latest_ai_feedback = (
            "您的报价已达到采购目标区间，系统已将您锁定为候选供应商。"
            "后续无需继续报价，系统会在自动谈判结束后统一进行综合排名并进入份额分配。"
        )

    locked_summary_names = "、".join(locked_supplier_names[:3])
    if len(locked_supplier_names) > 3:
        locked_summary_names += "等"
    if not locked_summary_names:
        locked_summary_names = "已达标供应商"

    # 3. 所有供应商均已报价，统一处理下一轮逻辑或结束
    strategy = link_task.strategy_config or {}
    max_rounds = strategy.get("max_rounds", 3)
    current_round = link.current_round
    if current_round < max_rounds:
        market_quotes = (
            db.query(Quotation)
            .join(InquirySupplier, Quotation.inquiry_supplier_id == InquirySupplier.id)
            .filter(
                InquirySupplier.task_id == link.task_id,
                InquirySupplier.status != LinkStatus.REJECT,
                Quotation.round == current_round
            )
            .all()
        )
        market_min_price_map = {}
        for mq in market_quotes:
            price = float(mq.price or 0)
            if price <= 0:
                continue
            if mq.item_id not in market_min_price_map or price < market_min_price_map[mq.item_id]:
                market_min_price_map[mq.item_id] = price

        def process_link(l):
            # 获取该供应商本轮报价
            l_quotes = db.query(Quotation).filter(Quotation.inquiry_supplier_id == l.id, Quotation.round == current_round).all()
            if not l_quotes:
                return
                
            feedback_lines = []
            
            for q in l_quotes:
                t_item = db.query(InquiryTaskItem).filter(InquiryTaskItem.id == q.item_id).first()
                r_item = db.query(InquiryRequest).filter(InquiryRequest.id == t_item.request_id).first()
                target_price = float(r_item.target_price) if r_item and r_item.target_price is not None else 0.0
                market_min_price = float(market_min_price_map.get(q.item_id, q.price or 0))
                drop_ratio, suggested_price, feedback = calculate_bargain_feedback(
                    target_price=target_price,
                    market_min_price=market_min_price,
                    current_price=float(q.price or 0),
                    current_round=current_round,
                    max_rounds=max_rounds,
                )
                material_name = r_item.material_name if r_item else f"物料#{q.item_id}"
                material_model = getattr(r_item, "material_model", "") if r_item else ""
                material_label = f"{material_name} / {material_model}" if material_model else material_name
                if feedback:
                    feedback_lines.append(
                        f"{material_label}：当前报价{float(q.price or 0):.4f}元，建议下调{drop_ratio * 100:.2f}%至{suggested_price:.4f}元。"
                    )
                else:
                    feedback_lines.append(
                        f"{material_label}：当前报价{float(q.price or 0):.4f}元，已接近目标区间，可保持或小幅优化。"
                    )

            l.latest_ai_feedback = "系统已完成本轮价格分析，请参考以下建议进行下一轮报价：\n" + "\n".join(feedback_lines)
            l.current_round += 1
            l.status = LinkStatus.NEGOTIATION

        quoted_links = [l for l in all_links if l.status == LinkStatus.QUOTED]
        if not quoted_links:
            link_task.status = TaskStatus.AWAITING_AWARD
            final_feedback = (
                "自动谈判已结束，系统已汇总所有有效报价并生成综合排名。"
                "采购方将直接在询价任务中完成份额分配，请耐心等待结果通知。"
            )
            for l in all_links:
                if l.status in [LinkStatus.QUOTED, LinkStatus.LOCKED]:
                    if l.status == LinkStatus.LOCKED:
                        l.latest_ai_feedback = (
                            "您的报价已达到采购目标区间并被锁定。"
                            "自动谈判现已结束，采购方将根据综合排名尽快完成份额分配。"
                        )
                    else:
                        l.latest_ai_feedback = final_feedback
            db.commit()
            return {
                "message": "已无待继续谈判的供应商，系统已转入最终评审与份额分配流程。",
                "next_action": "wait",
                "ai_feedback": final_feedback
            }
        for l in quoted_links:
            process_link(l)
        if locked_candidates:
            continue_feedback = (
                "本轮谈判已结束，系统已锁定达到目标区间的候选供应商。"
                "您将进入下一轮自动谈判，请根据系统建议继续报价。"
            )
        else:
            continue_feedback = link.latest_ai_feedback
        db.commit()
        
        return {
            "message": locked_candidates and "部分供应商已锁定，其余供应商已触发下一轮谈判。" or "所有供应商报价已完成，已触发下一轮谈判。",
            "next_action": "re-quote",
            "ai_feedback": continue_feedback
        }
        
    else:
        # 达到最大轮数后，列出所有有效供应商排名，再进入智能比价/定标流程
        link_task.status = TaskStatus.AWAITING_AWARD
        if locked_candidates:
            final_feedback = (
                "自动谈判已达到最大轮次，系统已汇总所有有效供应商当前轮次与锁定轮次报价并生成综合排名。"
                "采购方将直接在询价任务中完成份额分配，请耐心等待结果通知。"
            )
        else:
            final_feedback = "自动谈判已达到最大轮次，系统已汇总所有有效供应商报价并生成综合排名。采购方将直接在询价任务中完成份额分配，请耐心等待结果通知。"
        for l in all_links:
            if l.status in [LinkStatus.QUOTED, LinkStatus.LOCKED]:
                if l.status == LinkStatus.LOCKED:
                    l.latest_ai_feedback = (
                        "您的报价已达到采购目标区间并被锁定。"
                        "自动谈判现已结束，采购方将根据综合排名尽快完成份额分配。"
                    )
                else:
                    l.latest_ai_feedback = final_feedback
        db.commit()
        return {
            "message": "谈判轮次已达上限，系统已转入最终评审与份额分配流程。",
            "next_action": "wait",
            "ai_feedback": final_feedback
        }
