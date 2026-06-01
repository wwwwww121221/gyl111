import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from models import SessionLocal, User, Supplier, SupplierMember
from core.security import get_password_hash

TEST_SUPPLIERS = [
    {
        "name": "华鑫精密制造有限公司",
        "code": "SUP-001",
        "contact_person": "张伟",
        "phone": "13800001001",
        "email": "zhangwei@huaxin.com",
        "grade": "A级",
        "level": "core",
        "short_name": "华鑫精密",
    },
    {
        "name": "鼎盛电子科技有限公司",
        "code": "SUP-002",
        "contact_person": "李娜",
        "phone": "13800001002",
        "email": "lina@dingsheng.com",
        "grade": "A级",
        "level": "core",
        "short_name": "鼎盛电子",
    },
    {
        "name": "瑞达新材料股份有限公司",
        "code": "SUP-003",
        "contact_person": "王强",
        "phone": "13800001003",
        "email": "wangqiang@ruida.com",
        "grade": "B级",
        "level": "general",
        "short_name": "瑞达新材",
    },
    {
        "name": "恒通物流设备有限公司",
        "code": "SUP-004",
        "contact_person": "赵敏",
        "phone": "13800001004",
        "email": "zhaomin@hengtong.com",
        "grade": "B级",
        "level": "general",
        "short_name": "恒通物流",
    },
    {
        "name": "锦程机械零部件厂",
        "code": "SUP-005",
        "contact_person": "陈刚",
        "phone": "13800001005",
        "email": "chengang@jincheng.com",
        "grade": "一般",
        "level": "general",
        "short_name": "锦程机械",
    },
]

DEFAULT_PASSWORD = "123456"


def seed():
    db = SessionLocal()
    try:
        for item in TEST_SUPPLIERS:
            existing_supplier = db.query(Supplier).filter(Supplier.name == item["name"]).first()
            if existing_supplier:
                print(f"[跳过] 供应商已存在: {item['name']}")
                continue

            existing_user = db.query(User).filter(User.phone == item["phone"]).first()
            if existing_user:
                print(f"[跳过] 手机号已存在: {item['phone']}")
                continue

            username = f"supplier_{item['phone']}"
            existing_username = db.query(User).filter(User.username == username).first()
            if existing_username:
                print(f"[跳过] 用户名已存在: {username}")
                continue

            user = User(
                username=username,
                phone=item["phone"],
                password_hash=get_password_hash(DEFAULT_PASSWORD),
                role="supplier",
            )
            db.add(user)
            db.flush()

            supplier = Supplier(
                name=item["name"],
                code=item.get("code"),
                contact_person=item.get("contact_person"),
                phone=item["phone"],
                email=item.get("email"),
                grade=item.get("grade", "一般"),
                level=item.get("level", "general"),
                short_name=item.get("short_name"),
                status="approved",
                user_id=user.id,
                profile_audit_status="approved",
            )
            db.add(supplier)
            db.flush()

            member = SupplierMember(
                supplier_id=supplier.id,
                user_id=user.id,
                role="admin",
                status="active",
                member_name=item.get("contact_person"),
                position="管理员",
                application_note="测试数据自动创建",
                approval_mode="platform_admin",
            )
            db.add(member)

            print(f"[创建] 供应商: {item['name']} | 账号: {username} | 手机: {item['phone']} | 密码: {DEFAULT_PASSWORD}")

        db.commit()
        print("\n测试供应商数据插入完成！")
        print("=" * 70)
        print(f"{'供应商名称':<24} {'登录账号':<24} {'手机号':<14} 密码")
        print("-" * 70)
        for item in TEST_SUPPLIERS:
            username = f"supplier_{item['phone']}"
            print(f"{item['name']:<22} {username:<24} {item['phone']:<14} {DEFAULT_PASSWORD}")
        print("=" * 70)
    except Exception as e:
        db.rollback()
        print(f"插入失败: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
