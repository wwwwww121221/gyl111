from __future__ import annotations

import re
from typing import Any

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, or_
from sqlalchemy.orm import Session

from kingdee_erp_tool.services.purchase import search_purchase_orders as erp_search_purchase_orders
from models import InquiryRequest, Material, PurchaseOrderMonthlyStat, PurchaseOrderSummary, Supplier


class SearchMaterialInput(BaseModel):
    keyword: str = Field(..., description="Material code, material name, specification or group keyword.")
    limit: int = Field(default=5, ge=1, le=20, description="Maximum number of rows to return.")


class SearchSuppliersInput(BaseModel):
    keyword: str = Field(..., description="Supplier code, name, short name, group or grade keyword.")
    limit: int = Field(default=8, ge=1, le=20, description="Maximum number of rows to return.")


class MaterialPriceHistoryInput(BaseModel):
    material_code: str | None = Field(default=None, description="Exact material code.")
    material_name: str | None = Field(default=None, description="Material name keyword when code is unknown.")
    limit: int = Field(default=10, ge=1, le=30, description="Maximum supplier history rows to return.")


class SupplierPurchaseProfileInput(BaseModel):
    supplier_code: str | None = Field(default=None, description="Exact supplier code.")
    supplier_name: str | None = Field(default=None, description="Supplier name keyword when code is unknown.")
    limit: int = Field(default=10, ge=1, le=30, description="Maximum material rows to return.")


class PurchaseRequestSearchInput(BaseModel):
    keyword: str | None = Field(default=None, description="Material code, material name, model or bill number keyword.")
    material_code: str | None = Field(default=None, description="Exact material code.")
    material_name: str | None = Field(default=None, description="Material name keyword.")
    limit: int = Field(default=10, ge=1, le=30, description="Maximum purchase request rows to return.")


class PurchaseOrderSearchInput(BaseModel):
    keyword: str | None = Field(default=None, description="Purchase order number, material, or supplier keyword.")
    material_code: str | None = Field(default=None, description="Exact material code.")
    supplier_code: str | None = Field(default=None, description="Exact supplier code.")
    start_date: str | None = Field(default=None, description="Start date in YYYY-MM-DD or YYYY-MM-DDTHH:mm:ss.")
    end_date: str | None = Field(default=None, description="End date in YYYY-MM-DD or YYYY-MM-DDTHH:mm:ss.")
    limit: int = Field(default=10, ge=1, le=50, description="Maximum purchase order rows to return.")


def _like(value: str) -> str:
    return f"%{str(value or '').strip()}%"


def _trimmed(value: Any) -> str:
    return str(value or "").strip()


def _format_date(value: Any) -> str:
    return value.strftime("%Y-%m-%d") if value else ""


def extract_possible_codes(text: str) -> list[str]:
    # ERP material/supplier codes are usually latin letters, numbers, hyphen,
    # dot or underscore. Keep this intentionally conservative.
    candidates = re.findall(r"[A-Za-z0-9][A-Za-z0-9._/-]{2,}", text or "")
    seen = set()
    result = []
    for item in candidates:
        normalized = item.strip(".,;:，。；：()（）[]【】")
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(normalized)
    return result[:5]


def search_material(db: Session, args: dict[str, Any]) -> dict[str, Any]:
    keyword = _trimmed(args.get("keyword"))
    limit = int(args.get("limit") or 5)
    query = db.query(Material)
    if keyword:
        pattern = _like(keyword)
        query = query.filter(or_(
            Material.code.ilike(pattern),
            Material.name.ilike(pattern),
            Material.specification.ilike(pattern),
            Material.group_name.ilike(pattern),
        ))
    rows = query.order_by(Material.code.asc()).limit(limit).all()
    return {
        "items": [
            {
                "id": row.id,
                "code": row.code,
                "name": row.name,
                "specification": row.specification,
                "group_name": row.group_name,
                "base_unit": row.base_unit,
            }
            for row in rows
        ],
        "count": len(rows),
    }


def search_suppliers(db: Session, args: dict[str, Any]) -> dict[str, Any]:
    keyword = _trimmed(args.get("keyword"))
    limit = int(args.get("limit") or 8)
    query = db.query(Supplier)
    if keyword:
        pattern = _like(keyword)
        query = query.filter(or_(
            Supplier.code.ilike(pattern),
            Supplier.name.ilike(pattern),
            Supplier.short_name.ilike(pattern),
            Supplier.group_name.ilike(pattern),
            Supplier.grade.ilike(pattern),
        ))
    rows = query.order_by(Supplier.status.asc(), Supplier.name.asc()).limit(limit).all()
    return {
        "items": [
            {
                "id": row.id,
                "code": row.code,
                "name": row.name,
                "short_name": row.short_name,
                "group_name": row.group_name,
                "grade": row.grade,
                "level": row.level,
                "status": row.status,
                "rating_score": row.rating_score,
            }
            for row in rows
        ],
        "count": len(rows),
    }


