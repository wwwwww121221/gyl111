from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Any, List
from datetime import datetime
from models import get_db, User, OperationLog, InquiryTask, Contract, WarningMessage, Supplier
from routers.auth import get_current_user_auth
from sqlalchemy import func, or_
from core.config import settings
from services.wechat_service import (
    build_wechat_bind_entry_url,
    build_wechat_menu_payload,
    delete_wechat_menu,
    get_wechat_menu,
    is_wechat_configured,
    reset_wechat_menu,
    send_wechat_test_notification,
    sync_wechat_menu,
)

router = APIRouter()


class WechatTestSendPayload(BaseModel):
    openid: str | None = None
    subject: str | None = None
    result_text: str | None = None
    remark: str | None = None


class UserProfileUpdatePayload(BaseModel):
    phone: str | None = None
    department: str | None = None


def _is_admin_like(user: User | None) -> bool:
    return bool(user and user.role in ["admin", "buyer_manager"])


def _infer_module(action_type: str, detail: str) -> str:
    action_type = str(action_type or "").upper()
    mapping = {
        "LOGIN": "认证中心",
        "CREATE_USER": "账号管理",
        "DELETE_USER": "账号管理",
        "CHANGE_PASSWORD": "账号安全",
        "CREATE_INQUIRY": "询价管理",
        "UPDATE_SUPPLIER": "供应商管理",
        "DELETE_SUPPLIER": "供应商管理",
        "RESET_SUPPLIER_ACCOUNTS": "供应商管理",
        "SEND_WARNING": "预警管理",
    }
    return mapping.get(action_type) or ("系统管理" if detail else None)


def _infer_target(action_type: str, detail: str) -> tuple[str | None, str | None]:
    action_type = str(action_type or "").upper()
    detail = str(detail or "")

    if action_type == "CREATE_INQUIRY":
        marker = "创建了询价单:"
        if marker in detail:
            return "询价任务", detail.split(marker, 1)[1].strip()
        return "询价任务", None

    if action_type == "SEND_WARNING":
        marker = "向供应商"
        if marker in detail and "发送了催货预警" in detail:
            supplier_name = detail.split(marker, 1)[1].split("发送了催货预警", 1)[0].strip()
            return "供应商", supplier_name
        return "供应商", None

    if action_type == "LOGIN":
        marker = "用户"
        if marker in detail and "登录系统" in detail:
            username = detail.split(marker, 1)[1].split("登录系统", 1)[0].strip()
            return "账号", username
        return "账号", None

    if action_type == "CREATE_USER":
        marker = "新账号注册:"
        if marker in detail:
            username = detail.split(marker, 1)[1].split("(角色", 1)[0].strip()
            return "账号", username
        return "账号", None

    if action_type == "DELETE_USER":
        marker = "删除了采购员账号:"
        if marker in detail:
            return "账号", detail.split(marker, 1)[1].strip()
        return "账号", None

    if action_type == "UPDATE_SUPPLIER":
        marker = "更新供应商"
        if marker in detail and "状态为" in detail:
            supplier_name = detail.split(marker, 1)[1].split("状态为", 1)[0].strip()
            return "供应商", supplier_name
        return "供应商", None

    if action_type == "DELETE_SUPPLIER":
        marker = "删除了供应商及其关联账号和数据:"
        if marker in detail:
            return "供应商", detail.split(marker, 1)[1].strip()
        return "供应商", None

    if action_type == "CHANGE_PASSWORD":
        marker = "供应商"
        if marker in detail and "修改了登录密码" in detail:
            supplier_name = detail.split(marker, 1)[1].split("修改了登录密码", 1)[0].strip()
            return "供应商账号", supplier_name
        return "供应商账号", None

    if action_type == "RESET_SUPPLIER_ACCOUNTS":
        return "供应商账号", "批量重置"

    return None, None

def get_request_ip(request: Request = None) -> str:
    if not request:
        return None
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else None


def log_operation(
    db: Session,
    user_id: int,
    action_type: str,
    detail: str,
    ip_address: str = None,
    request: Request = None,
    module: str = None,
    target_type: str = None,
    target_name: str = None,
    result: str = "success",
    extra_data: dict = None
):
    try:
        log = OperationLog(
            user_id=user_id,
            action_type=action_type,
            module=module,
            target_type=target_type,
            target_name=target_name,
            result=result,
            detail=detail,
            extra_data=extra_data,
            ip_address=ip_address or get_request_ip(request)
        )
        db.add(log)
        db.commit()
    except Exception as e:
        print(f"Failed to log operation: {e}")
        db.rollback()


