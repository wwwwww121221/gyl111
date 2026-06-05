from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any

from dateutil.relativedelta import relativedelta
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from models import PurchaseOrderMonthlyStat, PurchaseOrderSummary


def trim_expr(column):
    return func.trim(column)


def get_summary_rows_by_material_codes(db: Session, material_codes: list[str]):
    normalized_codes = [code for code in {str(code or "").strip() for code in material_codes} if code]
    if not normalized_codes:
        return []
    trimmed_code = trim_expr(PurchaseOrderSummary.material_code)
    return (
        db.query(PurchaseOrderSummary)
        .filter(trimmed_code.in_(normalized_codes))
        .all()
    )


def get_summary_rows_by_material_names(db: Session, material_names: list[str]):
    normalized_names = [name for name in {str(name or "").strip() for name in material_names} if name]
    if not normalized_names:
        return []
    return (
        db.query(PurchaseOrderSummary)
        .filter(trim_expr(PurchaseOrderSummary.material_name).in_(normalized_names))
        .all()
    )


def get_material_supplier_counts(rows: list[PurchaseOrderSummary]) -> dict[str, list[dict[str, Any]]]:
    result = defaultdict(list)
    for row in sorted(rows, key=lambda item: (-int(item.order_count or 0), str(item.supplier_name or ""))):
        material_code = str(row.material_code or "").strip()
        if not material_code:
            continue
        result[material_code].append({
            "supplier_code": row.supplier_code,
            "supplier_name": row.supplier_name,
            "count": int(row.order_count or 0),
        })
    return result


def get_monthly_rows_for_supplier(db: Session, supplier_code: str, months: int = 6):
    cutoff = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0) - relativedelta(months=months - 1)
    return (
        db.query(PurchaseOrderMonthlyStat)
        .filter(
            PurchaseOrderMonthlyStat.supplier_code == supplier_code,
            PurchaseOrderMonthlyStat.stat_month >= cutoff,
        )
        .order_by(PurchaseOrderMonthlyStat.stat_month.asc())
        .all()
    )


def get_monthly_rows_for_material(db: Session, material_code: str):
    return (
        db.query(PurchaseOrderMonthlyStat)
        .filter(trim_expr(PurchaseOrderMonthlyStat.material_code) == str(material_code or "").strip())
        .order_by(PurchaseOrderMonthlyStat.stat_month.asc())
        .all()
    )