def search_purchase_requests(db: Session, args: dict[str, Any]) -> dict[str, Any]:
    keyword = _trimmed(args.get("keyword"))
    material_code = _trimmed(args.get("material_code"))
    material_name = _trimmed(args.get("material_name"))
    limit = int(args.get("limit") or 10)

    query = db.query(InquiryRequest)
    filters = []
    if material_code:
        filters.append(func.trim(InquiryRequest.material_code) == material_code)
    if material_name:
        filters.append(InquiryRequest.material_name.ilike(_like(material_name)))
    if keyword:
        pattern = _like(keyword)
        filters.append(or_(
            InquiryRequest.material_code.ilike(pattern),
            InquiryRequest.material_name.ilike(pattern),
            InquiryRequest.material_model.ilike(pattern),
            InquiryRequest.bill_no.ilike(pattern),
            InquiryRequest.erp_request_id.ilike(pattern),
        ))
    if filters:
        query = query.filter(or_(*filters))

    rows = (
        query
        .order_by(desc(InquiryRequest.created_at), desc(InquiryRequest.delivery_date), desc(InquiryRequest.id))
        .limit(limit)
        .all()
    )
    return {
        "items": [
            {
                "id": row.id,
                "erp_request_id": row.erp_request_id,
                "bill_no": row.bill_no,
                "material_code": row.material_code,
                "material_name": row.material_name,
                "material_model": row.material_model,
                "price_unit_name": row.price_unit_name,
                "qty": row.qty,
                "target_price": row.target_price,
                "delivery_date": _format_date(row.delivery_date),
                "status": row.status,
                "created_at": _format_date(row.created_at),
                "project_info": row.project_info,
            }
            for row in rows
        ],
        "count": len(rows),
    }


def search_purchase_orders(db: Session, args: dict[str, Any]) -> dict[str, Any]:
    keyword = _trimmed(args.get("keyword"))
    material_code = _trimmed(args.get("material_code"))
    supplier_code = _trimmed(args.get("supplier_code"))
    start_date = _trimmed(args.get("start_date"))
    end_date = _trimmed(args.get("end_date"))
    limit = int(args.get("limit") or 10)

    rows = erp_search_purchase_orders(
        keyword=keyword or None,
        material_code=material_code or None,
        supplier_code=supplier_code or None,
        start_date=start_date or None,
        end_date=end_date or None,
        limit=limit,
    )
    return {
        "items": rows,
        "count": len(rows),
    }


def get_material_price_history(db: Session, args: dict[str, Any]) -> dict[str, Any]:
    material_code = _trimmed(args.get("material_code"))
    material_name = _trimmed(args.get("material_name"))
    limit = int(args.get("limit") or 10)

    query = db.query(PurchaseOrderSummary)
    if material_code:
        query = query.filter(func.trim(PurchaseOrderSummary.material_code) == material_code)
    elif material_name:
        query = query.filter(PurchaseOrderSummary.material_name.ilike(_like(material_name)))
    else:
        return {"items": [], "monthly_trend": [], "count": 0}

    rows = (
        query
        .order_by(desc(PurchaseOrderSummary.order_count), desc(PurchaseOrderSummary.latest_date))
        .limit(limit)
        .all()
    )

    trend_code = material_code or (_trimmed(rows[0].material_code) if rows else "")
    monthly_rows = []
    if trend_code:
        monthly_rows = (
            db.query(PurchaseOrderMonthlyStat)
            .filter(func.trim(PurchaseOrderMonthlyStat.material_code) == trend_code)
            .order_by(PurchaseOrderMonthlyStat.stat_month.asc())
            .limit(18)
            .all()
        )

    return {
        "items": [
            {
                "supplier_code": row.supplier_code,
                "supplier_name": row.supplier_name,
                "material_code": row.material_code,
                "material_name": row.material_name,
                "order_count": row.order_count,
                "total_qty": row.total_qty,
                "avg_tax_net_price": row.avg_tax_net_price,
                "latest_tax_net_price": row.latest_tax_net_price,
                "latest_date": _format_date(row.latest_date),
                "lowest_price": row.lowest_price,
                "lowest_date": _format_date(row.lowest_date),
                "highest_price": row.highest_price,
                "highest_date": _format_date(row.highest_date),
                "avg_30_days": row.avg_30_days,
            }
            for row in rows
        ],
        "monthly_trend": [
            {
                "month": row.stat_month.strftime("%Y-%m") if row.stat_month else "",
                "supplier_code": row.supplier_code,
                "supplier_name": row.supplier_name,
                "order_count": row.order_count,
                "avg_tax_net_price": row.avg_tax_net_price,
                "min_tax_net_price": row.min_tax_net_price,
                "max_tax_net_price": row.max_tax_net_price,
            }
            for row in monthly_rows
        ],
        "count": len(rows),
    }


