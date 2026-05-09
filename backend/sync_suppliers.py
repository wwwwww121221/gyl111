from models import SessionLocal, Supplier
from kingdee_erp_tool.services.basic_data import fetch_suppliers_from_erp
import logging

logger = logging.getLogger(__name__)

def sync_suppliers(page_size: int = 500):
    """
    从金蝶ERP同步供应商主数据
    """
    db = SessionLocal()
    try:
        synced_count = 0
        start_row = 0
        while True:
            erp_suppliers = fetch_suppliers_from_erp(limit=page_size, start_row=start_row)
            if not erp_suppliers:
                break

            for s in erp_suppliers:
                code = s.get("code")
                if not code:
                    continue
                # Session uses autoflush=False; flush pending rows so duplicate checks see latest inserts.
                db.flush()

                name = s.get("name")
                short_name = s.get("short_name")
                group_name = s.get("group_name")
                grade = s.get("grade")

                exists = db.query(Supplier).filter(Supplier.code == code).first()
                if exists:
                    # Update existing
                    exists.name = name
                    exists.short_name = short_name
                    exists.group_name = group_name
                    exists.grade = grade
                else:
                    # 检查名字是否已存在（避免冲突）
                    name_exists = db.query(Supplier).filter(Supplier.name == name).first()
                    if name_exists:
                        name_exists.code = code
                        name_exists.short_name = short_name
                        name_exists.group_name = group_name
                        name_exists.grade = grade
                    else:
                        # Create new
                        new_sup = Supplier(
                            code=code,
                            name=name,
                            short_name=short_name,
                            group_name=group_name,
                            grade=grade,
                            status="approved" # 自动同步的认为是已审核
                        )
                        db.add(new_sup)
                synced_count += 1

            db.commit()
            start_row += len(erp_suppliers)
            logger.info(f"Supplier batch done: start_row={start_row}, batch={len(erp_suppliers)}")
            if len(erp_suppliers) < page_size:
                break

        logger.info(f"Successfully synced {synced_count} suppliers from ERP.")
        
    except Exception as e:
        logger.error(f"Error syncing suppliers: {str(e)}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    sync_suppliers()
