from datetime import datetime, timedelta
from pathlib import Path
import uuid
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from sqlalchemy import or_
from sqlalchemy.orm import Session

from core import security
from core.config import settings
from core.redis_client import cache_clear_pattern
from models import Supplier, SupplierMember, User, get_db
from schemas import (
    SupplierJoinRequestCreate,
    SupplierJoinRequestReview,
    SupplierOnboardingCreate,
    SupplierPasswordReset,
    SupplierPasswordLogin,
    SupplierSmsCodeSendRequest,
    SupplierSmsLogin,
    SupplierWechatBindRequest,
    SupplierWechatLoginRequest,
    Token,
    User as UserSchema,
    UserCreate,
)
from services.sms_service import (
    cleanup_expired_sms_codes,
    send_sms_code,
    validate_phone_or_raise,
    verify_sms_code,
)
from services.supplier_access import (
    get_supplier_context_for_portal,
    get_supplier_context_for_user,
    get_user_by_phone,
    get_user_memberships,
    normalize_phone,
    resolve_supplier_access,
)

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")

BASE_DIR = Path(__file__).resolve().parents[1]
SUPPLIER_UPLOAD_ROOT = BASE_DIR / "static" / "uploads" / "supplier_onboarding"
SUPPLIER_UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)


def _invalidate_supplier_cache() -> None:
    try:
        cache_clear_pattern("supplier:*")
    except Exception:
        pass


def _is_admin_like(user: User | None) -> bool:
    return bool(user and user.role in ["admin", "buyer_manager"])


def _find_user_for_login(db: Session, login_value: str) -> User | None:
    normalized = (login_value or "").strip()
    if not normalized:
        return None

    user = db.query(User).filter(User.username == normalized).first()
    if user:
        return user

    return db.query(User).filter(User.phone == normalized).first()


def _bind_openid_if_needed(db: Session, user: User, openid: str | None) -> None:
    normalized_openid = (openid or "").strip()
    if not normalized_openid:
        return

    existing = db.query(User).filter(User.openid == normalized_openid).first()
    if existing and existing.id != user.id:
        raise HTTPException(status_code=400, detail="该微信账号已绑定其他手机号")

    if user.openid != normalized_openid:
        user.openid = normalized_openid
        db.add(user)
        db.flush()


def _create_token_payload(
    user: User,
    supplier: Supplier | None = None,
    member: SupplierMember | None = None,
) -> dict[str, Any]:
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = security.create_access_token(
        subject=user.username,
        expires_delta=access_token_expires,
        additional_claims={"role": user.role},
    )
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "role": user.role,
        "username": user.username,
        "department": user.department,
        "supplier_id": supplier.id if supplier else None,
        "supplier_name": supplier.name if supplier else None,
        "supplier_status": supplier.status if supplier else None,
        "member_status": member.status if member else None,
    }


def _log_login(
    db: Session,
    user: User,
    request: Request | None = None,
    supplier: Supplier | None = None,
) -> None:
    from routers.system import log_operation

    extra_data = {"role": user.role}
    if supplier:
        extra_data["supplier_id"] = supplier.id
        extra_data["supplier_name"] = supplier.name

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
        extra_data=extra_data,
    )


def _ensure_supplier_user_role(user: User) -> None:
    if user.role != "supplier":
        raise HTTPException(status_code=400, detail="该手机号绑定的不是供应商账号")


def _require_supplier_member_reviewer(
    db: Session,
    current_user: User,
    member: SupplierMember,
) -> None:
    if current_user.role in ["admin", "buyer", "buyer_manager"]:
        return

    if current_user.role != "supplier":
        raise HTTPException(status_code=403, detail="Not authorized")

    supplier, reviewer_member = get_supplier_context_for_user(db, current_user)
    if supplier.id != member.supplier_id:
        raise HTTPException(status_code=403, detail="Not authorized")
    if member.approval_mode != "supplier_admin":
        raise HTTPException(status_code=403, detail="该申请需由平台管理员审核")
    if reviewer_member.role not in ["owner", "admin"]:
        raise HTTPException(status_code=403, detail="仅企业管理员可审核成员申请")


def _get_or_create_supplier_user(
    db: Session,
    phone: str,
    password: str | None = None,
    openid: str | None = None,
) -> User:
    normalized_phone = validate_phone_or_raise(phone)
    user = get_user_by_phone(db, normalized_phone)

    if user:
        _ensure_supplier_user_role(user)
        if password and not user.password_hash:
            user.password_hash = security.get_password_hash(password)
        _bind_openid_if_needed(db, user, openid)
        db.add(user)
        db.flush()
        return user

    if not password:
        password = uuid.uuid4().hex

    user = User(
        username=normalized_phone,
        phone=normalized_phone,
        password_hash=security.get_password_hash(password),
        role="supplier",
    )
    _bind_openid_if_needed(db, user, openid)
    db.add(user)
    db.flush()
    return user


