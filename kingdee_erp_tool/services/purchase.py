import datetime
import time
from kingdee_erp_tool.core.client import client

# 单据类型映射字典
BILL_TYPE_MAP = {
    "93591469feb54ca2b08eb635f8b79de3": "标准采购",
    "66387c8fd05437": "零星采购",
    "66d0038d59a406": "委外采购",
    "60d2460b0e5742d58432f70a06f193b6": "资产采购",
    "03c6c047c65c4a17a792f85dcf3cabec": "费用采购"
}

def get_purchase_requisition_data(keyword: str = None, bill_type_id: str = None, start_date: str = None, end_date: str = None):
    """
    获取采购申请单数据（支持多条件高级过滤）
    """
    now = datetime.datetime.now()
    now_str = now.strftime("%Y/%m/%d %H:%M:%S")

    # 基础固定条件
    filter_string = [
        {"Left": "(", "FieldName": "FDOCUMENTSTATUS", "Compare": "=", "Value": "C", "Right": ")", "Logic": "0"},
        {"Left": "(", "FieldName": "FMRPTERMINATESTATUS", "Compare": "=", "Value": "A", "Right": ")", "Logic": "0"},
        {"Left": "(", "FieldName": "FORDERJOINQTY", "Compare": "=", "Value": "0", "Right": ")", "Logic": "0"}
    ]
    
    # 单据类型过滤（如果没有传，默认查所有的类型，或者这里你可以强制默认只查标准采购）
    if bill_type_id:
        filter_string.append({"Left": "(", "FieldName": "FBILLTYPEID", "Compare": "=", "Value": bill_type_id, "Right": ")", "Logic": "0"})

    # 如果未指定日期范围，默认查询本月数据
    if not start_date and not end_date:
        first_day = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        start_date = first_day.strftime("%Y/%m/%d %H:%M:%S")
        end_date = now_str

    # 日期范围过滤
    if start_date:
        filter_string.append({"Left": "(", "FieldName": "FCREATEDATE", "Compare": ">=", "Value": start_date, "Right": ")", "Logic": "0"})
    if end_date:
        filter_string.append({"Left": "(", "FieldName": "FCREATEDATE", "Compare": "<=", "Value": end_date, "Right": ")", "Logic": "0"})
    
    # 交货日期过滤（固定要求大于当前时间，防止拉取到过期的）
    filter_string.append({"Left": "(", "FieldName": "FARRIVALDATE", "Compare": ">", "Value": now_str, "Right": ")", "Logic": "0"})

    # 如果有搜索关键字，增加按单号、项目号、物料名称的模糊匹配
    if keyword and keyword.strip():
        kw = keyword.strip()
        filter_string[-1]["Logic"] = "0" # Ensure the previous condition is AND
        
        filter_string.append({"Left": "(", "FieldName": "FBILLNO", "Compare": "LIKE", "Value": f"%{kw}%", "Right": "", "Logic": "1"}) # OR
        filter_string.append({"Left": "", "FieldName": "F_XJPJ_BASE3.FNUMBER", "Compare": "LIKE", "Value": f"%{kw}%", "Right": "", "Logic": "1"}) # OR
        filter_string.append({"Left": "", "FieldName": "FMATERIALNAME", "Compare": "LIKE", "Value": f"%{kw}%", "Right": ")", "Logic": "0"}) # End of OR group

    para = {
        "FormId": "PUR_Requisition",
        "FieldKeys": "FBILLTYPEID,F_XJPJ_BASE3.FNUMBER,F_XJPJ_BASEPROPERTY1,FMATERIALID.FNUMBER,FMATERIALNAME,FMATERIALMODEL,FAPPROVEQTY,FARRIVALDATE,FBILLNO,FCREATEDATE",
        "FilterString": filter_string,
        "OrderString": "FCREATEDATE DESC",
        "TopRowCount": 0,
        "StartRow": 0,
        "Limit": 2000,
        "SubSystemId": ""
    }

    # 使用 client 执行查询
    return client.execute_query(para)

