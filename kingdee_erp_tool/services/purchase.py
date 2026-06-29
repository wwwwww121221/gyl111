import datetime
import json
import logging
import time

from kingdee_erp_tool.core.client import client

logger = logging.getLogger(__name__)


BILL_TYPE_MAP = {
    "93591469feb54ca2b08eb635f8b79de3": "标准采购",
    "66387c8fd05437": "零星采购",
    "66d0038d59a406": "委外采购",
    "60d2460b0e5742d58432f70a06f193b6": "资产采购",
    "03c6c047c65c4a17a792f85dcf3cabec": "费用采购",
}


def get_purchase_requisition_data(
    keyword: str = None,
    bill_type_id: str = None,
    start_date: str = None,
    end_date: str = None,
):
    """
    获取采购申请单数据，支持关键字、单据类型和创建日期筛选。
    """
    now = datetime.datetime.now()
    now_str = now.strftime("%Y/%m/%d %H:%M:%S")

    filter_string = [
        {"Left": "(", "FieldName": "FDOCUMENTSTATUS", "Compare": "=", "Value": "C", "Right": ")", "Logic": "0"},
        {"Left": "(", "FieldName": "FMRPTERMINATESTATUS", "Compare": "=", "Value": "A", "Right": ")", "Logic": "0"},
        {"Left": "(", "FieldName": "FORDERJOINQTY", "Compare": "=", "Value": "0", "Right": ")", "Logic": "0"},
    ]

    if bill_type_id:
        filter_string.append(
            {"Left": "(", "FieldName": "FBILLTYPEID", "Compare": "=", "Value": bill_type_id, "Right": ")", "Logic": "0"}
        )

    if not start_date and not end_date:
        first_day = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        start_date = first_day.strftime("%Y/%m/%d %H:%M:%S")
        end_date = now_str

    if start_date:
        filter_string.append(
            {"Left": "(", "FieldName": "FCREATEDATE", "Compare": ">=", "Value": start_date, "Right": ")", "Logic": "0"}
        )
    if end_date:
        filter_string.append(
            {"Left": "(", "FieldName": "FCREATEDATE", "Compare": "<=", "Value": end_date, "Right": ")", "Logic": "0"}
        )

    filter_string.append(
        {"Left": "(", "FieldName": "FARRIVALDATE", "Compare": ">", "Value": now_str, "Right": ")", "Logic": "0"}
    )

    if keyword and keyword.strip():
        kw = keyword.strip()
        filter_string[-1]["Logic"] = "0"
        filter_string.append({"Left": "(", "FieldName": "FBILLNO", "Compare": "LIKE", "Value": f"%{kw}%", "Right": "", "Logic": "1"})
        filter_string.append({"Left": "", "FieldName": "F_XJPJ_BASE3.FNUMBER", "Compare": "LIKE", "Value": f"%{kw}%", "Right": "", "Logic": "1"})
        filter_string.append({"Left": "", "FieldName": "FMATERIALNAME", "Compare": "LIKE", "Value": f"%{kw}%", "Right": ")", "Logic": "0"})

    para = {
        "FormId": "PUR_Requisition",
        "FieldKeys": (
            "FBILLTYPEID,F_XJPJ_BASE3.FNUMBER,F_XJPJ_BASEPROPERTY1,FMATERIALID.FNUMBER,"
            "FMATERIALNAME,FMATERIALMODEL,FAPPROVEQTY,FPRICEUNITID.FNAME,FARRIVALDATE,"
            "FBILLNO,FCREATEDATE,FPURCHASERID.FNAME,F_XJPJ_BASE.FNAME,FNOTE,"
            "F_XJPJ_REMARKS_QTR,F_VBDA_USERID_83G.FNAME"
        ),
        "FilterString": filter_string,
        "OrderString": "FCREATEDATE DESC",
        "TopRowCount": 0,
        "StartRow": 0,
        "Limit": 2000,
        "SubSystemId": "",
    }

    return client.execute_query(para)


def process_purchase_data(rows):
    """
    将 ERP 原始二维数组处理为结构化字典列表。
    """
    if rows is None:
        return []
    if not isinstance(rows, list):
        raise RuntimeError("ERP returned data in an unexpected format")

    def _safe_float(value, default=0.0):
        if value is None or value == "":
            return default
        try:
            return float(value)
        except (TypeError, ValueError):
            logger.warning("Invalid ERP purchase qty value %r, fallback to %s", value, default)
            return default

    result = []
    for row in rows:
        if not isinstance(row, list):
            logger.warning("Skipping unexpected ERP requisition row: %r", row)
            continue

        bill_type_id = row[0] if len(row) > 0 else ""
        project_number = row[1] if len(row) > 1 else ""
        project_name = row[2] if len(row) > 2 else ""
        material_id = row[3] if len(row) > 3 else ""
        material_name = row[4] if len(row) > 4 else ""
        material_model = row[5] if len(row) > 5 else ""
        purchase_qty = _safe_float(row[6] if len(row) > 6 else None)
        price_unit_name = row[7] if len(row) > 7 else ""
        delivery_date = row[8] if len(row) > 8 else ""
        bill_no = row[9] if len(row) > 9 else ""
        created_date = row[10] if len(row) > 10 else ""
        purchaser_detail_name = row[11] if len(row) > 11 else ""
        purchaser_base_name = row[12] if len(row) > 12 else ""
        remark_base = row[13] if len(row) > 13 else ""
        remark_detail = row[14] if len(row) > 14 else ""
        technician_name = row[15] if len(row) > 15 else ""

        result.append(
            {
                "bill_type": BILL_TYPE_MAP.get(bill_type_id, bill_type_id),
                "bill_no": bill_no,
                "project_number": project_number,
                "project_name": project_name,
                "material_id": material_id,
                "material_name": material_name,
                "material_model": material_model,
                "price_unit_name": price_unit_name,
                "purchase_qty": purchase_qty,
                "delivery_date": delivery_date,
                "created_date": created_date,
                "purchaser_detail_name": purchaser_detail_name,
                "purchaser_base_name": purchaser_base_name,
                "purchaser_name": purchaser_detail_name or purchaser_base_name,
                "remark_base": remark_base,
                "remark_detail": remark_detail,
                "remark": remark_detail or remark_base,
                "technician_name": technician_name,
            }
        )

    return result


def get_processed_purchase_data(
    keyword: str = None,
    bill_type_id: str = None,
    start_date: str = None,
    end_date: str = None,
):
    """
    获取并处理采购申请单数据。
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
    获取历史采购订单明细价格，用于价格分析。
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
        "Limit": limit,
    }

    result = client.execute_query(json.dumps(para))

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

        for row in result:
            parsed_results.append(
                {
                    "bill_no": _v(row, 0),
                    "date": _v(row, 1),
                    "supplier_code": _v(row, 2),
                    "supplier_name": _v(row, 3),
                    "material_code": _v(row, 4),
                    "material_name": _v(row, 5),
                    "price": _v(row, 6),
                    "tax_net_price": _v(row, 7),
                    "qty": _v(row, 8),
                    "project_number": _v(row, 9),
                    "erp_entry_id": None,
                }
            )
    return parsed_results
