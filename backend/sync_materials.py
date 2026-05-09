from models import SessionLocal, Material
from kingdee_erp_tool.services.basic_data import fetch_materials_from_erp
import logging

logger = logging.getLogger(__name__)

def sync_materials(page_size: int = 500):
    """
    从金蝶ERP同步物料主数据
    """
    db = SessionLocal()
    try:
        synced_count = 0
        start_row = 0
        while True:
            erp_materials = fetch_materials_from_erp(limit=page_size, start_row=start_row)
            if not erp_materials:
                break

            for m in erp_materials:
                code = m.get("code")
                if not code:
                    continue

                exists = db.query(Material).filter(Material.code == code).first()
                if exists:
                    exists.name = m.get("name")
                    exists.specification = m.get("specification")
                    exists.erp_cls_id = m.get("erp_cls_id")
                    exists.group_name = m.get("group_name")
                    exists.base_unit = m.get("base_unit")
                else:
                    new_mat = Material(
                        code=code,
                        name=m.get("name"),
                        specification=m.get("specification"),
                        erp_cls_id=m.get("erp_cls_id"),
                        group_name=m.get("group_name"),
                        base_unit=m.get("base_unit")
                    )
                    db.add(new_mat)
                synced_count += 1

            db.commit()
            start_row += len(erp_materials)
            logger.info(f"Material batch done: start_row={start_row}, batch={len(erp_materials)}")
            if len(erp_materials) < page_size:
                break

        logger.info(f"Successfully synced {synced_count} materials from ERP.")
        
    except Exception as e:
        logger.error(f"Error syncing materials: {str(e)}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    sync_materials()
