import logging
from typing import Any, List

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Response
from requests import exceptions as requests_exceptions
from sqlalchemy.orm import Session

from kingdee_erp_tool.services.purchase import (
    get_historical_purchase_prices,
    get_processed_purchase_data,
)
from models import InquiryStatus, get_db
from schemas import InquiryRequest as InquiryRequestSchema
from services.cache_service import load_cache_entry, save_cached_data, should_refresh_cache

router = APIRouter()
logger = logging.getLogger(__name__)

_REQUISITION_CACHE_TTL = 300
_REQUISITION_SOFT_TTL = 60
_PO_HISTORY_CACHE_TTL = 1800
_PO_HISTORY_SOFT_TTL = 180


def _cache_key(keyword: str | None, bill_type_id: str | None, start_date: str | None, end_date: str | None) -> str:
    return f"{keyword or ''}|{bill_type_id or ''}|{start_date or ''}|{end_date or ''}"


def _requisition_redis_key(keyword: str | None, bill_type_id: str | None, start_date: str | None, end_date: str | None) -> str:
    return f"erp:requisitions:{_cache_key(keyword, bill_type_id, start_date, end_date)}"


def _po_history_redis_key(
    material_code: str | None,
    supplier_code: str | None,
    months_back: int,
    limit: int,
    start_date: str | None,
    end_date: str | None,
) -> str:
    return (
        "erp:po_history:"
        f"m:{material_code or ''}:s:{supplier_code or ''}:mb:{months_back}:"
        f"l:{limit}:sd:{start_date or ''}:ed:{end_date or ''}"
    )


def _build_display_items(erp_data: list[dict[str, Any]]) -> list[InquiryRequestSchema]:
    display_items: list[InquiryRequestSchema] = []
    for item in erp_data:
        bill_no = item.get("bill_no", "")
        material_id = item.get("material_id", "")
        unique_key = f"{bill_no}_{material_id}"
        display_items.append(
            InquiryRequestSchema(
                erp_request_id=unique_key,
                bill_no=bill_no,
                bill_type=item.get("bill_type"),
                project_info={
                    "number": item.get("project_number"),
                    "name": item.get("project_name"),
                },
                material_code=material_id,
                material_name=item.get("material_name"),
                material_model=item.get("material_model"),
                price_unit_name=item.get("price_unit_name"),
                qty=item.get("purchase_qty", 0),
                delivery_date=item.get("delivery_date"),
                purchaser_name=item.get("purchaser_name"),
                purchaser_detail_name=item.get("purchaser_detail_name"),
                purchaser_base_name=item.get("purchaser_base_name"),
                remark=item.get("remark"),
                remark_detail=item.get("remark_detail"),
                remark_base=item.get("remark_base"),
                technician_name=item.get("technician_name"),
                status=InquiryStatus.PENDING_POOL,
                id=None,
                created_at=item.get("created_date"),
            )
        )
    return display_items


def _refresh_requisition_cache(
    redis_key: str,
    keyword: str | None,
    bill_type_id: str | None,
    start_date: str | None,
    end_date: str | None,
) -> None:
    try:
        erp_data = get_processed_purchase_data(keyword, bill_type_id, start_date, end_date)
        new_items = _build_display_items(erp_data)
        old_entry = load_cache_entry(redis_key)
        old_items = (old_entry or {}).get("data") or []
        old_keys = [
            item.get("erp_request_id") if isinstance(item, dict) else getattr(item, "erp_request_id", None)
            for item in old_items
        ]
        new_keys = [item.erp_request_id for item in new_items]
        if old_keys != new_keys:
            save_cached_data(redis_key, new_items, ttl=_REQUISITION_CACHE_TTL)
            logger.info("Requisition cache updated for key=%s, count=%s", redis_key, len(new_items))
        else:
            save_cached_data(redis_key, old_items, ttl=_REQUISITION_CACHE_TTL)
    except Exception:
        logger.exception("Background requisition refresh failed, key=%s", redis_key)


