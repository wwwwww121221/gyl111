from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import String, cast, func, or_
from sqlalchemy.orm import Session
import asyncio
import logging

from models import Contract, InquirySupplier, InquiryTask, Supplier, User, get_db, SessionLocal
from routers.inquiry import get_current_user
from services.contract_service import generate_contract_pdf


router = APIRouter()
BASE_DIR = Path(__file__).resolve().parents[1]
logger = logging.getLogger(__name__)


def _require_buyer_or_admin(current_user: User):
    if current_user.role not in ["admin", "buyer"]:
        raise HTTPException(status_code=403, detail="Not authorized")


def _resolve_local_path(file_path: str) -> Path:
    if file_path.startswith("/static/"):
        return BASE_DIR / file_path.lstrip("/")
    candidate = Path(file_path)
    return candidate if candidate.is_absolute() else BASE_DIR / file_path


def _generate_contract_pdf_background(inquiry_supplier_id: int) -> None:
    db = SessionLocal()
    try:
        asyncio.run(generate_contract_pdf(db, inquiry_supplier_id))
    except Exception:
        logger.exception("合同生成失败, inquiry_supplier_id=%s", inquiry_supplier_id)
        try:
            contract_record = db.query(Contract).filter(Contract.inquiry_supplier_id == inquiry_supplier_id).first()
            if contract_record:
                contract_record.status = "failed"
                db.add(contract_record)
                db.commit()
        except Exception:
            logger.exception("更新合同失败状态失败, inquiry_supplier_id=%s", inquiry_supplier_id)
    finally:
        db.close()


@router.get("/list")
def get_contract_list(
    skip: int = 0,
    limit: int = 20,
    keyword: str = "",
    task_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    _require_buyer_or_admin(current_user)
    if limit <= 0:
        limit = 20
    if limit > 200:
        limit = 200

    contract_no_expr = func.concat(
        "HT-",
        cast(Contract.task_id, String),
        "-",
        cast(Contract.inquiry_supplier_id, String),
    )

    query = (
        db.query(
            Contract,
            InquiryTask.title.label("task_title"),
            Supplier.name.label("supplier_name"),
        )
        .join(InquiryTask, Contract.task_id == InquiryTask.id)
        .join(InquirySupplier, Contract.inquiry_supplier_id == InquirySupplier.id)
        .join(Supplier, InquirySupplier.supplier_id == Supplier.id)
    )
    
    if current_user.role == "buyer":
        query = query.filter(InquiryTask.buyer_id == current_user.id)
    if task_id is not None:
        query = query.filter(Contract.task_id == task_id)
        
    query = query.order_by(Contract.id.desc())
    keyword = (keyword or "").strip()
    if keyword:
        like_kw = f"%{keyword}%"
        query = query.filter(
            or_(
                contract_no_expr.ilike(like_kw),
                InquiryTask.title.ilike(like_kw),
                Supplier.name.ilike(like_kw),
                Contract.status.ilike(like_kw),
            )
        )

    total = query.count()
    rows = query.offset(skip).limit(limit).all()

    items = []
    for contract, task_title, supplier_name in rows:
        contract_no = f"HT-{contract.task_id}-{contract.inquiry_supplier_id}"
        items.append(
            {
                "id": contract.id,
                "contract_no": contract_no,
                "inquiry_name": task_title,
                "supplier_name": supplier_name,
                "total_amount": contract.total_amount,
                "status": contract.status,
            }
        )
    return {"total": total, "skip": skip, "limit": limit, "items": items}


@router.get("/{contract_id}/pdf")
def preview_or_download_contract_pdf(
    contract_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_buyer_or_admin(current_user)
    contract = db.query(Contract).filter(Contract.id == contract_id).first()
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    if not contract.pdf_path:
        raise HTTPException(status_code=404, detail="Contract PDF not generated")

    local_path = _resolve_local_path(contract.pdf_path)
    if not local_path.exists():
        history_versions = list(contract.history_versions or [])
        history_versions.append(
            {
                "pdf_path": contract.pdf_path,
                "generated_at": datetime.now().isoformat(),
                "event": "file_missing_auto_cleanup",
            }
        )
        contract.history_versions = history_versions
        contract.pdf_path = None
        contract.status = "failed"
        db.add(contract)
        db.commit()
        raise HTTPException(status_code=404, detail="PDF file not found")

    return FileResponse(
        path=str(local_path),
        media_type="application/pdf",
        filename=local_path.name,
    )


@router.post("/{contract_id}/regenerate")
def regenerate_contract_pdf(
    contract_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    _require_buyer_or_admin(current_user)
    contract = db.query(Contract).filter(Contract.id == contract_id).first()
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")

    if contract.pdf_path:
        history_versions = list(contract.history_versions or [])
        history_versions.append(
            {
                "pdf_path": contract.pdf_path,
                "generated_at": datetime.now().isoformat(),
                "event": "buyer_regenerated",
            }
        )
        contract.history_versions = history_versions
        contract.pdf_path = None

    contract.status = "generating"
    db.add(contract)
    db.commit()
    db.refresh(contract)

    background_tasks.add_task(_generate_contract_pdf_background, contract.inquiry_supplier_id)
    return {"message": "合同正在重新生成", "id": contract.id}


@router.delete("/{contract_id}/pdf")
def delete_contract_pdf(
    contract_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    _require_buyer_or_admin(current_user)
    contract = db.query(Contract).filter(Contract.id == contract_id).first()
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    if not contract.pdf_path:
        return {"message": "Contract PDF already empty", "id": contract.id}

    current_pdf_path = contract.pdf_path
    local_path = _resolve_local_path(current_pdf_path)
    if local_path.exists():
        local_path.unlink()

    history_versions = list(contract.history_versions or [])
    history_versions.append(
        {
            "pdf_path": current_pdf_path,
            "generated_at": datetime.now().isoformat(),
            "event": "deleted",
        }
    )
    contract.history_versions = history_versions
    contract.pdf_path = None
    contract.status = "deleted"
    db.add(contract)
    db.commit()
    db.refresh(contract)
    return {"message": "Contract PDF deleted successfully", "id": contract.id}


@router.delete("/{contract_id}")
def delete_contract(
    contract_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    _require_buyer_or_admin(current_user)
    contract = db.query(Contract).filter(Contract.id == contract_id).first()
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")

    if contract.pdf_path:
        local_path = _resolve_local_path(contract.pdf_path)
        if local_path.exists():
            try:
                local_path.unlink()
            except Exception:
                pass

    db.delete(contract)
    db.commit()
    return {"message": "Contract deleted successfully", "id": contract_id}
