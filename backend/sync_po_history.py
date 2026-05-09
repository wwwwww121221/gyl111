from models import SessionLocal, PurchaseOrderHistory
from kingdee_erp_tool.services.purchase import get_historical_purchase_prices
from datetime import datetime
import hashlib
import logging

logger = logging.getLogger(__name__)


def _parse_datetime(value: str):
    if not value:
        return None
    # ERP may return both "YYYY-mm-dd HH:MM:SS" and ISO "YYYY-mm-ddTHH:MM:SS"
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")


def _stable_entry_id(record: dict) -> str:
    raw = "|".join([
        str(record.get("bill_no") or ""),
        str(record.get("date") or ""),
        str(record.get("supplier_code") or ""),
        str(record.get("material_code") or ""),
        str(record.get("qty") or ""),
        str(record.get("price") or ""),
    ])
    return hashlib.md5(raw.encode("utf-8")).hexdigest()

def sync_po_history(start_date: str = "2025-01-01T00:00:00", end_date: str = None, page_size: int = 500):
    """
    同步采购订单历史记录（全量或增量）
    """
    db = SessionLocal()
    try:
        logger.info(f"Starting PO history sync from {start_date} to {end_date}")
        start_dt = _parse_datetime(start_date) if start_date else None
        end_dt = _parse_datetime(end_date) if end_date else None
        synced_count = 0
        start_row = 0
        while True:
            records = get_historical_purchase_prices(
                start_date=start_date,
                end_date=end_date,
                start_row=start_row,
                limit=page_size,
            )
            if not records:
                break

            seen_entry_ids = set()
            batch_new = 0
            for record in records:
                entry_id = record.get("erp_entry_id") or _stable_entry_id(record)
                if entry_id in seen_entry_ids:
                    continue
                seen_entry_ids.add(entry_id)
                record_date = _parse_datetime(record.get("date"))
                if start_dt and record_date and record_date < start_dt:
                    continue
                if end_dt and record_date and record_date > end_dt:
                    continue
                exists = db.query(PurchaseOrderHistory).filter(
                    PurchaseOrderHistory.erp_entry_id == entry_id
                ).first()

                if not exists:
                    new_po = PurchaseOrderHistory(
                        erp_entry_id=entry_id,
                        bill_no=record.get("bill_no"),
                        project_number=record.get("project_number"),
                        supplier_code=record.get("supplier_code"),
                        supplier_name=record.get("supplier_name"),
                        material_code=record.get("material_code"),
                        material_name=record.get("material_name"),
                        qty=record.get("qty"),
                        price=record.get("price"),
                        tax_net_price=record.get("tax_net_price"),
                        date=record_date
                    )
                    db.add(new_po)
                    synced_count += 1
                    batch_new += 1

            db.commit()
            start_row += len(records)
            logger.info(f"PO batch done: start_row={start_row}, batch={len(records)}, new={batch_new}")
            # Defensive stop: some ERP endpoints may ignore StartRow and return the same page repeatedly.
            if batch_new == 0:
                break
            if len(records) < page_size:
                break

        logger.info(f"Successfully synced {synced_count} new PO history records.")
        
    except Exception as e:
        logger.error(f"Error syncing PO history: {str(e)}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    sync_po_history()