def get_current_user_auth(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
):
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
    request: Request = None,
) -> Any:
    login_value = (form_data.username or "").strip()
    user = _find_user_for_login(db, login_value)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="该账号尚未注册",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not security.verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )

    supplier = None
    member = None
    if user.role == "supplier":
        supplier, member = get_supplier_context_for_portal(db, user)

    payload = _create_token_payload(user, supplier, member)
    _log_login(db, user, request=request, supplier=supplier)
    return payload


@router.post("/supplier/send-sms-code")
def send_supplier_sms_code(
    payload: SupplierSmsCodeSendRequest,
    db: Session = Depends(get_db),
) -> Any:
    cleanup_expired_sms_codes()
    phone = validate_phone_or_raise(payload.phone)
    scene = (payload.scene or "").strip().lower()

    if scene in {"login", "reset_password"}:
        user = get_user_by_phone(db, phone)
        if not user:
            raise HTTPException(
                status_code=404,
                detail="该手机号尚未绑定供应商，请先创建新供应商入驻或申请加入已有供应商",
            )
        if not get_user_memberships(db, user.id):
            raise HTTPException(status_code=403, detail="您尚未加入任何供应商企业")
    elif scene not in {"onboarding", "join"}:
        raise HTTPException(status_code=400, detail="短信场景不支持")

    result = send_sms_code(phone, scene)
    response: dict[str, Any] = {
        "message": result.message,
        "expires_in_seconds": result.expires_in_seconds,
    }
    if result.debug_code:
        response["debug_code"] = result.debug_code
    return response


@router.post("/supplier/reset-password")
def supplier_reset_password(
    payload: SupplierPasswordReset,
    db: Session = Depends(get_db),
) -> Any:
    phone = validate_phone_or_raise(payload.phone)
    user = get_user_by_phone(db, phone)
    if not user:
        raise HTTPException(status_code=404, detail="该手机号尚未绑定供应商账号")

    _ensure_supplier_user_role(user)
    verify_sms_code(phone, "reset_password", payload.sms_code)

    user.password_hash = security.get_password_hash(payload.new_password)
    db.add(user)
    db.commit()
    return {"message": "密码已重置，请使用新密码登录"}


@router.post("/supplier/password-login", response_model=Token)
def supplier_password_login(
    payload: SupplierPasswordLogin,
    db: Session = Depends(get_db),
    request: Request = None,
) -> Any:
    phone = validate_phone_or_raise(payload.phone)
    user = get_user_by_phone(db, phone)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="该手机号尚未绑定供应商，请先创建新供应商入驻或申请加入已有供应商",
        )

    _ensure_supplier_user_role(user)

    if not security.verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="密码错误",
        )

    supplier, member = resolve_supplier_access(db, user, allow_pending_supplier=True)
    _bind_openid_if_needed(db, user, payload.openid)
    db.commit()

    token_payload = _create_token_payload(user, supplier, member)
    _log_login(db, user, request=request, supplier=supplier)
    return token_payload


@router.post("/supplier/sms-login", response_model=Token)
def supplier_sms_login(
    payload: SupplierSmsLogin,
    db: Session = Depends(get_db),
    request: Request = None,
) -> Any:
    phone = validate_phone_or_raise(payload.phone)
    user = get_user_by_phone(db, phone)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="该手机号尚未绑定供应商，请先创建新供应商入驻或申请加入已有供应商",
        )

    _ensure_supplier_user_role(user)
    verify_sms_code(phone, "login", payload.sms_code)

    supplier, member = resolve_supplier_access(db, user, allow_pending_supplier=True)
    _bind_openid_if_needed(db, user, payload.openid)
    db.commit()

    token_payload = _create_token_payload(user, supplier, member)
    _log_login(db, user, request=request, supplier=supplier)
    return token_payload


@router.post("/supplier/wechat-login")
def supplier_wechat_login(
    payload: SupplierWechatLoginRequest,
    db: Session = Depends(get_db),
    request: Request = None,
) -> Any:
    openid = (payload.openid or "").strip()
    user = db.query(User).filter(User.openid == openid).first()
    if not user:
        return {
            "bound": False,
            "message": "该微信账号尚未绑定手机号，请先完成手机号登录",
            "next_action": "bind_phone",
        }

    _ensure_supplier_user_role(user)
    supplier, member = resolve_supplier_access(db, user, allow_pending_supplier=True)

    token_payload = _create_token_payload(user, supplier, member)
    _log_login(db, user, request=request, supplier=supplier)
    return {
        "bound": True,
        **token_payload,
    }


