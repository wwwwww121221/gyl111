import datetime
from kingdee_erp_tool.core.client import client

BASE_WARNING_FIELDS = [
    "F_XJPJ_BASE.FNUMBER",
    "FSUPPLIERID.FNAME",
    "FMATERIALID.FNUMBER",
    "FMATERIALNAME",
]

WARNING_MODEL_FIELD_CANDIDATES = [
    "FMATERIALMODEL",
    "FMATERIALID.FSpecification",
]

WARNING_TAIL_FIELDS = [
    "FQTY",
    "FDELIVERYDATE",
    "FRECEIVEQTY",
    "FREMAINRECEIVEQTY",
    "FSTOCKINQTY",
    "FREMAINSTOCKINQTY",
]


def _build_warning_field_keys(material_model_field: str | None = None) -> str:
    field_keys = list(BASE_WARNING_FIELDS)
    if material_model_field:
        field_keys.append(material_model_field)
    field_keys.extend(WARNING_TAIL_FIELDS)
    return ",".join(field_keys)


def _is_query_error_response(rows) -> bool:
    if not isinstance(rows, list) or not rows:
        return False
    first = rows[0]
    if isinstance(first, list) and first:
        first = first[0]
    if not isinstance(first, dict):
        return False
    response_status = (((first.get("Result") or {}).get("ResponseStatus")) or {})
    return response_status.get("IsSuccess") is False


def get_purchase_order_data():
    """
    获取采购订单数据
    """
    now = datetime.datetime.now()
    now_str = now.strftime("%Y/%m/%d %H:%M:%S")
    future_time = now + datetime.timedelta(days=3)
    future_str = future_time.strftime("%Y/%m/%d %H:%M:%S")

    # 参数配置
    # 项目号F_XJPJ_BASE.FNUMBER、供应商名称FSUPPLIERID.FNAME、物料编码FMATERIALID.FNUMBER、物料名称FMATERIALNAME、采购数量FQTY、交货日期FDELIVERYDATE(大于现在时间、小于现在加三天）
    # 累计收料数量FRECEIVEQTY,剩余收料数量FREMAINRECEIVEQTY,累计入库数量FSTOCKINQTY,剩余入库数量FREMAINSTOCKINQTY
    para = {
        "FormId": "PUR_PurchaseOrder",
        "FilterString": [
            {"Left": "(", "FieldName": "FDELIVERYDATE", "Compare": ">=", "Value": now_str, "Right": ")", "Logic": "0"},
            {"Left": "(", "FieldName": "FDELIVERYDATE", "Compare": "<=", "Value": future_str, "Right": ")", "Logic": "0"},
            {"Left": "(", "FieldName": "FMRPCLOSESTATUS", "Compare": "=", "Value": "A", "Right": ")", "Logic": "0"}  # 业务关闭FMRPCLOSESTATUS(A正常、B业务关闭)
        ],
        "OrderString": "FDELIVERYDATE",
        "TopRowCount": 0,
        "StartRow": 0,
        "Limit": 1000,
        "SubSystemId": ""
    }

    # 优先尝试直接取规格型号；ERP不支持时自动回退，避免整页预警数据丢失
    for material_model_field in WARNING_MODEL_FIELD_CANDIDATES + [None]:
        query_para = dict(para)
        query_para["FieldKeys"] = _build_warning_field_keys(material_model_field)
        print(f"Executing query with params: {query_para}")
        try:
            rows = client.execute_query(query_para)
        except Exception as exc:
            print(f"Warning query failed with field {material_model_field}: {exc}")
            continue
        if _is_query_error_response(rows):
            print(f"Warning query failed with field {material_model_field}, fallback to next candidate.")
            continue
        return rows

    return []

def process_warning_data(rows):
    """
    处理采购预警数据：供应商未到货 & 仓库未入库
    """
    supplier_unreceived = []
    warehouse_unstockin = []

    if not isinstance(rows, list):
        print(f"Warning: Expected list of rows, got {type(rows)}: {rows}")
        return [], []

    print(f"Processing {len(rows)} rows...")

    for r in rows:
        try:
            # Check if row is valid list
            if not isinstance(r, list) or len(r) < 10:
                print(f"Skipping invalid row: {r}")
                continue

            project_number = r[0]
            supplier_id = r[1]
            material_id = r[2]
            material_name = r[3]
            has_material_model = len(r) >= 11
            material_model = r[4] if has_material_model and r[4] is not None else ""
            value_offset = 1 if has_material_model else 0
            qty = float(r[4 + value_offset]) if r[4 + value_offset] is not None else 0.0
            delivery_date = r[5 + value_offset]
            receive_qty = float(r[6 + value_offset]) if r[6 + value_offset] is not None else 0.0
            # r[7 + value_offset] is FREMAINRECEIVEQTY
            stockin_qty = float(r[8 + value_offset]) if r[8 + value_offset] is not None else 0.0
            # r[9 + value_offset] is FREMAINSTOCKINQTY

            # 核心逻辑
            unreceived_qty = max(0, qty - receive_qty)
            unstockin_qty = max(0, receive_qty - stockin_qty)

            base_info = {
                "project_number": project_number,
                "supplier_name": supplier_id,
                "material_id": material_id,
                "material_name": material_name,
                "material_model": material_model,
                "delivery_date": delivery_date
            }

            if unreceived_qty > 0:
                supplier_unreceived.append({
                    **base_info,
                    "purchase_qty": qty,
                    "received_qty": receive_qty,
                    "warning_unreceived_qty": unreceived_qty
                })

            if unstockin_qty > 0:
                warehouse_unstockin.append({
                    **base_info,
                    "received_qty": receive_qty,
                    "stockin_qty": stockin_qty,
                    "warning_unstockin_qty": unstockin_qty
                })
        except Exception as e:
            print(f"Error processing row {r}: {e}")
            continue

    print(f"Found {len(supplier_unreceived)} unreceived items and {len(warehouse_unstockin)} unstockin items.")
    return supplier_unreceived, warehouse_unstockin

def get_inventory_warning_data():
    """
    获取并处理预警数据
    """
    rows = get_purchase_order_data()
    return process_warning_data(rows)
