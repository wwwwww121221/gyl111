from fastapi import APIRouter, Depends, HTTPException, Request
from typing import Any, List, Optional
from pydantic import BaseModel
from datetime import datetime
import logging
from sqlalchemy.orm import Session
from models import get_db, WarningMessage, Supplier, User, Material
from routers.inquiry import get_current_user
from services.wechat_service import notify_warning_message

# 引用现有的 ERP 业务逻辑
from kingdee_erp_tool.services.inventory import get_inventory_warning_data

router = APIRouter()
logger = logging.getLogger(__name__)

# --- Schemas ---

class WarningItem(BaseModel):
    project_number: Optional[str] = None
    supplier_name: Optional[str] = None
    material_id: Optional[str] = None
    material_name: Optional[str] = None
    material_model: Optional[str] = None
    delivery_date: Any # 可能是 datetime 或 str
    purchase_qty: float = 0.0
    received_qty: float = 0.0
    stockin_qty: float = 0.0
    warning_unreceived_qty: float = 0.0
    warning_unstockin_qty: float = 0.0

class DashboardSummary(BaseModel):
    total_unreceived_items: int
    total_unstockin_items: int
    supplier_count: int # Renamed from risk_suppliers_count
    total_unreceived_qty: float # Renamed from total_risk_qty

class WarningDashboardResponse(BaseModel):
    summary: DashboardSummary
    supplier_unreceived: List[WarningItem]
    warehouse_unstockin: List[WarningItem]

class SendWarningRequest(BaseModel):
    supplier_name: str
    items: List[dict]

class MarkReadRequest(BaseModel):
    remark: Optional[str] = None

class WarningMessageResponse(BaseModel):
    id: int
    content: str
    created_at: datetime
    is_read: bool
    read_at: Optional[datetime] = None
    supplier_remark: Optional[str] = None
    
    class Config:
        from_attributes = True

class BuyerWarningMessageResponse(WarningMessageResponse):
    supplier_name: str
    buyer_name: Optional[str] = None


def _enrich_warning_items_with_material_model(items: List[dict], db: Session) -> List[dict]:
    if not items:
        return items

    material_codes = {
        str(item.get("material_id") or "").strip()
        for item in items
        if item.get("material_id")
    }
    if not material_codes:
        return items

    material_rows = (
        db.query(Material.code, Material.specification)
        .filter(Material.code.in_(material_codes))
        .all()
    )
    model_map = {
        str(row.code).strip(): row.specification
        for row in material_rows
        if row.code
    }

    enriched_items = []
    for item in items:
        normalized_code = str(item.get("material_id") or "").strip()
        erp_material_model = str(item.get("material_model") or "").strip()
        enriched_items.append({
            **item,
            "material_model": erp_material_model or model_map.get(normalized_code) or ""
        })
    return enriched_items

# --- Endpoints ---

@router.post("/send")
def send_warning_to_supplier(
    req: SendWarningRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    request: Request = None
) -> Any:
    """
    采购员向供应商发送发货预警通知
    """
    if current_user.role not in ["admin", "buyer", "buyer_manager"]:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    supplier = db.query(Supplier).filter(Supplier.name == req.supplier_name).first()
    if not supplier:
        raise HTTPException(status_code=404, detail=f"Supplier {req.supplier_name} not found in system")
        
    # 构建预警内容
    content_lines = [f"【发货预警通知】采购员 {current_user.username} 提醒您有逾期或即将逾期的物料，请尽快安排发货：\n"]
    for item in req.items:
        m_name = item.get("material_name", "未知物料")
        m_model = item.get("material_model", "")
        # 兼容前端传递 qty 或 warning_unreceived_qty
        q = item.get("qty", item.get("warning_unreceived_qty", 0))
        d = item.get("delivery_date", "")
        model_text = f"，规格型号：{m_model}" if m_model else ""
        content_lines.append(f"- 物料：{m_name}{model_text}，欠交数量：{q}，要求交期：{d}")
        
    msg = WarningMessage(
        supplier_id=supplier.id,
        buyer_id=current_user.id,
        content="\n".join(content_lines)
    )
    db.add(msg)
    db.commit()
    latest_delivery = None
    if req.items:
        delivery_values = [
            str(item.get("delivery_date") or "").strip()
            for item in req.items
            if item.get("delivery_date")
        ]
        if delivery_values:
            latest_delivery = sorted(delivery_values)[0]

    try:
        notify_warning_message(
            db,
            supplier,
            latest_delivery=latest_delivery,
            item_count=len(req.items or []),
            buyer_name=current_user.username,
        )
    except Exception:
        logger.exception("发货预警微信通知发送失败, supplier_id=%s", supplier.id)
    
    from routers.system import log_operation
    log_operation(
        db,
        current_user.id,
        "SEND_WARNING",
        f"向供应商 {req.supplier_name} 发送了催货预警",
        request=request,
        module="预警管理",
        target_type="供应商",
        target_name=req.supplier_name,
        result="success",
        extra_data={
            "item_count": len(req.items or []),
            "items": [
                {
                    "material_name": item.get("material_name", ""),
                    "material_model": item.get("material_model", ""),
                    "qty": item.get("qty", item.get("warning_unreceived_qty", 0)),
                    "delivery_date": item.get("delivery_date", "")
                }
                for item in (req.items or [])
            ]
        }
    )
    
    return {"message": "预警发送成功"}