@router.post("/supplier/wechat-bind")
def supplier_wechat_bind(
    payload: SupplierWechatBindRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_auth),
) -> Any:
    _bind_openid_if_needed(db, current_user, payload.openid)
    db.commit()
    return {"message": "微信绑定成功"}


@router.get("/supplier/companies/search")
def search_supplier_companies(
    keyword: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
) -> Any:
    normalized_keyword = keyword.strip()
    suppliers = (
        db.query(Supplier)
        .filter(Supplier.status == "approved")
        .filter(
            or_(
                Supplier.name.ilike(f"%{normalized_keyword}%"),
                Supplier.social_credit_code.ilike(f"%{normalized_keyword}%"),
            )
        )
        .order_by(Supplier.status.asc(), Supplier.name.asc())
        .limit(20)
        .all()
    )
    return [
        {
            "id": supplier.id,
            "name": supplier.name,
            "social_credit_code": supplier.social_credit_code,
            "status": supplier.status,
        }
        for supplier in suppliers
    ]


@router.post("/supplier/upload-attachment")
async def upload_supplier_attachment(
    file: UploadFile = File(...),
) -> Any:
    if not file.filename:
        raise HTTPException(status_code=400, detail="文件名不能为空")

    ext = Path(file.filename).suffix.lower()
    allowed_extensions = {
        ".pdf",
        ".doc",
        ".docx",
        ".xls",
        ".xlsx",
        ".png",
        ".jpg",
        ".jpeg",
        ".zip",
        ".rar",
        ".7z",
        ".tar",
        ".gz",
        ".bz2",
        ".xz",
    }
    if ext not in allowed_extensions:
        raise HTTPException(status_code=400, detail="附件格式不支持")

    content = await file.read()

    month_bucket = datetime.now().strftime("%Y%m")
    target_dir = SUPPLIER_UPLOAD_ROOT / month_bucket
    target_dir.mkdir(parents=True, exist_ok=True)

    safe_name = Path(file.filename).name
    saved_name = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}_{safe_name}"
    saved_path = target_dir / saved_name
    saved_path.write_bytes(content)
    relative_path = f"/static/uploads/supplier_onboarding/{month_bucket}/{saved_name}"

    return {
        "message": "附件上传成功",
        "name": safe_name,
        "file_path": relative_path,
        "size": len(content),
        "uploaded_at": datetime.now().isoformat(),
    }


@router.post("/supplier/onboarding")
def supplier_onboarding(
    payload: SupplierOnboardingCreate,
    db: Session = Depends(get_db),
) -> Any:
    phone = validate_phone_or_raise(payload.phone)
    verify_sms_code(phone, "onboarding", payload.sms_code)

    company_name = (payload.company_name or "").strip()
    if not company_name:
        raise HTTPException(status_code=400, detail="公司名称不能为空")

    if db.query(Supplier).filter(Supplier.name == company_name).first():
        raise HTTPException(status_code=400, detail="该企业已存在，请直接申请加入已有供应商")

    social_credit_code = (payload.social_credit_code or "").strip() or None
    if social_credit_code:
        existing_code = db.query(Supplier).filter(Supplier.social_credit_code == social_credit_code).first()
        if existing_code:
            raise HTTPException(status_code=400, detail="该统一社会信用代码已存在，请直接申请加入已有供应商")

    user = _get_or_create_supplier_user(
        db,
        phone=phone,
        password=payload.password,
        openid=payload.openid,
    )

    supplier = Supplier(
        name=company_name,
        social_credit_code=social_credit_code,
        contact_person=(payload.contact_person or "").strip(),
        phone=phone,
        email=(payload.email or "").strip() or None,
        status="pending",
        user_id=user.id,
        application_attachments=payload.attachments or [],
        onboarding_note=(payload.onboarding_note or "").strip() or None,
    )
    db.add(supplier)
    db.flush()

    member = SupplierMember(
        supplier_id=supplier.id,
        user_id=user.id,
        role="admin",
        status="pending",
        member_name=(payload.contact_person or "").strip(),
        position="管理员",
        application_note="新供应商入驻首个联系人",
        application_attachments=payload.attachments or [],
        approval_mode="platform_admin",
    )
    db.add(member)
    db.commit()
    _invalidate_supplier_cache()

    return {
        "message": "入驻申请已提交，请等待平台审核",
        "supplier_id": supplier.id,
        "supplier_status": supplier.status,
        "member_status": member.status,
    }


