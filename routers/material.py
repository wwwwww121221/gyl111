from collections import defaultdict
import logging
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Response
from sqlalchemy import desc, func, or_
from sqlalchemy.orm import Session

from backend.sync_po_history import sync_recent_po_history_for_analysis
from kingdee_erp_tool.services.purchase import get_historical_purchase_prices
from models import Material, PurchaseOrderMonthlyStat, PurchaseOrderSummary, Supplier, User, get_db
from routers.inquiry import get_current_user
from services.cache_service import load_cache_entry, save_cached_data, should_refresh_cache

router = APIRouter()
logger = logging.getLogger(__name__)

_MATERIAL_LIST_CACHE_TTL = 1800
_MATERIAL_LIST_SOFT_TTL = 180
_MATERIAL_ANALYSIS_CACHE_TTL = 1800
_MATERIAL_ANALYSIS_SOFT_TTL = 180
_MATERIAL_HISTORY_CACHE_TTL = 600
_MATERIAL_HISTORY_SOFT_TTL = 120
_MATERIAL_ANALYSIS_MONTHS_BACK = 12
_MATERIAL_DETAIL_PAGE_SIZE = 500
_MATERIAL_DETAIL_MAX_ROWS = 5000


def _require_buyer_or_admin(current_user: User) -> None:
    if current_user.role not in ["admin", "buyer", "buyer_manager"]:
        raise HTTPException(status_code=403, detail="Not authorized")


def _material_list_cache_key(keyword: str, limit: int) -> str:
    return f"material:list:k:{keyword}:l:{limit}"


def _material_analysis_cache_key(material_code: str) -> str:
    return f"material:analysis:{material_code}"


def _material_history_cache_key(
    material_code: str,
    supplier_code: str,
    start_date: str,
    end_date: str,
    page: int,
    page_size: int,
) -> str:
    return (
        "material:history:"
        f"m:{material_code}:s:{supplier_code}:sd:{start_date}:ed:{end_date}:"
        f"p:{page}:ps:{page_size}"
    )


