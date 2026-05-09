from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from typing import Any, List
from datetime import datetime
from models import get_db, User, OperationLog, InquiryTask, Contract, WarningMessage, Supplier
from routers.auth import get_current_user_auth
from sqlalchemy import func

router = APIRouter()

def log_operation(db: Session, user_id: int, action_type: str, detail: str, ip_address: str = None):
    try:
        log = OperationLog(
            user_id=user_id,
            action_type=action_type,
            detail=detail,
            ip_address=ip_address
        )
        db.add(log)
        db.commit()
    except Exception as e:
        print(f"Failed to log operation: {e}")
        db.rollback()

@router.get("/logs")
def get_operation_logs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_auth),
    skip: int = 0,
    limit: int = 100
) -> Any:
    """
    获取操作日志列表（仅限超级管理员）
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="只有超级管理员可以查看操作日志")
        
    logs = db.query(OperationLog).order_by(OperationLog.created_at.desc()).offset(skip).limit(limit).all()
    
    result = []
    for log in logs:
        result.append({
            "id": log.id,
            "username": log.user.username if log.user else "系统/未知",
            "action_type": log.action_type,
            "detail": log.detail,
            "ip_address": log.ip_address,
            "created_at": log.created_at.strftime("%Y-%m-%d %H:%M:%S") if log.created_at else None
        })
    return result

@router.get("/buyer-analysis")
def get_buyer_analysis(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_auth)
) -> Any:
    """
    获取采购员数据分析（仅限超级管理员）
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="只有超级管理员可以查看采购员分析")
        
    # 获取所有的 buyer 和 admin (因为 admin 也可能发单)
    buyers = db.query(User).filter(User.role.in_(["buyer", "admin"])).all()
    
    result = []
    for buyer in buyers:
        # 1. 询价单总数
        total_tasks = db.query(InquiryTask).filter(InquiryTask.buyer_id == buyer.id).count()
        
        # 2. 定标生成的合同总数
        contracts_count = db.query(Contract).join(InquiryTask).filter(InquiryTask.buyer_id == buyer.id).count()
        
        # 3. 发送预警次数
        warnings_count = db.query(WarningMessage).filter(WarningMessage.buyer_id == buyer.id).count()
        
        # 4. 审核通过的供应商数量
        approved_suppliers = db.query(Supplier).filter(Supplier.reviewer_id == buyer.id).count()
        
        result.append({
            "id": buyer.id,
            "username": buyer.username,
            "role": buyer.role,
            "total_tasks": total_tasks,
            "contracts_count": contracts_count,
            "warnings_count": warnings_count,
            "approved_suppliers": approved_suppliers
        })
        
    return result