def process_purchase_data(rows):
    """
    将原始二维数组处理成结构化字典列表
    """
    result = []

    for r in rows:
        bill_type_id = r[0] if len(r) > 0 else ""
        project_number = r[1] if len(r) > 1 else ""
        project_name = r[2] if len(r) > 2 else ""
        material_id = r[3] if len(r) > 3 else ""
        material_name = r[4] if len(r) > 4 else ""
        material_model = r[5] if len(r) > 5 else ""
        purchase_qty = float(r[6]) if len(r) > 6 and r[6] is not None else 0.0
        delivery_date = r[7] if len(r) > 7 else ""
        bill_no = r[8] if len(r) > 8 else ""
        created_date = r[9] if len(r) > 9 else ""

        # 单据类型替换
        bill_type_name = BILL_TYPE_MAP.get(bill_type_id, bill_type_id)

        item = {
            "bill_type": bill_type_name,
            "bill_no": bill_no,
            "project_number": project_number,
            "project_name": project_name,
            "material_id": material_id,
            "material_name": material_name,
            "material_model": material_model,
            "purchase_qty": purchase_qty,
            "delivery_date": delivery_date,
            "created_date": created_date
        }

        result.append(item)

    return result

def get_processed_purchase_data(keyword: str = None, bill_type_id: str = None, start_date: str = None, end_date: str = None):
    """
    获取并处理采购申请单数据
    """
    rows = get_purchase_requisition_data(keyword, bill_type_id, start_date, end_date)
    return process_purchase_data(rows)

def get_historical_purchase_prices(
    material_code: str = None,
    supplier_code: str = None,
    months_back: int = 12,
    limit: int = 100,
    start_date: str = None,
    end_date: str = None,
    start_row: int = 0,
):
    """
    获取历史采购订单明细价格（用于 AI 价格分析）
    """
    now = datetime.datetime.now()
    start_date = start_date or (now - datetime.timedelta(days=30 * months_back)).strftime("%Y-%m-%dT00:00:00")
    filter_string = f"FDate >= '{start_date}' and FDocumentStatus = 'C'"
    if end_date:
        filter_string += f" and FDate <= '{end_date}'"
    
    if material_code:
        filter_string += f" and FMaterialId.FNumber = '{material_code}'"
    if supplier_code:
        filter_string += f" and FSupplierId.FNumber = '{supplier_code}'"

    para = {
        "FormId": "PUR_PurchaseOrder",
        "FieldKeys": "FBillNo,FDate,FSupplierId.FNumber,FSupplierId.FName,FMaterialId.FNumber,FMaterialId.FName,FPrice,FTaxNetPrice,FQty,F_XJPJ_BASE.FNUMBER",
        "FilterString": filter_string,
        "OrderString": "FDate DESC",
        "StartRow": start_row,
        "Limit": limit
    }
    
    import json
    result = client.execute_query(json.dumps(para))

    # ERP may return error payload in a list; detect and return empty instead of parsing as data row.
    if isinstance(result, list) and result:
        first = result[0]
        if isinstance(first, dict) and "Result" in first:
            return []
        if isinstance(first, list) and first and isinstance(first[0], dict) and "Result" in first[0]:
            return []
    
    parsed_results = []
    if isinstance(result, list) and len(result) > 0 and isinstance(result[0], list):
        def _v(row, idx, default=None):
            return row[idx] if len(row) > idx else default
        for r in result:
            parsed_results.append({
                "bill_no": _v(r, 0),
                "date": _v(r, 1),
                "supplier_code": _v(r, 2),
                "supplier_name": _v(r, 3),
                "material_code": _v(r, 4),
                "material_name": _v(r, 5),
                "price": _v(r, 6),
                "tax_net_price": _v(r, 7),
                "qty": _v(r, 8),
                "project_number": _v(r, 9),
                "erp_entry_id": None,
            })
    return parsed_results