def _fetch_material_history_details(
    material_code: str,
    months_back: int = _MATERIAL_ANALYSIS_MONTHS_BACK,
    page_size: int = _MATERIAL_DETAIL_PAGE_SIZE,
    max_rows: int = _MATERIAL_DETAIL_MAX_ROWS,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    start_row = 0

    while len(rows) < max_rows:
        batch_limit = min(page_size, max_rows - len(rows))
        batch = get_historical_purchase_prices(
            material_code=material_code,
            months_back=months_back,
            limit=batch_limit,
            start_row=start_row,
        )
        if not batch:
            break

        rows.extend(batch)
        start_row += len(batch)
        if len(batch) < batch_limit:
            break

    return rows


def _normalize_history_date_range(start_date: str | None, end_date: str | None) -> tuple[str | None, str | None]:
    normalized_start = (start_date or "").strip() or None
    normalized_end = (end_date or "").strip() or None

    if normalized_start and "T" not in normalized_start:
        normalized_start = f"{normalized_start}T00:00:00"
    if normalized_end and "T" not in normalized_end:
        normalized_end = f"{normalized_end}T23:59:59"

    return normalized_start, normalized_end


def _build_material_history_payload(
    db: Session,
    material_code: str,
    supplier_code: str | None,
    start_date: str | None,
    end_date: str | None,
    page: int,
    page_size: int,
) -> dict[str, Any]:
    normalized_supplier_code = (supplier_code or "").strip()
    normalized_start, normalized_end = _normalize_history_date_range(start_date, end_date)
    start_row = max(0, (page - 1) * page_size)
    fetch_limit = page_size + 1

    raw_rows = get_historical_purchase_prices(
        material_code=material_code,
        supplier_code=normalized_supplier_code or None,
        months_back=_MATERIAL_ANALYSIS_MONTHS_BACK,
        limit=fetch_limit,
        start_date=normalized_start,
        end_date=normalized_end,
        start_row=start_row,
    )

    grade_rows = (
        db.query(PurchaseOrderSummary.supplier_code, PurchaseOrderSummary.supplier_name, Supplier.grade.label("supplier_grade"))
        .outerjoin(Supplier, PurchaseOrderSummary.supplier_name == Supplier.name)
        .filter(PurchaseOrderSummary.material_code == material_code)
        .all()
    )
    grade_by_code = {
        str(row.supplier_code or "").strip(): row.supplier_grade
        for row in grade_rows
        if row.supplier_code
    }
    grade_by_name = {
        str(row.supplier_name or "").strip(): row.supplier_grade
        for row in grade_rows
        if row.supplier_name
    }

    has_more = len(raw_rows) > page_size
    items = []
    for item in raw_rows[:page_size]:
        row_supplier_code = str(item.get("supplier_code") or "").strip()
        row_supplier_name = str(item.get("supplier_name") or "").strip()
        items.append(
            {
                "date": str(item.get("date") or "")[:10],
                "bill_no": str(item.get("bill_no") or "").strip(),
                "supplier_code": row_supplier_code,
                "supplier_name": row_supplier_name,
                "supplier_grade": grade_by_code.get(row_supplier_code) or grade_by_name.get(row_supplier_name),
                "qty": float(item.get("qty") or 0.0),
                "price": float(item.get("price") or 0.0),
                "tax_net_price": float(item.get("tax_net_price") or 0.0),
                "project_number": str(item.get("project_number") or "").strip(),
            }
        )

    return {
        "items": items,
        "page": page,
        "page_size": page_size,
        "has_more": has_more,
    }


def _query_material_list(db: Session, keyword: str, limit: int) -> list[dict[str, Any]]:
    query = (
        db.query(
            PurchaseOrderSummary.material_code,
            PurchaseOrderSummary.material_name,
            Material.specification,
            func.sum(PurchaseOrderSummary.order_count).label("count"),
        )
        .outerjoin(Material, PurchaseOrderSummary.material_code == Material.code)
        .filter(PurchaseOrderSummary.material_name.isnot(None), PurchaseOrderSummary.material_name != "")
    )

    if keyword:
        like_pattern = f"%{keyword}%"
        query = query.filter(
            or_(
                PurchaseOrderSummary.material_code.ilike(like_pattern),
                PurchaseOrderSummary.material_name.ilike(like_pattern),
                Material.specification.ilike(like_pattern),
            )
        )

    rows = (
        query.group_by(PurchaseOrderSummary.material_code, PurchaseOrderSummary.material_name, Material.specification)
        .order_by(desc("count"))
        .limit(limit)
        .all()
    )

    return [
        {
            "material_code": row.material_code,
            "material_name": row.material_name,
            "material_model": row.specification,
            "count": int(row.count or 0),
        }
        for row in rows
    ]


def _build_material_analysis_payload(db: Session, material_code: str) -> dict[str, Any]:
    records = (
        db.query(
            PurchaseOrderSummary,
            Supplier.grade.label("supplier_grade"),
        )
        .outerjoin(Supplier, PurchaseOrderSummary.supplier_name == Supplier.name)
        .filter(PurchaseOrderSummary.material_code == material_code)
        .order_by(PurchaseOrderSummary.latest_date.desc())
        .all()
    )
    monthly_records = (
        db.query(PurchaseOrderMonthlyStat)
        .filter(PurchaseOrderMonthlyStat.material_code == material_code)
        .order_by(PurchaseOrderMonthlyStat.stat_month.asc())
        .all()
    )

    if not records:
        return {"kpi": {}, "trend": [], "supplier_share": [], "history": [], "all_suppliers": []}

    total_qty = sum(float(row[0].total_qty or 0) for row in records)
    total_amount = sum(float(row[0].total_amount or 0) for row in records)
    suppliers_set = {row[0].supplier_name for row in records if row[0].supplier_name}
    valid_prices = [row for row in records if row[0].lowest_price and row[0].lowest_price > 0]
    latest_lowest = min(valid_prices, key=lambda item: item[0].lowest_price) if valid_prices else None

    kpi = {
        "total_amount": total_amount,
        "total_qty": total_qty,
        "supplier_count": len(suppliers_set),
        "avg_price": total_amount / total_qty if total_qty > 0 else 0.0,
        "lowest_price": latest_lowest[0].lowest_price if latest_lowest else 0.0,
        "lowest_supplier": latest_lowest[0].supplier_name if latest_lowest else "-",
    }

    share_dict: defaultdict[str, float] = defaultdict(float)
    for row, _grade in records:
        if row.supplier_name:
            share_dict[row.supplier_name] += float(row.total_amount or 0.0)

    supplier_share_list = [{"name": key, "value": value} for key, value in share_dict.items() if value > 0]
    supplier_share_list.sort(key=lambda item: item["value"], reverse=True)
    all_suppliers = list({row[0].supplier_name for row in records if row[0].supplier_name})
    history_suppliers = []
    seen_history_supplier_codes: set[str] = set()
    for row, grade in records:
        supplier_code = str(row.supplier_code or "").strip()
        supplier_name = str(row.supplier_name or "").strip()
        unique_key = supplier_code or supplier_name
        if not unique_key or unique_key in seen_history_supplier_codes:
            continue
        seen_history_supplier_codes.add(unique_key)
        history_suppliers.append(
            {
                "code": supplier_code,
                "name": supplier_name,
                "grade": grade,
            }
        )

    final_supplier_share: list[dict[str, Any]] = []
    other_value = 0.0
    for index, item in enumerate(supplier_share_list):
        if index < 5:
            final_supplier_share.append(item)
        else:
            other_value += item["value"]
    if other_value > 0:
        final_supplier_share.append({"name": "其他", "value": other_value})

    detail_rows: list[dict[str, Any]] = []
    try:
        detail_rows = _fetch_material_history_details(material_code)
    except Exception:
        logger.exception("Fetch material detail history failed, material_code=%s", material_code)

    grade_map = {
        str(row.supplier_name or "").strip(): grade
        for row, grade in records
        if row.supplier_name
    }

    trend = []
    history = []
    for item in detail_rows:
        supplier_name = str(item.get("supplier_name") or "").strip()
        trend.append(
            {
                "date": str(item.get("date") or "")[:10],
                "supplier": supplier_name,
                "price": float(item.get("tax_net_price") or 0.0),
                "bill_no": str(item.get("bill_no") or "").strip(),
            }
        )
        history.append(
            {
                "date": str(item.get("date") or "")[:10],
                "bill_no": str(item.get("bill_no") or "").strip(),
                "supplier_code": str(item.get("supplier_code") or "").strip(),
                "supplier_name": supplier_name,
                "supplier_grade": grade_map.get(supplier_name),
                "qty": float(item.get("qty") or 0.0),
                "price": float(item.get("price") or 0.0),
                "tax_net_price": float(item.get("tax_net_price") or 0.0),
                "project_number": str(item.get("project_number") or "").strip(),
            }
        )

    if not trend:
        trend = [
            {
                "date": row.stat_month.strftime("%Y-%m-%d") if row.stat_month else "",
                "supplier": row.supplier_name,
                "price": float(row.avg_tax_net_price or 0.0),
                "bill_no": "",
            }
            for row in monthly_records
        ]

    if not history:
        history = [
            {
                "date": row.latest_date.strftime("%Y-%m-%d") if row.latest_date else "",
                "bill_no": "统计汇总",
                "supplier_code": str(row.supplier_code or "").strip(),
                "supplier_name": row.supplier_name,
                "supplier_grade": grade,
                "qty": float(row.total_qty or 0.0),
                "price": float(row.avg_price or 0.0),
                "tax_net_price": float(row.avg_tax_net_price or 0.0),
                "project_number": "",
            }
            for row, grade in records
        ]

    return {
        "kpi": kpi,
        "trend": trend,
        "supplier_share": final_supplier_share,
        "history": history,
        "all_suppliers": all_suppliers,
        "history_suppliers": history_suppliers,
    }


def _refresh_material_list_cache(keyword: str, limit: int) -> None:
    db = next(get_db())
    try:
        data = _query_material_list(db, keyword, limit)
        if not data and not keyword and not db.query(PurchaseOrderSummary.id).first():
            sync_recent_po_history_for_analysis(months_back=12)
            data = _query_material_list(db, keyword, limit)
        save_cached_data(_material_list_cache_key(keyword, limit), data, ttl=_MATERIAL_LIST_CACHE_TTL)
    except Exception:
        logger.exception("Background material list refresh failed")
    finally:
        db.close()


def _refresh_material_analysis_cache(material_code: str) -> None:
    db = next(get_db())
    try:
        payload = _build_material_analysis_payload(db, material_code)
        if not payload.get("history") or not payload.get("trend"):
            sync_recent_po_history_for_analysis(material_code=material_code, months_back=12)
            payload = _build_material_analysis_payload(db, material_code)
        save_cached_data(_material_analysis_cache_key(material_code), payload, ttl=_MATERIAL_ANALYSIS_CACHE_TTL)
    except Exception:
        logger.exception("Background material analysis refresh failed, material_code=%s", material_code)
    finally:
        db.close()


def _refresh_material_history_cache(
    material_code: str,
    supplier_code: str,
    start_date: str,
    end_date: str,
    page: int,
    page_size: int,
) -> None:
    db = next(get_db())
    try:
        payload = _build_material_history_payload(
            db,
            material_code=material_code,
            supplier_code=supplier_code or None,
            start_date=start_date or None,
            end_date=end_date or None,
            page=page,
            page_size=page_size,
        )
        save_cached_data(
            _material_history_cache_key(material_code, supplier_code, start_date, end_date, page, page_size),
            payload,
            ttl=_MATERIAL_HISTORY_CACHE_TTL,
        )
    except Exception:
        logger.exception(
            "Background material history refresh failed, material_code=%s supplier_code=%s page=%s",
            material_code,
            supplier_code,
            page,
        )
    finally:
        db.close()


@router.get("/list")
def get_material_list(
    keyword: str = Query("", description="物料编码/名称/规格型号关键字"),
    limit: int = Query(5000, ge=1, le=5000),
    force_refresh: bool = Query(False, description="是否强制刷新缓存"),
    background_tasks: BackgroundTasks = None,
    response: Response = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    _require_buyer_or_admin(current_user)
    keyword = (keyword or "").strip()
    cache_key = _material_list_cache_key(keyword, limit)
    entry = None if force_refresh else load_cache_entry(cache_key)

    if entry:
        if response:
            response.headers["X-Cache"] = "HIT"
        if background_tasks and should_refresh_cache(entry, _MATERIAL_LIST_SOFT_TTL):
            background_tasks.add_task(_refresh_material_list_cache, keyword, limit)
        return entry["data"]

    rows = _query_material_list(db, keyword, limit)
    if not rows and not keyword:
        summary_exists = db.query(PurchaseOrderSummary.id).first()
        if not summary_exists:
            try:
                sync_recent_po_history_for_analysis(months_back=12)
            except Exception:
                logger.exception("Auto sync recent PO history for material list failed")
            rows = _query_material_list(db, keyword, limit)

    save_cached_data(cache_key, rows, ttl=_MATERIAL_LIST_CACHE_TTL)
    if response:
        response.headers["X-Cache"] = "MISS"
    return rows


@router.get("/analysis")
def get_material_analysis(
    material_code: str = Query(..., min_length=1),
    force_refresh: bool = Query(False, description="是否强制刷新缓存"),
    background_tasks: BackgroundTasks = None,
    response: Response = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    _require_buyer_or_admin(current_user)
    material_code = material_code.strip()
    cache_key = _material_analysis_cache_key(material_code)
    entry = None if force_refresh else load_cache_entry(cache_key)

    if entry:
        if response:
            response.headers["X-Cache"] = "HIT"
        if background_tasks and should_refresh_cache(entry, _MATERIAL_ANALYSIS_SOFT_TTL):
            background_tasks.add_task(_refresh_material_analysis_cache, material_code)
        return entry["data"]

    payload = _build_material_analysis_payload(db, material_code)
    if not payload.get("history") or not payload.get("trend"):
        try:
            sync_recent_po_history_for_analysis(material_code=material_code, months_back=12)
        except Exception:
            logger.exception("Auto sync recent PO history for material analysis failed, material_code=%s", material_code)
        payload = _build_material_analysis_payload(db, material_code)

    save_cached_data(cache_key, payload, ttl=_MATERIAL_ANALYSIS_CACHE_TTL)
    if response:
        response.headers["X-Cache"] = "MISS"
    return payload


@router.get("/analysis/history")
def get_material_analysis_history(
    material_code: str = Query(..., min_length=1),
    supplier_code: str = Query(""),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    force_refresh: bool = Query(False, description="是否强制刷新缓存"),
    background_tasks: BackgroundTasks = None,
    response: Response = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    _require_buyer_or_admin(current_user)
    material_code = material_code.strip()
    normalized_supplier_code = (supplier_code or "").strip()
    normalized_start = (start_date or "").strip()
    normalized_end = (end_date or "").strip()
    cache_key = _material_history_cache_key(
        material_code,
        normalized_supplier_code,
        normalized_start,
        normalized_end,
        page,
        page_size,
    )
    entry = None if force_refresh else load_cache_entry(cache_key)

    if entry:
        if response:
            response.headers["X-Cache"] = "HIT"
        if background_tasks and should_refresh_cache(entry, _MATERIAL_HISTORY_SOFT_TTL):
            background_tasks.add_task(
                _refresh_material_history_cache,
                material_code,
                normalized_supplier_code,
                normalized_start,
                normalized_end,
                page,
                page_size,
            )
        return entry["data"]

    payload = _build_material_history_payload(
        db,
        material_code=material_code,
        supplier_code=normalized_supplier_code or None,
        start_date=normalized_start or None,
        end_date=normalized_end or None,
        page=page,
        page_size=page_size,
    )
    save_cached_data(cache_key, payload, ttl=_MATERIAL_HISTORY_CACHE_TTL)
    if response:
        response.headers["X-Cache"] = "MISS"
    return payload
