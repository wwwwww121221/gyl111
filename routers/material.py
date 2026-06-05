from collections import defaultdict
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, func, or_
from sqlalchemy.orm import Session

from models import Material, PurchaseOrderMonthlyStat, PurchaseOrderSummary, Supplier, User, get_db
from routers.inquiry import get_current_user

router = APIRouter()


def _require_buyer_or_admin(current_user: User):
    if current_user.role not in ["admin", "buyer", "buyer_manager"]:
        raise HTTPException(status_code=403, detail="Not authorized")


@router.get("/list")
def get_material_list(
    keyword: str = Query("", description="物料编码/名称/规格型号关键词"),
    limit: int = Query(5000, ge=1, le=5000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_buyer_or_admin(current_user)

    keyword = (keyword or "").strip()
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
            "material_code": r.material_code,
            "material_name": r.material_name,
            "material_model": r.specification,
            "count": int(r.count or 0),
        }
        for r in rows
    ]


@router.get("/analysis")
def get_material_analysis(
    material_code: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    _require_buyer_or_admin(current_user)

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

    total_qty = sum(float(r[0].total_qty or 0) for r in records)
    total_amount = sum(float(r[0].total_amount or 0) for r in records)
    suppliers_set = {r[0].supplier_name for r in records if r[0].supplier_name}
    valid_prices = [r for r in records if r[0].lowest_price and r[0].lowest_price > 0]
    latest_lowest = min(valid_prices, key=lambda x: x[0].lowest_price) if valid_prices else None

    kpi = {
        "total_amount": total_amount,
        "total_qty": total_qty,
        "supplier_count": len(suppliers_set),
        "avg_price": total_amount / total_qty if total_qty > 0 else 0.0,
        "lowest_price": latest_lowest[0].lowest_price if latest_lowest else 0.0,
        "lowest_supplier": latest_lowest[0].supplier_name if latest_lowest else "-",
    }

    share_dict = defaultdict(float)
    for row, _ in records:
        if row.supplier_name:
            share_dict[row.supplier_name] += float(row.total_amount or 0.0)

    supplier_share_list = [{"name": k, "value": v} for k, v in share_dict.items() if v > 0]
    supplier_share_list.sort(key=lambda x: x["value"], reverse=True)
    all_suppliers = list({r[0].supplier_name for r in records if r[0].supplier_name})

    final_supplier_share = []
    other_value = 0.0
    for i, item in enumerate(supplier_share_list):
        if i < 5:
            final_supplier_share.append(item)
        else:
            other_value += item["value"]
    if other_value > 0:
        final_supplier_share.append({"name": "鍏朵粬", "value": other_value})

    trend = []
    history = []
    for row in monthly_records:
        trend.append({
            "date": row.stat_month.strftime("%Y-%m-%d") if row.stat_month else "",
            "supplier": row.supplier_name,
            "price": float(row.avg_tax_net_price or 0.0),
            "bill_no": "",
        })

    for row, grade in records:
        history.append({
            "date": row.latest_date.strftime("%Y-%m-%d") if row.latest_date else "",
            "bill_no": "统计汇总",
            "supplier_name": row.supplier_name,
            "supplier_grade": grade,
            "qty": float(row.total_qty or 0.0),
            "price": float(row.avg_price or 0.0),
            "tax_net_price": float(row.avg_tax_net_price or 0.0),
        })

    return {
        "kpi": kpi,
        "trend": trend,
        "supplier_share": final_supplier_share,
        "history": history,
        "all_suppliers": all_suppliers,
    }
