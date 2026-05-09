from fastapi import APIRouter
from typing import List, Any
from datetime import datetime

from kingdee_getdata.login.session import session
from kingdee_getdata.getdata.GetPoData import get_po_data

router = APIRouter()


def build_warning_data(rows: List[List[Any]]):
    supplier_unreceived = []
    warehouse_unstockin = []

    for r in rows:
        # 新增了 FBILLNO 在最前面，所以后面的索引全部后移一位
        bill_no = r[0] if len(r) > 0 else ""
        project_number = r[1] if len(r) > 1 else ""
        supplier_id = r[2] if len(r) > 2 else ""
        material_id = r[3] if len(r) > 3 else ""
        material_name = r[4] if len(r) > 4 else ""
        qty = float(r[5]) if len(r) > 5 and r[5] else 0.0
        delivery_date = r[6] if len(r) > 6 else ""
        receive_qty = float(r[7]) if len(r) > 7 and r[7] else 0.0
        remain_receive_qty = float(r[8]) if len(r) > 8 and r[8] else 0.0 # 直接取 ERP 算好的剩余收料数量
        stockin_qty = float(r[9]) if len(r) > 9 and r[9] else 0.0
        remain_stockin_qty = float(r[10]) if len(r) > 10 and r[10] else 0.0 # 直接取 ERP 算好的剩余入库数量

        base_info = {
            "bill_no": bill_no,
            "project_number": project_number,
            "supplier_name": supplier_id,
            "material_id": material_id,
            "material_name": material_name,
            "delivery_date": delivery_date
        }

        # 只要 ERP 告诉我们供应商还没交齐，就加入预警
        if remain_receive_qty > 0:
            supplier_unreceived.append({
                **base_info,
                "purchase_qty": qty,
                "received_qty": receive_qty,
                "warning_unreceived_qty": remain_receive_qty
            })

        # 只要 ERP 告诉我们仓库还没入完，就加入预警
        if remain_stockin_qty > 0:
            warehouse_unstockin.append({
                **base_info,
                "received_qty": receive_qty,
                "stockin_qty": stockin_qty,
                "warning_unstockin_qty": remain_stockin_qty
            })

    return supplier_unreceived, warehouse_unstockin


@router.get("/warning")
def warning():
    """
    采购预警接口：
    - 供应商未到货
    - 仓库未入库
    """
    session()
    rows = get_po_data()

    supplier_unreceived, warehouse_unstockin = build_warning_data(rows)

    return {
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "supplier_unreceived": {
            "count": len(supplier_unreceived),
            "total_qty": sum(i["warning_unreceived_qty"] for i in supplier_unreceived),
            "list": supplier_unreceived
        },
        "warehouse_unstockin": {
            "count": len(warehouse_unstockin),
            "total_qty": sum(i["warning_unstockin_qty"] for i in warehouse_unstockin),
            "list": warehouse_unstockin
        }
    }
