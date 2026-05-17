from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta
from typing import Any

from core import security
from core.config import settings
from models import get_db, User
from schemas import Token, UserCreate, User as UserSchema
from jose import jwt, JWTError

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")


def _find_user_for_login(db: Session, login_value: str):
    user = db.query(User).filter(User.username == login_value).first()
    if user:
        return user

    from models import Supplier

    supplier = db.query(Supplier).filter(Supplier.phone == login_value).first()
    if supplier and supplier.user_id:
        return db.query(User).filter(User.id == supplier.user_id).first()

    return None

def get_current_user_auth(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise credentials_exception
    return user

@router.post("/login", response_model=Token)
def login_access_token(
    db: Session = Depends(get_db), 
    form_data: OAuth2PasswordRequestForm = Depends(),
    request: Request = None
) -> Any:
    """
    OAuth2 兼容的 token 登录接口，获取 Access Token
    """
    login_value = (form_data.username or "").strip()
    user = _find_user_for_login(db, login_value)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="该账号未注册",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    # 检查供应商审核状态（在验证密码之前，或之后，但如果用户希望在没审核时提示没审核而不是密码错误，应该先检查审核状态）
    if user.role == "supplier":
        from models import Supplier
        supplier = db.query(Supplier).filter(Supplier.user_id == user.id).first()
        if not supplier:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Supplier profile not found.",
            )
        if supplier.status == "pending":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="您的账号正在审核中，请耐心等待。",
            )
        if supplier.status == "rejected":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="您的账号审核未通过或已被停用。",
            )
            
    if not security.verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    # 增加 role 字段到 token payload 中
    access_token = security.create_access_token(
        subject=user.username, 
        expires_delta=access_token_expires,
        additional_claims={"role": user.role}
    )
    
    from routers.system import log_operation
    log_operation(
        db,
        user.id,
        "LOGIN",
        f"用户 {user.username} 登录系统",
        request=request,
        module="认证中心",
        target_type="账号",
        target_name=user.username,
        result="success",
        extra_data={"role": user.role}
    )
    
    return {"access_token": access_token, "token_type": "bearer", "role": user.role, "username": user.username}

@router.post("/register", response_model=UserSchema)
def register_user(
    *,
    db: Session = Depends(get_db),
    user_in: UserCreate,
    request: Request = None
) -> Any:
    """
    注册新用户
    """
    user = db.query(User).filter(User.username == user_in.username).first()
    if user:
        raise HTTPException(
            status_code=400,
            detail="The user with this username already exists in the system.",
        )
    
    user = User(
        username=user_in.username,
        password_hash=security.get_password_hash(user_in.password),
        role=user_in.role
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # 如果是供应商注册，需要同步创建 Supplier 记录
    if user.role == "supplier":
        from models import Supplier
        # 提取注册时传入的额外信息
        supplier = Supplier(
            name=user_in.company_name or user.username, # 优先使用填写的公司名
            contact_person=user_in.contact_person,
            phone=user_in.phone,
            email=user_in.email,
            status="pending",   # 恢复为需要人工审核
            user_id=user.id
        )
        db.add(supplier)
        db.commit()
        
    from routers.system import log_operation
    log_operation(
        db,
        user.id,
        "CREATE_USER",
        f"新账号注册: {user.username} (角色: {user.role})",
        request=request,
        module="认证中心",
        target_type="账号",
        target_name=user.username,
        result="success",
        extra_data={
            "role": user.role,
            "company_name": user_in.company_name or ""
        }
    )

    return user

@router.get("/users")
def get_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_auth)
) -> Any:
    """
    获取采购员和管理员列表（仅超级管理员可访问）
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="只有超级管理员可以访问账号列表")
        
    users = db.query(User).filter(User.role.in_(["admin", "buyer"])).all()
    return [{"id": u.id, "username": u.username, "role": u.role} for u in users]

@router.delete("/users/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_auth),
    request: Request = None
) -> Any:
    """
    删除采购员账号（仅超级管理员可访问）
    处理外键约束问题，将关联记录的 buyer_id 置空
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="只有超级管理员可以删除账号")
        
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="账号不存在")
        
    if user.role == "admin" and user.id == current_user.id:
        raise HTTPException(status_code=400, detail="不能删除当前正在使用的超级管理员账号")
        
    try:
        from models import InquiryTask, WarningMessage, Supplier
        from routers.system import log_operation
        
        # 1. 询价单的外键 buyer_id 和 created_by 置空或移交
        db.query(InquiryTask).filter(InquiryTask.buyer_id == user.id).update({"buyer_id": None})
        db.query(InquiryTask).filter(InquiryTask.created_by == user.id).update({"created_by": None})
        
        # 2. 预警消息的 buyer_id 置空
        db.query(WarningMessage).filter(WarningMessage.buyer_id == user.id).update({"buyer_id": None})
        
        # 3. 供应商表里的 reviewer_id 置空
        db.query(Supplier).filter(Supplier.reviewer_id == user.id).update({"reviewer_id": None})
        
        log_operation(
            db,
            current_user.id,
            "DELETE_USER",
            f"删除了采购员账号: {user.username}",
            request=request,
            module="账号管理",
            target_type="账号",
            target_name=user.username,
            result="success",
            extra_data={"deleted_role": user.role}
        )
        
        db.delete(user)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"删除失败，外键冲突或系统错误: {str(e)}")
        
    return {"message": "账号已删除"}
