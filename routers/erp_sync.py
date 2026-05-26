from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Any
import logging
from requests import exceptions as requests_exceptions

from models import get_db, InquiryRequest, InquiryStatus
from schemas import InquiryRequest as InquiryRequestSchema
from kingdee_erp_tool.services.purchase import get_processed_purchase_data, get_historical_purchase_prices
from kingdee_erp_tool.services.inventory import get_inventory_warning_data

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/requisitions", response_model=List[InquiryRequestSchema])
def sync_purchase_requisitions(
    keyword: str = None,
    bill_type_id: str = None,
    start_date: str = None,
    end_date: str = None,
    db: Session = Depends(get_db)
) -> Any:
    """
    从 ERP 获取采购申请单数据（不保存到数据库，仅返回给前端展示）
    """
    try:
        # 1. 从 ERP 拉取数据
        erp_data = get_processed_purchase_data(keyword, bill_type_id, start_date, end_date)
        
        display_items = []
        for item in erp_data:
            bill_no = item.get("bill_no", "")
            material_id = item.get("material_id", "")
            unique_key = f"{bill_no}_{material_id}" 
            
            # 创建临时对象，不存库
            temp_request = InquiryRequestSchema(
                erp_request_id=unique_key,
                bill_no=bill_no,
                bill_type=item.get("bill_type"),
                project_info={
                    "number": item.get("project_number"),
                    "name": item.get("project_name")
                },
                material_code=material_id,
                material_name=item.get("material_name"),
                material_model=item.get("material_model"),
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
                id=None, # No ID yet
                created_at=item.get("created_date")
            )
            display_items.append(temp_request)
        
        return display_items
        
    except requests_exceptions.RequestException as e:
        logger.exception("ERP sync request failed")
        raise HTTPException(
            status_code=502,
            detail=f"无法连接 ERP 服务，请检查网络、代理或 ERP 地址配置。原始错误: {str(e)}"
        )
    except Exception as e:
        logger.exception("ERP sync failed")
        raise HTTPException(status_code=500, detail=f"ERP 同步失败: {str(e)}")

@router.get("/po_history")
def get_po_history(
    material_code: str = None,
    supplier_code: str = None,
    months_back: int = 12,
    limit: int = 100
) -> Any:
    """
    获取历史采购订单价格（用于 AI 价格分析）
    """
    try:
        return get_historical_purchase_prices(
            material_code=material_code,
            supplier_code=supplier_code,
            months_back=months_back,
            limit=limit
        )
    except requests_exceptions.RequestException as e:
        logger.exception("ERP PO history request failed")
        raise HTTPException(
            status_code=502,
            detail=f"无法连接 ERP 服务，请检查网络、代理或 ERP 地址配置。原始错误: {str(e)}"
        )
    except Exception as e:
        logger.exception("Get PO history failed")
        raise HTTPException(status_code=500, detail=f"Failed to fetch PO history: {str(e)}")
