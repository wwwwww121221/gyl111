from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from models import Supplier, SupplierMember, User


def normalize_phone(phone: str | None) -> str:
    return (phone or "").strip()


def get_user_by_phone(db: Session, phone: str) -> User | None:
    normalized_phone = normalize_phone(phone)
    if not normalized_phone:
        return None
    return db.query(User).filter(User.phone == normalized_phone).first()


def get_user_memberships(db: Session, user_id: int) -> list[SupplierMember]:
    return (
        db.query(SupplierMember)
        .filter(SupplierMember.user_id == user_id)
        .order_by(SupplierMember.created_at.asc(), SupplierMember.id.asc())
        .all()
    )


def _membership_priority(member: SupplierMember) -> int:
    role_priority = {"admin": 0, "member": 1}
    return role_priority.get((member.role or "").lower(), 9)


def _backfill_memberships_for_user(db: Session, user: User) -> list[SupplierMember]:
    suppliers = (
        db.query(Supplier)
        .filter(Supplier.user_id == user.id)
        .order_by(Supplier.created_at.asc(), Supplier.id.asc())
        .all()
    )
    if not suppliers:
        return []

    created = False
    for supplier in suppliers:
        existing_member = (
            db.query(SupplierMember)
            .filter(
                SupplierMember.supplier_id == supplier.id,
                SupplierMember.user_id == user.id,
            )
            .first()
        )
        if existing_member:
            continue

        member_status = "pending"
        if supplier.status == "approved":
            member_status = "active"
        elif supplier.status == "rejected":
            member_status = "disabled"

        db.add(
            SupplierMember(
                supplier_id=supplier.id,
                user_id=user.id,
                role="admin",
                status=member_status,
                member_name=supplier.contact_person,
                position="管理员",
                application_note="系统自动补建供应商成员关系",
                approval_mode="platform_admin",
                reviewed_at=supplier.reviewed_at,
                reviewed_by=supplier.reviewer_id,
                review_comment=supplier.review_comment,
            )
        )
        created = True

    if created:
        db.flush()

    return get_user_memberships(db, user.id)


def _load_supplier_memberships(
    db: Session,
    user: User,
) -> tuple[list[SupplierMember], dict[int, Supplier]]:
    memberships = get_user_memberships(db, user.id)
    if not memberships:
        memberships = _backfill_memberships_for_user(db, user)
    memberships = sorted(memberships, key=_membership_priority)
    supplier_ids = [member.supplier_id for member in memberships]
    suppliers = db.query(Supplier).filter(Supplier.id.in_(supplier_ids)).all() if supplier_ids else []
    supplier_map = {supplier.id: supplier for supplier in suppliers}
    return memberships, supplier_map


def resolve_supplier_access(
    db: Session,
    user: User,
    allow_pending_supplier: bool = False,
) -> tuple[Supplier, SupplierMember]:
    memberships, supplier_map = _load_supplier_memberships(db, user)
    if not memberships:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="鎮ㄥ皻鏈姞鍏ヤ换浣曚緵搴斿晢浼佷笟",
        )

    for member in memberships:
        supplier = supplier_map.get(member.supplier_id)
        if supplier and supplier.status == "approved" and member.status == "active":
            return supplier, member

    if allow_pending_supplier:
        for member in memberships:
            supplier = supplier_map.get(member.supplier_id)
            if supplier and supplier.status == "pending":
                return supplier, member

    for member in memberships:
        supplier = supplier_map.get(member.supplier_id)
        if supplier and supplier.status == "pending":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="浼佷笟寰呭鏍?")

    for member in memberships:
        if member.status == "pending":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="鎴愬憳鐢宠寰呭鏍?")

    for member in memberships:
        supplier = supplier_map.get(member.supplier_id)
        if supplier and supplier.status == "rejected":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="浼佷笟瀹℃牳鏈€氳繃")

    for member in memberships:
        if member.status in ["disabled", "rejected"]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="璐﹀彿宸插仠鐢?")

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="鎮ㄥ綋鍓嶆病鏈夊彲鐢ㄧ殑渚涘簲鍟嗕紒涓氭潈闄?",
    )


def get_supplier_context_for_user(db: Session, user: User) -> tuple[Supplier, SupplierMember]:
    if user.role != "supplier":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    return resolve_supplier_access(db, user)


def get_supplier_context_for_portal(db: Session, user: User) -> tuple[Supplier, SupplierMember]:
    if user.role != "supplier":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    return resolve_supplier_access(db, user, allow_pending_supplier=True)
