import json
from kingdee_erp_tool.core.client import client

def fetch_suppliers_from_erp(limit: int = 2000, start_row: int = 0):
    """
    从金蝶 ERP 获取供应商列表
    表单: BD_Supplier
    """
    field_keys = [
        "FNUMBER",
        "FNAME",
        "FSHORTNAME",
        "FGroup.FName",
        "FSupplierGrade.FDataValue"
    ]
    
    para = {
        "FormId": "BD_Supplier",
        "FieldKeys": ",".join(field_keys),
        "FilterString": "",
        "OrderString": "FNUMBER ASC",
        "TopRowCount": 0,
        "StartRow": start_row,
        "Limit": limit
    }
    
    try:
        query_json = json.dumps(para)
        result = client.execute_query(query_json)
        
        if isinstance(result, list) and len(result) > 0:
            if isinstance(result[0], list):
                parsed_suppliers = []
                for row in result:
                    supplier = {
                        "code": row[0],
                        "name": row[1],
                        "short_name": row[2] if len(row) > 2 else None,
                        "group_name": row[3] if len(row) > 3 else None,
                        "grade": row[4] if len(row) > 4 else None
                    }
                    parsed_suppliers.append(supplier)
                return parsed_suppliers
            elif isinstance(result[0], dict) and "Result" in result[0]:
                print(f"ERP Error: {result[0]['Result']['ResponseStatus']['Errors']}")
                return []
        return result
    except Exception as e:
        print(f"Failed to fetch suppliers from ERP: {e}")
        return []

def fetch_materials_from_erp(limit: int = 2000, start_row: int = 0):
    """
    从金蝶 ERP 获取物料主数据列表
    表单: BD_MATERIAL
    """
    field_keys = [
        "FNUMBER",
        "FNAME",
        "FSpecification",
        "FErpClsID",
        "FMaterialGroup.FName",
        "FBaseUnitId.FName"
    ]
    
    para = {
        "FormId": "BD_MATERIAL",
        "FieldKeys": ",".join(field_keys),
        "FilterString": "FUseOrgId.FNumber='100'", # 默认取组织，根据需要修改，通常这里可为空
        "OrderString": "FNUMBER ASC",
        "TopRowCount": 0,
        "StartRow": start_row,
        "Limit": limit
    }
    
    try:
        query_json = json.dumps(para)
        result = client.execute_query(query_json)
        
        if isinstance(result, list) and len(result) > 0:
            if isinstance(result[0], list):
                parsed_materials = []
                for row in result:
                    material = {
                        "code": row[0],
                        "name": row[1],
                        "specification": row[2] if len(row) > 2 else None,
                        "erp_cls_id": str(row[3]) if len(row) > 3 else None,
                        "group_name": row[4] if len(row) > 4 else None,
                        "base_unit": row[5] if len(row) > 5 else None
                    }
                    parsed_materials.append(material)
                return parsed_materials
            elif isinstance(result[0], dict) and "Result" in result[0]:
                print(f"ERP Error: {result[0]['Result']['ResponseStatus']['Errors']}")
                return []
        return result
    except Exception as e:
        print(f"Failed to fetch materials from ERP: {e}")
        return []