@router.get("/profile")
def get_current_user_profile(
    current_user: User = Depends(get_current_user_auth),
) -> Any:
    return {
        "id": current_user.id,
        "username": current_user.username,
        "role": current_user.role,
        "department": current_user.department,
        "phone": current_user.phone,
    }


@router.put("/profile")
def update_current_user_profile(
    payload: UserProfileUpdatePayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_auth),
    request: Request = None,
) -> Any:
    phone = (payload.phone or "").strip() or None
    department = (payload.department or "").strip() or None

    if phone:
        duplicated = db.query(User).filter(User.phone == phone, User.id != current_user.id).first()
        if duplicated:
            raise HTTPException(status_code=400, detail="该手机号已被其他账号使用")

    current_user.phone = phone
    current_user.department = department
    db.add(current_user)
    db.commit()
    db.refresh(current_user)

    log_operation(
        db,
        current_user.id,
        "UPDATE_PROFILE",
        f"用户 {current_user.username} 更新了个人信息",
        request=request,
        module="账号安全",
        target_type="账号",
        target_name=current_user.username,
        result="success",
        extra_data={"phone": current_user.phone, "department": current_user.department},
    )

    return {
        "id": current_user.id,
        "username": current_user.username,
        "role": current_user.role,
        "department": current_user.department,
        "phone": current_user.phone,
    }


@router.get("/logs")
def get_operation_logs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_auth),
    skip: int = 0,
    limit: int = 200,
    start_time: str | None = Query(None),
    end_time: str | None = Query(None),
    role: str | None = Query(None),
    module: str | None = Query(None),
    action_type: str | None = Query(None),
    result: str | None = Query(None),
    keyword: str | None = Query(None)
) -> Any:
    """
    获取操作日志列表（仅限超级管理员）
    """
    if not _is_admin_like(current_user):
        raise HTTPException(status_code=403, detail="只有超级管理员或采购部经理可以查看操作日志")

    logs_query = db.query(OperationLog).outerjoin(User, OperationLog.user_id == User.id)

    if start_time:
        try:
            start_dt = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
            logs_query = logs_query.filter(OperationLog.created_at >= start_dt)
        except ValueError:
            raise HTTPException(status_code=400, detail="开始时间格式不正确")

    if end_time:
        try:
            end_dt = datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S")
            logs_query = logs_query.filter(OperationLog.created_at <= end_dt)
        except ValueError:
            raise HTTPException(status_code=400, detail="结束时间格式不正确")

    if role:
        logs_query = logs_query.filter(User.role == role)

    if action_type:
        logs_query = logs_query.filter(OperationLog.action_type == action_type)

    if result:
        logs_query = logs_query.filter(OperationLog.result == result)

    if keyword:
        like_pattern = f"%{keyword.strip()}%"
        logs_query = logs_query.filter(
            or_(
                User.username.ilike(like_pattern),
                OperationLog.detail.ilike(like_pattern),
                OperationLog.target_name.ilike(like_pattern),
                OperationLog.module.ilike(like_pattern),
                OperationLog.action_type.ilike(like_pattern)
            )
        )

    logs = logs_query.order_by(OperationLog.created_at.desc()).all()

    resolved_logs = []
    for log in logs:
        resolved_module = log.module or _infer_module(log.action_type, log.detail)
        resolved_target_type = log.target_type
        resolved_target_name = log.target_name
        if not resolved_target_type and not resolved_target_name:
            resolved_target_type, resolved_target_name = _infer_target(log.action_type, log.detail)

        if module and resolved_module != module:
            continue

        resolved_logs.append({
            "id": log.id,
            "username": log.user.username if log.user else "系统/未知",
            "user_role": log.user.role if log.user else None,
            "action_type": log.action_type,
            "module": resolved_module,
            "target_type": resolved_target_type,
            "target_name": resolved_target_name,
            "result": log.result or "success",
            "detail": log.detail,
            "extra_data": log.extra_data or {},
            "ip_address": log.ip_address,
            "created_at": log.created_at.strftime("%Y-%m-%d %H:%M:%S") if log.created_at else None
        })

    return resolved_logs[skip: skip + limit]