@router.post("/supplier/join-request")
def supplier_join_request(
    payload: SupplierJoinRequestCreate,
    db: Session = Depends(get_db),
) -> Any:
    phone = validate_phone_or_raise(payload.phone)
    verify_sms_code(phone, "join", payload.sms_code)

    approval_mode = "supplier_admin"
    if False and approval_mode not in {"platform_admin", "supplier_admin"}:
        raise HTTPException(status_code=400, detail="审核方式不支持")

    company_name = (payload.company_name or "").strip()
    social_credit_code = (payload.social_credit_code or "").strip()
    if not company_name and not social_credit_code:
        raise HTTPException(status_code=400, detail="请填写公司名称或统一社会信用代码")

    supplier_query = db.query(Supplier).filter(Supplier.status == "approved")
    if social_credit_code:
        supplier_query = supplier_query.filter(Supplier.social_credit_code == social_credit_code)
    else:
        supplier_query = supplier_query.filter(Supplier.name == company_name)
    supplier = supplier_query.first()
    if not supplier:
        raise HTTPException(status_code=404, detail="未找到可加入的已审核供应商企业")

    user = _get_or_create_supplier_user(
        db,
        phone=phone,
        password=payload.password,
        openid=payload.openid,
    )

    existing_member = (
        db.query(SupplierMember)
        .filter(
            SupplierMember.supplier_id == supplier.id,
            SupplierMember.user_id == user.id,
        )
        .first()
    )
    if existing_member and existing_member.status == "active":
        raise HTTPException(status_code=400, detail="您已是该供应商企业成员")
    if existing_member and existing_member.status == "pending":
        raise HTTPException(status_code=400, detail="您已提交加入申请，请等待审核")

    member = existing_member or SupplierMember(
        supplier_id=supplier.id,
        user_id=user.id,
        role="member",
    )
    member.status = "pending"
    member.role = existing_member.role if existing_member and existing_member.role in {"owner", "admin"} else "member"
    member.member_name = (payload.member_name or "").strip()
    member.position = (payload.position or "").strip() or None
    member.application_note = (payload.application_note or "").strip() or None
    member.application_attachments = payload.attachments or []
    member.approval_mode = approval_mode
    member.reviewed_at = None
    member.reviewed_by = None
    member.review_comment = None
    db.add(member)
    db.commit()

    return {
        "message": "加入申请已提交，请等待审核",
        "supplier_id": supplier.id,
        "supplier_name": supplier.name,
        "member_status": member.status,
        "approval_mode": member.approval_mode,
    }


@router.get("/supplier/member-requests")
def get_supplier_member_requests(
    status_filter: str = "pending",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_auth),
) -> Any:
    if current_user.role in ["admin", "buyer", "buyer_manager"]:
        query = db.query(SupplierMember)
    elif current_user.role == "supplier":
        supplier, reviewer_member = get_supplier_context_for_user(db, current_user)
        if reviewer_member.role not in ["owner", "admin"]:
            raise HTTPException(status_code=403, detail="仅企业管理员可查看成员申请")
        query = db.query(SupplierMember).filter(
            SupplierMember.supplier_id == supplier.id,
            SupplierMember.approval_mode == "supplier_admin",
        )
    else:
        raise HTTPException(status_code=403, detail="Not authorized")

    if status_filter:
        query = query.filter(SupplierMember.status == status_filter)

    rows = query.order_by(SupplierMember.created_at.desc(), SupplierMember.id.desc()).all()
    result = []
    for row in rows:
        supplier = db.query(Supplier).filter(Supplier.id == row.supplier_id).first()
        user = db.query(User).filter(User.id == row.user_id).first()
        reviewer = db.query(User).filter(User.id == row.reviewed_by).first() if row.reviewed_by else None
        result.append(
            {
                "id": row.id,
                "supplier_id": row.supplier_id,
                "supplier_name": supplier.name if supplier else "",
                "social_credit_code": supplier.social_credit_code if supplier else "",
                "user_id": row.user_id,
                "phone": user.phone if user else "",
                "member_name": row.member_name,
                "position": row.position,
                "role": row.role,
                "status": row.status,
                "approval_mode": row.approval_mode,
                "application_note": row.application_note,
                "application_attachments": row.application_attachments or [],
                "review_comment": row.review_comment,
                "reviewed_by_name": reviewer.username if reviewer else None,
                "reviewed_at": row.reviewed_at,
                "created_at": row.created_at,
            }
        )
    return result