@router.get("/my-messages", response_model=List[WarningMessageResponse])
def get_my_warning_messages(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    供应商获取自己的预警消息
    """
    if current_user.role != "supplier":
        raise HTTPException(status_code=403, detail="Not authorized")
        
    supplier = db.query(Supplier).filter(Supplier.user_id == current_user.id).first()
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier profile not found")
        
    messages = db.query(WarningMessage).filter(WarningMessage.supplier_id == supplier.id).order_by(WarningMessage.created_at.desc()).all()
    return messages

@router.put("/my-messages/{msg_id}/read")
def mark_message_read(
    msg_id: int,
    req: Optional[MarkReadRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    if current_user.role != "supplier":
        raise HTTPException(status_code=403, detail="Not authorized")
        
    supplier = db.query(Supplier).filter(Supplier.user_id == current_user.id).first()
    msg = db.query(WarningMessage).filter(WarningMessage.id == msg_id, WarningMessage.supplier_id == supplier.id).first()
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
        
    msg.is_read = True
    msg.read_at = datetime.now()
    if req and req.remark:
        msg.supplier_remark = req.remark
    db.commit()
    return {"message": "标记为已读"}

@router.get("/sent-messages", response_model=List[BuyerWarningMessageResponse])
def get_sent_warning_messages(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    采购员获取发送过的预警消息及回复状态
    如果是 admin，获取所有；如果是 buyer，只获取自己发送的
    """
    if current_user.role not in ["admin", "buyer", "buyer_manager"]:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    query = db.query(WarningMessage).join(Supplier, WarningMessage.supplier_id == Supplier.id)
    if current_user.role == "buyer":
        query = query.filter(WarningMessage.buyer_id == current_user.id)
        
    messages = query.order_by(WarningMessage.created_at.desc()).all()
    
    result = []
    for msg in messages:
        result.append({
            "id": msg.id,
            "content": msg.content,
            "created_at": msg.created_at,
            "is_read": msg.is_read,
            "read_at": msg.read_at,
            "supplier_remark": msg.supplier_remark,
            "supplier_name": msg.supplier.name,
            "buyer_name": msg.buyer.username if msg.buyer else None
        })
    return result

@router.get("/dashboard", response_model=WarningDashboardResponse)
def get_warning_dashboard(
    db: Session = Depends(get_db)
) -> Any:
    """
    获取预警大屏数据：包含汇总信息和详细列表
    """
    try:
        # 调用底层服务获取数据
        unreceived, unstockin = get_inventory_warning_data()
        unreceived = _enrich_warning_items_with_material_model(unreceived, db)
        unstockin = _enrich_warning_items_with_material_model(unstockin, db)
        
        # 计算汇总指标
        unique_suppliers = set()
        total_unreceived_qty = 0.0
        
        for item in unreceived:
            # item.get("supplier_name") might be None
            s_name = item.get("supplier_name")
            if s_name:
                unique_suppliers.add(s_name)
            total_unreceived_qty += item.get("warning_unreceived_qty", 0)
            
        summary = DashboardSummary(
            total_unreceived_items=len(unreceived),
            total_unstockin_items=len(unstockin),
            supplier_count=len(unique_suppliers),
            total_unreceived_qty=total_unreceived_qty
        )
        
        return {
            "summary": summary,
            "supplier_unreceived": unreceived,
            "warehouse_unstockin": unstockin
        }
        
    except Exception as e:
        logger.exception("Failed to fetch warning dashboard data")
        # Return 500 but try to be helpful
        raise HTTPException(status_code=500, detail=f"Failed to fetch warning data: {str(e)}")