def _refresh_po_history_cache(
    redis_key: str,
    material_code: str | None,
    supplier_code: str | None,
    months_back: int,
    limit: int,
    start_date: str | None,
    end_date: str | None,
) -> None:
    try:
        rows = get_historical_purchase_prices(
            material_code=material_code,
            supplier_code=supplier_code,
            months_back=months_back,
            limit=limit,
            start_date=start_date,
            end_date=end_date,
        )
        save_cached_data(redis_key, rows, ttl=_PO_HISTORY_CACHE_TTL)
    except Exception:
        logger.exception("Background PO history refresh failed, key=%s", redis_key)


@router.post("/requisitions", response_model=List[InquiryRequestSchema])
def sync_purchase_requisitions(
    keyword: str | None = None,
    bill_type_id: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    force_refresh: bool = Query(False, description="是否强制回源 ERP 刷新缓存"),
    background_tasks: BackgroundTasks = None,
    response: Response = None,
    db: Session = Depends(get_db),
) -> Any:
    del db
    redis_key = _requisition_redis_key(keyword, bill_type_id, start_date, end_date)
    entry = None if force_refresh else load_cache_entry(redis_key)

    if entry:
        if response:
            response.headers["X-Cache"] = "HIT"
        if background_tasks and should_refresh_cache(entry, _REQUISITION_SOFT_TTL):
            background_tasks.add_task(
                _refresh_requisition_cache,
                redis_key,
                keyword,
                bill_type_id,
                start_date,
                end_date,
            )
        return entry["data"]

    try:
        erp_data = get_processed_purchase_data(keyword, bill_type_id, start_date, end_date)
        display_items = _build_display_items(erp_data)
        save_cached_data(redis_key, display_items, ttl=_REQUISITION_CACHE_TTL)
        if response:
            response.headers["X-Cache"] = "MISS"
        return display_items
    except requests_exceptions.RequestException as exc:
        logger.exception("ERP requisition request failed")
        stale_entry = load_cache_entry(redis_key)
        if stale_entry:
            if response:
                response.headers["X-Cache"] = "STALE"
            return stale_entry["data"]
        raise HTTPException(
            status_code=502,
            detail=f"无法连接 ERP 服务，请检查网络、代理或 ERP 地址配置。原始错误: {exc}",
        )
    except Exception as exc:
        logger.exception("ERP requisition sync failed")
        message = str(exc).strip() or "ERP 返回异常，请稍后重试"
        raise HTTPException(status_code=500, detail=f"ERP 同步失败: {message}")


@router.get("/po_history")
def get_po_history(
    material_code: str | None = None,
    supplier_code: str | None = None,
    months_back: int = 12,
    limit: int = 100,
    start_date: str | None = None,
    end_date: str | None = None,
    force_refresh: bool = Query(False, description="是否强制回源 ERP 刷新缓存"),
    background_tasks: BackgroundTasks = None,
    response: Response = None,
) -> Any:
    redis_key = _po_history_redis_key(material_code, supplier_code, months_back, limit, start_date, end_date)
    entry = None if force_refresh else load_cache_entry(redis_key)

    if entry:
        if response:
            response.headers["X-Cache"] = "HIT"
        if background_tasks and should_refresh_cache(entry, _PO_HISTORY_SOFT_TTL):
            background_tasks.add_task(
                _refresh_po_history_cache,
                redis_key,
                material_code,
                supplier_code,
                months_back,
                limit,
                start_date,
                end_date,
            )
        return entry["data"]

    try:
        rows = get_historical_purchase_prices(
            material_code=material_code,
            supplier_code=supplier_code,
            months_back=months_back,
            limit=limit,
            start_date=start_date,
            end_date=end_date,
        )
        save_cached_data(redis_key, rows, ttl=_PO_HISTORY_CACHE_TTL)
        if response:
            response.headers["X-Cache"] = "MISS"
        return rows
    except requests_exceptions.RequestException as exc:
        logger.exception("ERP PO history request failed")
        stale_entry = load_cache_entry(redis_key)
        if stale_entry:
            if response:
                response.headers["X-Cache"] = "STALE"
            return stale_entry["data"]
        raise HTTPException(
            status_code=502,
            detail=f"无法连接 ERP 服务，请检查网络、代理或 ERP 地址配置。原始错误: {exc}",
        )
    except Exception as exc:
        logger.exception("Get PO history failed")
        raise HTTPException(status_code=500, detail=f"Failed to fetch PO history: {exc}")