@router.put("/supplier/member-requests/{member_id}/review")
def review_supplier_member_request(
    member_id: int,
    payload: SupplierJoinRequestReview,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_auth),
) -> Any:
    member = db.query(SupplierMember).filter(SupplierMember.id == member_id).first()
    if not member:
        raise HTTPException(status_code=404, detail="成员申请不存在")

    _require_supplier_member_reviewer(db, current_user, member)

    if member.status != "pending":
        raise HTTPException(status_code=400, detail="该申请已处理")

    supplier = db.query(Supplier).filter(Supplier.id == member.supplier_id).first()
    if not supplier:
        raise HTTPException(status_code=404, detail="供应商不存在")

    review_status = (payload.status or "").strip().lower()
    if review_status not in {"approved", "rejected"}:
        raise HTTPException(status_code=400, detail="审核结果不支持")

    if review_status == "approved":
        if supplier.status != "approved":
            raise HTTPException(status_code=400, detail="企业尚未审核通过，暂不能激活成员")
        member.status = "active"
        member.role = (payload.role or member.role or "member").strip()
    else:
        member.status = "rejected"

    member.reviewed_by = current_user.id
    member.reviewed_at = datetime.now()
    member.review_comment = (payload.review_comment or "").strip() or None
    db.add(member)
    db.commit()

    return {
        "message": "成员申请处理成功",
        "id": member.id,
        "status": member.status,
        "role": member.role,
    }


@router.post("/register", response_model=UserSchema)
def register_user(
    *,
    db: Session = Depends(get_db),
    user_in: UserCreate,
    request: Request = None,
) -> Any:
    user = db.query(User).filter(User.username == user_in.username).first()
    if user:
        raise HTTPException(
            status_code=400,
            detail="The user with this username already exists in the system.",
        )

    normalized_phone = normalize_phone(user_in.phone) or None
    if normalized_phone and db.query(User).filter(User.phone == normalized_phone).first():
        raise HTTPException(status_code=400, detail="该手机号已存在")

    user = User(
        username=user_in.username,
        password_hash=security.get_password_hash(user_in.password),
        role=user_in.role,
        department=user_in.department or ("采购部" if user_in.role in ["buyer", "buyer_manager"] else None),
        phone=normalized_phone,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    if user.role == "supplier":
        supplier = Supplier(
            name=user_in.company_name or user.username,
            contact_person=user_in.contact_person,
            phone=normalized_phone,
            email=user_in.email,
            status="pending",
            user_id=user.id,
        )
        db.add(supplier)
        db.flush()
        db.add(
            SupplierMember(
                supplier_id=supplier.id,
                user_id=user.id,
                role="owner",
                status="pending",
                member_name=user_in.contact_person,
                position="owner",
                application_note="历史注册接口创建",
                approval_mode="platform_admin",
            )
        )
        db.commit()

    from routers.system import log_operation

    log_operation(
        db,
        user.id,
        "CREATE_USER",
        f"新账号注册 {user.username} (角色: {user.role})",
        request=request,
        module="认证中心",
        target_type="账号",
        target_name=user.username,
        result="success",
        extra_data={
            "role": user.role,
            "company_name": user_in.company_name or "",
        },
    )

    return user


@router.get("/users")
def get_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_auth),
) -> Any:
    if not _is_admin_like(current_user):
        raise HTTPException(status_code=403, detail="只有超级管理员或采购部经理可以访问账号列表")

    users = db.query(User).filter(User.role.in_(["admin", "buyer", "buyer_manager"])).all()
    return [{"id": u.id, "username": u.username, "role": u.role, "department": u.department} for u in users]


@router.delete("/users/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_auth),
    request: Request = None,
) -> Any:
    if not _is_admin_like(current_user):
        raise HTTPException(status_code=403, detail="只有超级管理员或采购部经理可以删除账号")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="账号不存在")

    if user.role in ["admin", "buyer_manager"] and user.id == current_user.id:
        raise HTTPException(status_code=400, detail="不能删除当前正在使用的管理账号")

    try:
        from models import InquiryTask, WarningMessage
        from routers.system import log_operation

        db.query(InquiryTask).filter(InquiryTask.buyer_id == user.id).update({"buyer_id": None})
        db.query(InquiryTask).filter(InquiryTask.created_by == user.id).update({"created_by": None})
        db.query(WarningMessage).filter(WarningMessage.buyer_id == user.id).update({"buyer_id": None})
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
            extra_data={"deleted_role": user.role},
        )

        db.delete(user)
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"删除失败，外键冲突或系统错误: {exc}") from exc

    return {"message": "账号已删除"}
