from typing import Any
from collections import defaultdict
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, func, desc
from sqlalchemy.orm import Session

from models import (
    Supplier,
    User,
    Material,
    PurchaseOrderHistory,
    get_db,
)
from routers.inquiry import get_current_user

router = APIRouter()

def _require_buyer_or_admin(current_user: User):
    if current_user.role not in ["admin", "buyer"]:
        raise HTTPException(status_code=403, detail="Not authorized")

@router.get("/list")
def get_material_list(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    获取具有采购历史记录的物料列表（按采购次数倒序）
    """
    _require_buyer_or_admin(current_user)
    
    rows = (
        db.query(
            PurchaseOrderHistory.material_code,
            PurchaseOrderHistory.material_name,
            Material.specification,
            func.count(PurchaseOrderHistory.id).label("count")
        )
        .outerjoin(Material, PurchaseOrderHistory.material_code == Material.code)
        .filter(PurchaseOrderHistory.material_name != None, PurchaseOrderHistory.material_name != '')
        .group_by(PurchaseOrderHistory.material_code, PurchaseOrderHistory.material_name, Material.specification)
        .order_by(desc("count"))
        .all()
    )
    
    return [
        {
            "material_code": r.material_code,
            "material_name": r.material_name,
            "material_model": r.specification,
            "count": r.count
        }
        for r in rows
    ]

@router.get("/analysis")
def get_material_analysis(
    material_code: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    获取特定物料的多供应商比价分析数据
    """
    _require_buyer_or_admin(current_user)
    
    # 获取该物料的所有采购历史，关联供应商以获取等级
    records = (
        db.query(
            PurchaseOrderHistory,
            Supplier.grade.label("supplier_grade")
        )
        .outerjoin(Supplier, PurchaseOrderHistory.supplier_name == Supplier.name)
        .filter(PurchaseOrderHistory.material_code == material_code)
        .order_by(PurchaseOrderHistory.date.desc())
        .all()
    )
    
    if not records:
        return {"kpi": {}, "trend": [], "supplier_share": [], "history": []}

    # --- 1. 计算核心 KPI ---
    total_qty = sum(r[0].qty for r in records if r[0].qty)
    total_amount = sum((r[0].qty or 0) * (r[0].tax_net_price or 0) for r in records)
    suppliers_set = {r[0].supplier_name for r in records if r[0].supplier_name}
    
    # 查找最近的最低价
    # 我们按日期从新到旧找最近半年/或者所有记录中的最低价
    valid_prices = [r for r in records if r[0].tax_net_price and r[0].tax_net_price > 0]
    latest_lowest = min(valid_prices, key=lambda x: x[0].tax_net_price) if valid_prices else None
    
    kpi = {
        "total_amount": total_amount,
        "total_qty": total_qty,
        "supplier_count": len(suppliers_set),
        "avg_price": total_amount / total_qty if total_qty > 0 else 0.0,
        "lowest_price": latest_lowest[0].tax_net_price if latest_lowest else 0.0,
        "lowest_supplier": latest_lowest[0].supplier_name if latest_lowest else "-"
    }
    
    # --- 2. 预计算份额以获取 Top 供应商 ---
    share_dict = defaultdict(float)
    for r in records:
        if r[0].supplier_name:
            qty = float(r[0].qty) if r[0].qty else 0.0
            tax_net_price = float(r[0].tax_net_price) if r[0].tax_net_price else 0.0
            share_dict[r[0].supplier_name] += (qty * tax_net_price)
            
    supplier_share_list = [{"name": k, "value": v} for k, v in share_dict.items() if v > 0]
    supplier_share_list.sort(key=lambda x: x["value"], reverse=True)
    
    # 获取所有有关联的供应商名称，供前端筛选使用
    all_suppliers = list({r[0].supplier_name for r in records if r[0].supplier_name})
    
    # 饼图展示前5，其他归类
    final_supplier_share = []
    other_value = 0.0
    for i, s in enumerate(supplier_share_list):
        if i < 5:
            final_supplier_share.append(s)
        else:
            other_value += s["value"]
            
    if other_value > 0:
        final_supplier_share.append({"name": "其他", "value": other_value})
    
    # --- 3. 构建趋势图和交易明细 ---
    trend = []
    history = []
    MAX_HISTORY = 1000 # 限制明细数量，防止前端表格卡顿
    
    for po, grade in records:
        date_str = po.date.strftime("%Y-%m-%d") if po.date else ""
        price = float(po.price) if po.price else 0.0
        tax_net_price = float(po.tax_net_price) if po.tax_net_price else 0.0
        qty = float(po.qty) if po.qty else 0.0
        
        # 趋势图返回全量（或限制数量），让前端可自由选择
        if len(trend) < MAX_HISTORY:
            trend.append({
                "date": date_str,
                "supplier": po.supplier_name,
                "price": tax_net_price,
                "bill_no": po.bill_no
            })
            
        if len(history) < MAX_HISTORY:
            history.append({
                "date": date_str,
                "bill_no": po.bill_no,
                "supplier_name": po.supplier_name,
                "supplier_grade": grade,
                "qty": qty,
                "price": price,
                "tax_net_price": tax_net_price
            })

    return {
        "kpi": kpi,
        "trend": trend,
        "supplier_share": final_supplier_share,
        "history": history,
        "all_suppliers": all_suppliers
    }
