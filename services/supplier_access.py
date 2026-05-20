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
    role_priority = {"owner": 0, "admin": 1, "member": 2}
    return role_priority.get((member.role or "").lower(), 9)


def resolve_supplier_access(db: Session, user: User) -> tuple[Supplier, SupplierMember]:
    memberships = get_user_memberships(db, user.id)
    if not memberships:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="您尚未加入任何供应商企业",
        )

    memberships = sorted(memberships, key=_membership_priority)
    supplier_ids = [member.supplier_id for member in memberships]
    suppliers = db.query(Supplier).filter(Supplier.id.in_(supplier_ids)).all()
    supplier_map = {supplier.id: supplier for supplier in suppliers}

    for member in memberships:
        supplier = supplier_map.get(member.supplier_id)
        if supplier and supplier.status == "approved" and member.status == "active":
            return supplier, member

    for member in memberships:
        supplier = supplier_map.get(member.supplier_id)
        if supplier and supplier.status == "pending":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="企业待审核")

    for member in memberships:
        if member.status == "pending":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="成员申请待审核")

    for member in memberships:
        supplier = supplier_map.get(member.supplier_id)
        if supplier and supplier.status == "rejected":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="企业审核未通过")

    for member in memberships:
        if member.status in ["disabled", "rejected"]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账号已停用")

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="您当前没有可用的供应商企业权限",
    )


def get_supplier_context_for_user(db: Session, user: User) -> tuple[Supplier, SupplierMember]:
    if user.role != "supplier":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    return resolve_supplier_access(db, user)