@router.get("/buyer-analysis")
def get_buyer_analysis(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_auth)
) -> Any:
    """
    获取采购员数据分析（仅限超级管理员）
    """
    if not _is_admin_like(current_user):
        raise HTTPException(status_code=403, detail="只有超级管理员或采购部经理可以查看采购员分析")
        
    # 获取所有的 buyer/admin/buyer_manager (管理角色也可能发单)
    buyers = db.query(User).filter(
        User.role.in_(["buyer", "admin", "buyer_manager"]),
        (User.department == "采购部") | (User.role.in_(["admin", "buyer_manager"]))
    ).all()
    
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


@router.get("/wechat/status")
def get_wechat_status(
    current_user: User = Depends(get_current_user_auth),
) -> Any:
    login_url = None
    register_url = None
    preview_openid = str(current_user.openid or "").strip() or None
    if is_wechat_configured():
        try:
            login_url = build_wechat_bind_entry_url(openid=preview_openid, target="login")
            register_url = build_wechat_bind_entry_url(openid=preview_openid, target="register")
        except Exception:
            login_url = None
            register_url = None

    return {
        "configured": is_wechat_configured(),
        "app_id": settings.WECHAT_APP_ID,
        "verify_url": settings.WECHAT_VERIFY_URL,
        "bind_login_url": login_url,
        "bind_register_url": register_url,
        "menu_preview": build_wechat_menu_payload() if login_url and register_url else None,
        "current_user_openid": current_user.openid,
        "current_user_openid_bound": bool(str(current_user.openid or "").strip()),
    }


@router.post("/wechat/test-send")
def send_wechat_test_message(
    payload: WechatTestSendPayload,
    current_user: User = Depends(get_current_user_auth),
) -> Any:
    target_openid = str(payload.openid or current_user.openid or "").strip()
    if not target_openid:
        raise HTTPException(status_code=400, detail="Current user has no bound openid")

    try:
        result = send_wechat_test_notification(
            openid=target_openid,
            subject=payload.subject or current_user.username or "System Test",
            result_text=payload.result_text or "Sent",
            remark=payload.remark or "If you received this message, WeChat template messaging is working.",
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {
        "message": "WeChat test message sent successfully",
        "openid": target_openid,
        "wechat_result": result,
    }


@router.get("/wechat/menu-preview")
def get_wechat_menu_preview(
    current_user: User = Depends(get_current_user_auth),
) -> Any:
    if not _is_admin_like(current_user):
        raise HTTPException(status_code=403, detail="Only admin users can preview WeChat menu settings")

    try:
        payload = build_wechat_menu_payload()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "message": "WeChat menu preview generated successfully",
        "menu": payload,
    }


@router.get("/wechat/menu")
def read_wechat_menu(
    current_user: User = Depends(get_current_user_auth),
) -> Any:
    if not _is_admin_like(current_user):
        raise HTTPException(status_code=403, detail="Only admin users can view WeChat menu settings")

    try:
        result = get_wechat_menu()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {
        "message": "WeChat menu fetched successfully",
        "wechat_result": result,
    }


@router.post("/wechat/menu/sync")
def update_wechat_menu(
    current_user: User = Depends(get_current_user_auth),
) -> Any:
    if not _is_admin_like(current_user):
        raise HTTPException(status_code=403, detail="Only admin users can sync WeChat menu settings")

    try:
        result = sync_wechat_menu()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {
        "message": "WeChat menu synced successfully",
        **result,
    }


@router.post("/wechat/menu/delete")
def remove_wechat_menu(
    current_user: User = Depends(get_current_user_auth),
) -> Any:
    if not _is_admin_like(current_user):
        raise HTTPException(status_code=403, detail="Only admin users can delete WeChat menu settings")

    try:
        result = delete_wechat_menu()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {
        "message": "WeChat menu deleted successfully",
        "wechat_result": result,
    }


@router.post("/wechat/menu/reset")
def recreate_wechat_menu(
    current_user: User = Depends(get_current_user_auth),
) -> Any:
    if not _is_admin_like(current_user):
        raise HTTPException(status_code=403, detail="Only admin users can reset WeChat menu settings")

    try:
        result = reset_wechat_menu()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {
        "message": "WeChat menu reset successfully",
        **result,
    }
