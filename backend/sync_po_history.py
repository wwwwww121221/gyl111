from collections import defaultdict
from datetime import datetime, timedelta
import logging

from kingdee_erp_tool.services.purchase import get_historical_purchase_prices
from models import PurchaseOrderMonthlyStat, PurchaseOrderSummary, SessionLocal

logger = logging.getLogger(__name__)


def _parse_datetime(value: str):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")


def _month_start(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _aggregate_po_stats(records: list[dict]):
    recent_cutoff = datetime.now() - timedelta(days=30)
    summary_map = defaultdict(lambda: {
        "supplier_name": "",
        "material_name": "",
        "order_count": 0,
        "total_qty": 0.0,
        "total_amount": 0.0,
        "price_total": 0.0,
        "price_count": 0,
        "tax_price_total": 0.0,
        "tax_price_count": 0,
        "latest_price": None,
        "latest_tax_net_price": None,
        "latest_date": None,
        "lowest_price": None,
        "lowest_date": None,
        "highest_price": None,
        "highest_date": None,
        "recent_tax_price_total": 0.0,
        "recent_tax_price_count": 0,
    })
    monthly_map = defaultdict(lambda: {
        "supplier_name": "",
        "material_name": "",
        "order_count": 0,
        "total_qty": 0.0,
        "total_amount": 0.0,
        "tax_price_total": 0.0,
        "tax_price_count": 0,
        "min_tax_net_price": None,
        "max_tax_net_price": None,
    })

    total_records = 0
    for record in records:
        record_date = _parse_datetime(record.get("date"))
        supplier_code = str(record.get("supplier_code") or "").strip()
        material_code = str(record.get("material_code") or "").strip()
        if not supplier_code or not material_code:
            continue

        supplier_name = str(record.get("supplier_name") or "").strip()
        material_name = str(record.get("material_name") or "").strip()
        qty = float(record.get("qty") or 0.0)
        price = float(record.get("price") or 0.0)
        tax_net_price = float(record.get("tax_net_price") or 0.0)
        amount = qty * tax_net_price

        summary_key = (supplier_code, material_code)
        summary = summary_map[summary_key]
        summary["supplier_name"] = supplier_name or summary["supplier_name"]
        summary["material_name"] = material_name or summary["material_name"]
        summary["order_count"] += 1
        summary["total_qty"] += qty
        summary["total_amount"] += amount

        if price > 0:
            summary["price_total"] += price
            summary["price_count"] += 1
        if tax_net_price > 0:
            summary["tax_price_total"] += tax_net_price
            summary["tax_price_count"] += 1
            if summary["lowest_price"] is None or tax_net_price < summary["lowest_price"]:
                summary["lowest_price"] = tax_net_price
                summary["lowest_date"] = record_date
            if summary["highest_price"] is None or tax_net_price > summary["highest_price"]:
                summary["highest_price"] = tax_net_price
                summary["highest_date"] = record_date

        if record_date and (summary["latest_date"] is None or record_date > summary["latest_date"]):
            summary["latest_date"] = record_date
            summary["latest_price"] = price if price > 0 else None
            summary["latest_tax_net_price"] = tax_net_price if tax_net_price > 0 else None

        if record_date and record_date >= recent_cutoff and tax_net_price > 0:
            summary["recent_tax_price_total"] += tax_net_price
            summary["recent_tax_price_count"] += 1

        stat_month = _month_start(record_date)
        if stat_month is not None:
            monthly_key = (supplier_code, material_code, stat_month)
            monthly = monthly_map[monthly_key]
            monthly["supplier_name"] = supplier_name or monthly["supplier_name"]
            monthly["material_name"] = material_name or monthly["material_name"]
            monthly["order_count"] += 1
            monthly["total_qty"] += qty
            monthly["total_amount"] += amount
            if tax_net_price > 0:
                monthly["tax_price_total"] += tax_net_price
                monthly["tax_price_count"] += 1
                if monthly["min_tax_net_price"] is None or tax_net_price < monthly["min_tax_net_price"]:
                    monthly["min_tax_net_price"] = tax_net_price
                if monthly["max_tax_net_price"] is None or tax_net_price > monthly["max_tax_net_price"]:
                    monthly["max_tax_net_price"] = tax_net_price

        total_records += 1

    return summary_map, monthly_map, total_records


def _delete_scope_rows(db, supplier_code: str | None = None, material_code: str | None = None):
    summary_query = db.query(PurchaseOrderSummary)
    monthly_query = db.query(PurchaseOrderMonthlyStat)

    if supplier_code:
        summary_query = summary_query.filter(PurchaseOrderSummary.supplier_code == supplier_code)
        monthly_query = monthly_query.filter(PurchaseOrderMonthlyStat.supplier_code == supplier_code)
    if material_code:
        summary_query = summary_query.filter(PurchaseOrderSummary.material_code == material_code)
        monthly_query = monthly_query.filter(PurchaseOrderMonthlyStat.material_code == material_code)

    summary_query.delete(synchronize_session=False)
    monthly_query.delete(synchronize_session=False)


def _save_aggregated_po_stats(
    db,
    summary_map,
    monthly_map,
    supplier_code: str | None = None,
    material_code: str | None = None,
):
    _delete_scope_rows(db, supplier_code=supplier_code, material_code=material_code)

    for (row_supplier_code, row_material_code), item in summary_map.items():
        db.add(PurchaseOrderSummary(
            supplier_code=row_supplier_code,
            supplier_name=item["supplier_name"],
            material_code=row_material_code,
            material_name=item["material_name"],
            order_count=item["order_count"],
            total_qty=item["total_qty"],
            total_amount=item["total_amount"],
            avg_price=(item["price_total"] / item["price_count"]) if item["price_count"] else 0.0,
            avg_tax_net_price=(item["tax_price_total"] / item["tax_price_count"]) if item["tax_price_count"] else 0.0,
            latest_price=item["latest_price"],
            latest_tax_net_price=item["latest_tax_net_price"],
            latest_date=item["latest_date"],
            lowest_price=item["lowest_price"],
            lowest_date=item["lowest_date"],
            highest_price=item["highest_price"],
            highest_date=item["highest_date"],
            avg_30_days=(item["recent_tax_price_total"] / item["recent_tax_price_count"]) if item["recent_tax_price_count"] else 0.0,
            recent_order_count=item["recent_tax_price_count"],
        ))

    for (row_supplier_code, row_material_code, stat_month), item in monthly_map.items():
        db.add(PurchaseOrderMonthlyStat(
            supplier_code=row_supplier_code,
            supplier_name=item["supplier_name"],
            material_code=row_material_code,
            material_name=item["material_name"],
            stat_month=stat_month,
            order_count=item["order_count"],
            total_qty=item["total_qty"],
            total_amount=item["total_amount"],
            avg_tax_net_price=(item["tax_price_total"] / item["tax_price_count"]) if item["tax_price_count"] else 0.0,
            min_tax_net_price=item["min_tax_net_price"],
            max_tax_net_price=item["max_tax_net_price"],
        ))


def sync_recent_po_history_for_analysis(
    supplier_code: str | None = None,
    material_code: str | None = None,
    months_back: int = 12,
    page_size: int = 500,
):
    """
    按供应商或物料范围回补近一年的采购汇总数据，不清空其他范围的数据。
    """
    db = SessionLocal()
    try:
        logger.info(
            "Starting scoped PO sync for analysis. supplier_code=%s material_code=%s months_back=%s",
            supplier_code,
            material_code,
            months_back,
        )
        start_row = 0
        all_records = []
        while True:
            records = get_historical_purchase_prices(
                supplier_code=supplier_code,
                material_code=material_code,
                months_back=months_back,
                start_row=start_row,
                limit=page_size,
            )
            if not records:
                break
            all_records.extend(records)
            start_row += len(records)
            logger.info("Scoped PO sync batch done: start_row=%s, batch=%s", start_row, len(records))
            if len(records) < page_size:
                break

        if not all_records:
            logger.info(
                "Scoped PO sync found no ERP data. supplier_code=%s material_code=%s",
                supplier_code,
                material_code,
            )
            return 0

        summary_map, monthly_map, total_records = _aggregate_po_stats(all_records)
        _save_aggregated_po_stats(
            db,
            summary_map,
            monthly_map,
            supplier_code=supplier_code,
            material_code=material_code,
        )
        db.commit()
        logger.info(
            "Scoped PO sync completed. supplier_code=%s material_code=%s records=%s summaries=%s monthly=%s",
            supplier_code,
            material_code,
            total_records,
            len(summary_map),
            len(monthly_map),
        )
        return total_records
    except Exception:
        db.rollback()
        logger.exception(
            "Scoped PO sync failed. supplier_code=%s material_code=%s",
            supplier_code,
            material_code,
        )
        raise
    finally:
        db.close()


def sync_po_history(start_date: str = "2025-01-01T00:00:00", end_date: str = None, page_size: int = 500):
    """
    直接同步 ERP 历史订单并重建统计表，不再落原始明细表。
    """
    db = SessionLocal()
    try:
        logger.info("Starting PO summary rebuild from %s to %s", start_date, end_date)
        start_dt = _parse_datetime(start_date) if start_date else None
        end_dt = _parse_datetime(end_date) if end_date else None
        start_row = 0
        all_records = []
        while True:
            records = get_historical_purchase_prices(
                start_date=start_date,
                end_date=end_date,
                start_row=start_row,
                limit=page_size,
            )
            if not records:
                break

            for record in records:
                record_date = _parse_datetime(record.get("date"))
                if start_dt and record_date and record_date < start_dt:
                    continue
                if end_dt and record_date and record_date > end_dt:
                    continue
                all_records.append(record)

            start_row += len(records)
            logger.info("PO stats batch done: start_row=%s, batch=%s", start_row, len(records))
            if len(records) < page_size:
                break

        summary_map, monthly_map, total_records = _aggregate_po_stats(all_records)
        db.query(PurchaseOrderMonthlyStat).delete()
        db.query(PurchaseOrderSummary).delete()
        db.flush()
        _save_aggregated_po_stats(db, summary_map, monthly_map)

        db.commit()
        logger.info(
            "Successfully rebuilt PO stats. records=%s, summaries=%s, monthly=%s",
            total_records,
            len(summary_map),
            len(monthly_map),
        )

    except Exception as e:
        logger.error("Error syncing PO history summary: %s", str(e))
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    sync_po_history()