def get_supplier_purchase_profile(db: Session, args: dict[str, Any]) -> dict[str, Any]:
    supplier_code = _trimmed(args.get("supplier_code"))
    supplier_name = _trimmed(args.get("supplier_name"))
    limit = int(args.get("limit") or 10)

    supplier = None
    if supplier_code:
        supplier = db.query(Supplier).filter(Supplier.code == supplier_code).first()
    if not supplier and supplier_name:
        supplier = db.query(Supplier).filter(Supplier.name.ilike(_like(supplier_name))).first()

    query = db.query(PurchaseOrderSummary)
    if supplier_code:
        query = query.filter(PurchaseOrderSummary.supplier_code == supplier_code)
    elif supplier:
        query = query.filter(PurchaseOrderSummary.supplier_code == supplier.code)
    elif supplier_name:
        query = query.filter(PurchaseOrderSummary.supplier_name.ilike(_like(supplier_name)))
    else:
        return {"supplier": None, "materials": [], "count": 0}

    rows = query.order_by(desc(PurchaseOrderSummary.total_amount)).limit(limit).all()
    return {
        "supplier": {
            "id": supplier.id,
            "code": supplier.code,
            "name": supplier.name,
            "grade": supplier.grade,
            "level": supplier.level,
            "status": supplier.status,
            "rating_score": supplier.rating_score,
        } if supplier else None,
        "materials": [
            {
                "material_code": row.material_code,
                "material_name": row.material_name,
                "order_count": row.order_count,
                "total_qty": row.total_qty,
                "total_amount": row.total_amount,
                "avg_tax_net_price": row.avg_tax_net_price,
                "latest_date": _format_date(row.latest_date),
            }
            for row in rows
        ],
        "count": len(rows),
    }


def create_langchain_tools(db: Session) -> dict[str, StructuredTool]:
    """Create request-scoped LangChain tools.

    The SQLAlchemy session is injected by closure, so the model never receives
    database credentials. Each tool is read-only in this first agent version.
    """

    def _search_material(keyword: str, limit: int = 5) -> dict[str, Any]:
        return search_material(db, {"keyword": keyword, "limit": limit})

    def _search_suppliers(keyword: str, limit: int = 8) -> dict[str, Any]:
        return search_suppliers(db, {"keyword": keyword, "limit": limit})

    def _get_material_price_history(
        material_code: str | None = None,
        material_name: str | None = None,
        limit: int = 10,
    ) -> dict[str, Any]:
        return get_material_price_history(db, {
            "material_code": material_code,
            "material_name": material_name,
            "limit": limit,
        })

    def _get_supplier_purchase_profile(
        supplier_code: str | None = None,
        supplier_name: str | None = None,
        limit: int = 10,
    ) -> dict[str, Any]:
        return get_supplier_purchase_profile(db, {
            "supplier_code": supplier_code,
            "supplier_name": supplier_name,
            "limit": limit,
        })

    def _search_purchase_requests(
        keyword: str | None = None,
        material_code: str | None = None,
        material_name: str | None = None,
        limit: int = 10,
    ) -> dict[str, Any]:
        return search_purchase_requests(db, {
            "keyword": keyword,
            "material_code": material_code,
            "material_name": material_name,
            "limit": limit,
        })

    def _search_purchase_orders(
        keyword: str | None = None,
        material_code: str | None = None,
        supplier_code: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int = 10,
    ) -> dict[str, Any]:
        return search_purchase_orders(db, {
            "keyword": keyword,
            "material_code": material_code,
            "supplier_code": supplier_code,
            "start_date": start_date,
            "end_date": end_date,
            "limit": limit,
        })

    tools = [
        StructuredTool.from_function(
            func=_search_purchase_orders,
            name="search_purchase_orders",
            description="查询 ERP 的采购订单明细（PUR_PurchaseOrder）。适合回答采购订单、下单记录、订单追溯、支付前关联订单核对等问题，可按订单号、物料、供应商和日期范围搜索。",
            args_schema=PurchaseOrderSearchInput,
        ),
        StructuredTool.from_function(
            func=_search_purchase_requests,
            name="search_purchase_requests",
            description="按物料编码、物料名称、规格型号或采购申请单号查询采购申请明细。适合回答最近采购申请、需求池、申请单状态和交付日期。",
            args_schema=PurchaseRequestSearchInput,
        ),
        StructuredTool.from_function(
            func=_search_material,
            name="search_material",
            description="按编码、名称、规格或分组查询物料主数据。适合先定位用户提到的物料。",
            args_schema=SearchMaterialInput,
        ),
        StructuredTool.from_function(
            func=_search_suppliers,
            name="search_suppliers",
            description="按编码、名称、简称、分组或等级查询供应商。适合查供应商档案和候选供应商。",
            args_schema=SearchSuppliersInput,
        ),
        StructuredTool.from_function(
            func=_get_material_price_history,
            name="get_material_price_history",
            description="查询物料历史采购价格、供应商供货情况和月度趋势。适合做询价推荐、比价和谈判建议。",
            args_schema=MaterialPriceHistoryInput,
        ),
        StructuredTool.from_function(
            func=_get_supplier_purchase_profile,
            name="get_supplier_purchase_profile",
            description="查询供应商档案及其历史供货物料概况。适合评估供应商供货范围和历史合作。",
            args_schema=SupplierPurchaseProfileInput,
        ),
    ]
    return {tool.name: tool for tool in tools}
