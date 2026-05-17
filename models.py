from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, Text, Boolean, JSON, Enum, UniqueConstraint, inspect, text
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from datetime import datetime
import enum
import os
from dotenv import load_dotenv

# 加载 .env 文件，并覆盖系统同名环境变量，避免读取到旧配置
load_dotenv(override=True)

# 直接从环境变量读取，如果没有则提供一个备用默认值
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:123456@localhost:5432/supply_chain_agent")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def ensure_runtime_schema_columns():
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    alter_statements = []

    if "inquiry_suppliers" in table_names:
        inquiry_supplier_columns = {col["name"] for col in inspector.get_columns("inquiry_suppliers")}
        if "allocated_ratio" not in inquiry_supplier_columns:
            alter_statements.append("ALTER TABLE inquiry_suppliers ADD COLUMN allocated_ratio FLOAT")
        if "allocated_qty" not in inquiry_supplier_columns:
            alter_statements.append("ALTER TABLE inquiry_suppliers ADD COLUMN allocated_qty FLOAT")
        if "item_allocations" not in inquiry_supplier_columns:
            alter_statements.append("ALTER TABLE inquiry_suppliers ADD COLUMN item_allocations JSON")

    if "inquiry_tasks" in table_names:
        inquiry_task_columns = {col["name"] for col in inspector.get_columns("inquiry_tasks")}
        if "type" not in inquiry_task_columns:
            alter_statements.append("ALTER TABLE inquiry_tasks ADD COLUMN type VARCHAR DEFAULT 'auto'")
        if "buyer_id" not in inquiry_task_columns:
            alter_statements.append("ALTER TABLE inquiry_tasks ADD COLUMN buyer_id INTEGER")

    if "inquiry_requests" in table_names:
        inquiry_request_columns = {col["name"] for col in inspector.get_columns("inquiry_requests")}
        if "material_model" not in inquiry_request_columns:
            alter_statements.append("ALTER TABLE inquiry_requests ADD COLUMN material_model VARCHAR")

    if "warning_messages" in table_names:
        warning_columns = {col["name"] for col in inspector.get_columns("warning_messages")}
        if "buyer_id" not in warning_columns:
            alter_statements.append("ALTER TABLE warning_messages ADD COLUMN buyer_id INTEGER")
        if "is_read" not in warning_columns:
            alter_statements.append("ALTER TABLE warning_messages ADD COLUMN is_read BOOLEAN DEFAULT FALSE")
        if "read_at" not in warning_columns:
            alter_statements.append("ALTER TABLE warning_messages ADD COLUMN read_at TIMESTAMP")
        if "supplier_remark" not in warning_columns:
            alter_statements.append("ALTER TABLE warning_messages ADD COLUMN supplier_remark TEXT")

    if "operation_logs" in table_names:
        operation_log_columns = {col["name"] for col in inspector.get_columns("operation_logs")}
        if "module" not in operation_log_columns:
            alter_statements.append("ALTER TABLE operation_logs ADD COLUMN module VARCHAR")
        if "target_type" not in operation_log_columns:
            alter_statements.append("ALTER TABLE operation_logs ADD COLUMN target_type VARCHAR")
        if "target_name" not in operation_log_columns:
            alter_statements.append("ALTER TABLE operation_logs ADD COLUMN target_name VARCHAR")
        if "result" not in operation_log_columns:
            alter_statements.append("ALTER TABLE operation_logs ADD COLUMN result VARCHAR DEFAULT 'success'")
        if "extra_data" not in operation_log_columns:
            alter_statements.append("ALTER TABLE operation_logs ADD COLUMN extra_data JSON")

    if "compare_drafts" not in table_names:
        alter_statements.extend([
            """
            CREATE TABLE IF NOT EXISTS compare_drafts (
                id SERIAL PRIMARY KEY,
                task_id INTEGER NOT NULL REFERENCES inquiry_tasks (id),
                buyer_id INTEGER NOT NULL REFERENCES users (id),
                task_title VARCHAR,
                material_code VARCHAR NOT NULL,
                material_name VARCHAR,
                supplier_count INTEGER DEFAULT 0,
                created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
                UNIQUE (task_id, buyer_id, material_code)
            )
            """
        ])

    if not alter_statements:
        return

    with engine.begin() as conn:
        for statement in alter_statements:
            conn.execute(text(statement))

# --- 枚举类型 ---

class UserRole(str, enum.Enum):
    ADMIN = "admin"
    BUYER = "buyer"
    SUPPLIER = "supplier"

class InquiryStatus(str, enum.Enum):
    PENDING_POOL = "pending_pool"  # 在池中
    IN_PROCESS = "in_process"      # 处理中
    COMPLETED = "completed"        # 已完成

class TaskStatus(str, enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    CLOSED = "closed"
    AWAITING_AWARD = "awaiting_award"
    # 手动询价相关状态
    PENDING_FILL = "pending_fill"  # 待填写
    ANALYZING = "analyzing"        # 分析中

class LinkStatus(str, enum.Enum):
    SENT = "sent"            # 已发送
    QUOTED = "quoted"        # 已报价
    NEGOTIATION = "negotiation" # 谈判中
    LOCKED = "locked"        # 已达目标价，锁定等待最终比价
    DEAL = "deal"            # 成交
    REJECT = "reject"        # 拒绝/淘汰

# --- 数据库模型 ---

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, default=UserRole.BUYER)
    created_at = Column(DateTime, default=datetime.now)

class InquiryRequest(Base):
    """
    询价需求池：从ERP拉取的快照数据
    """
    __tablename__ = "inquiry_requests"
    
    id = Column(Integer, primary_key=True, index=True)
    erp_request_id = Column(String, index=True, comment="ERP采购申请单号+行号")
    bill_no = Column(String, index=True, comment="ERP单据编号") # 对应 FBILLNO
    project_info = Column(JSON, comment="项目信息 {number, name}")
    material_code = Column(String, index=True)
    material_name = Column(String)
    material_model = Column(String, nullable=True, comment="规格型号")
    qty = Column(Float)
    target_price = Column(Float, nullable=True, comment="期望单价")
    delivery_date = Column(DateTime)
    status = Column(String, default=InquiryStatus.PENDING_POOL)
    created_at = Column(DateTime, default=datetime.now)

class InquiryTask(Base):
    """
    询价任务单：一次具体的询价活动
    """
    __tablename__ = "inquiry_tasks"
    
    id = Column(Integer, primary_key=True, index=True)
    type = Column(String, default="auto", comment="任务类型: auto(自动询价), manual(手动询价)")
    title = Column(String, nullable=False)
    strategy_config = Column(JSON, comment="谈判策略配置 {max_rounds, bargain_ratio...}")
    deadline = Column(DateTime, nullable=True, comment="询价截止时间")
    status = Column(String, default=TaskStatus.DRAFT)
    buyer_id = Column(Integer, ForeignKey("users.id"), comment="负责的采购员")
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.now)

    # 关系
    creator = relationship("User", foreign_keys=[created_by])
    buyer = relationship("User", foreign_keys=[buyer_id])
    items = relationship("InquiryTaskItem", back_populates="task")
    suppliers = relationship("InquirySupplier", back_populates="task")
    contracts = relationship("Contract", back_populates="task")

class Material(Base):
    """
    物料主数据：从 ERP 同步
    """
    __tablename__ = "materials"
    
    id = Column(Integer, primary_key=True, index=True)
    code = Column(String, unique=True, index=True, nullable=False, comment="物料编码")
    name = Column(String, nullable=False, comment="物料名称")
    specification = Column(String, nullable=True, comment="规格型号")
    erp_cls_id = Column(String, nullable=True, comment="物料属性(1外购, 2自制, 10资产, 11费用, 6服务)")
    group_name = Column(String, nullable=True, comment="物料分组")
    base_unit = Column(String, nullable=True, comment="基本单位")
    
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

class InquiryTaskItem(Base):
    """
    任务与需求的关联表
    """
    __tablename__ = "inquiry_task_items"
    
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("inquiry_tasks.id"))
    request_id = Column(Integer, ForeignKey("inquiry_requests.id"))
    
    task = relationship("InquiryTask", back_populates="items")
    request = relationship("InquiryRequest")

class Supplier(Base):
    """
    供应商库
    """
    __tablename__ = "suppliers"
    
    id = Column(Integer, primary_key=True, index=True)
    code = Column(String, unique=True, index=True, nullable=True, comment="供应商编码")
    name = Column(String, unique=True, index=True)
    short_name = Column(String, nullable=True, comment="供应商简称")
    group_name = Column(String, nullable=True, comment="供应商分组")
    grade = Column(String, nullable=True, comment="供应商等级(A级/B级等)")
    contact_person = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    email = Column(String, nullable=True)
    level = Column(String, default="general", comment="general/core")
    status = Column(String, default="pending", comment="pending/approved/rejected")
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    rating_score = Column(Float, default=0.0)
    reviewer_id = Column(Integer, ForeignKey("users.id"), nullable=True, comment="审核人ID")
    reviewed_at = Column(DateTime, nullable=True, comment="审核时间")

    user = relationship("User", foreign_keys=[user_id], backref="supplier_profile")
    reviewer = relationship("User", foreign_keys=[reviewer_id])

class InquirySupplier(Base):
    """
    询价任务与供应商的关联状态
    """
    __tablename__ = "inquiry_suppliers"
    
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("inquiry_tasks.id"))
    supplier_id = Column(Integer, ForeignKey("suppliers.id"))
    current_round = Column(Integer, default=1)
    status = Column(String, default=LinkStatus.SENT)
    allocated_ratio = Column(Float, nullable=True, comment="中标分配比例(0-100)")
    allocated_qty = Column(Float, nullable=True, comment="中标分配数量")
    item_allocations = Column(JSON, nullable=True, comment="按物料维度的分配结果")
    latest_ai_feedback = Column(Text, nullable=True, comment="最新的AI谈判反馈")
    created_at = Column(DateTime, default=datetime.now)

    task = relationship("InquiryTask", back_populates="suppliers")
    supplier = relationship("Supplier")
    quotations = relationship("Quotation", back_populates="inquiry_supplier")
    contracts = relationship("Contract", back_populates="inquiry_supplier")

class Quotation(Base):
    """
    报价记录
    """
    __tablename__ = "quotations"
    
    id = Column(Integer, primary_key=True, index=True)
    inquiry_supplier_id = Column(Integer, ForeignKey("inquiry_suppliers.id"))
    round = Column(Integer, nullable=False)
    item_id = Column(Integer, ForeignKey("inquiry_task_items.id"))
    qty = Column(Float, nullable=True, comment="供应商可供数量")
    price = Column(Float, nullable=False)
    delivery_date = Column(DateTime, nullable=True)
    remark = Column(Text, nullable=True)
    ai_analysis = Column(JSON, nullable=True, comment="AI分析结果")
    created_at = Column(DateTime, default=datetime.now)

    inquiry_supplier = relationship("InquirySupplier", back_populates="quotations")
    item = relationship("InquiryTaskItem") # 关联到具体的任务明细项 (从而知道是对哪个物料报价)

class Contract(Base):
    __tablename__ = "contracts"
    __table_args__ = (UniqueConstraint("inquiry_supplier_id", name="uq_contracts_inquiry_supplier_id"),)
    
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("inquiry_tasks.id"), nullable=False)
    inquiry_supplier_id = Column(Integer, ForeignKey("inquiry_suppliers.id"), nullable=False)
    pdf_path = Column(Text, nullable=True)
    total_amount = Column(Float, nullable=True)
    buyer_company_name = Column(String, nullable=True)
    history_versions = Column(JSON, nullable=True, default=list)
    address = Column(String, nullable=True)
    legal_representative = Column(String, nullable=True)
    agent = Column(String, nullable=True)

    contact_phone = Column(String, nullable=True)
    bank_name = Column(String, nullable=True)
    bank_account = Column(String, nullable=True)
    tax_id = Column(String, nullable=True)
    fax = Column(String, nullable=True)
    postal_code = Column(String, nullable=True)
    status = Column(String, default="generated")
    generated_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    task = relationship("InquiryTask", back_populates="contracts")
    inquiry_supplier = relationship("InquirySupplier", back_populates="contracts")
    generator = relationship("User")

class ContractTemplate(Base):
    __tablename__ = "contract_templates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)
    file_path = Column(String, nullable=False)
    default_buyer_name = Column(String, nullable=True)
    is_active = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

class SupplierMetric(Base):
    """
    供应商绩效指标
    """
    __tablename__ = "supplier_metrics"
    
    id = Column(Integer, primary_key=True, index=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"))
    task_id = Column(Integer, ForeignKey("inquiry_tasks.id"))
    response_time_minutes = Column(Integer)
    total_rounds = Column(Integer)
    final_deal_rate = Column(Float)
    price_competitiveness = Column(Float)
    created_at = Column(DateTime, default=datetime.now)

class WarningMessage(Base):
    """
    采购员发给供应商的预警消息
    """
    __tablename__ = "warning_messages"
    
    id = Column(Integer, primary_key=True, index=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"))
    buyer_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.now)
    is_read = Column(Boolean, default=False)
    read_at = Column(DateTime, nullable=True)
    supplier_remark = Column(Text, nullable=True)
    
    supplier = relationship("Supplier")
    buyer = relationship("User")

class CompareDraft(Base):
    """
    智能比价工作台草稿：支持多端共享草稿列表
    """
    __tablename__ = "compare_drafts"
    __table_args__ = (UniqueConstraint("task_id", "buyer_id", "material_code", name="uq_compare_drafts_task_buyer_material"),)

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("inquiry_tasks.id"), nullable=False)
    buyer_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    task_title = Column(String, nullable=True)
    material_code = Column(String, nullable=False, index=True)
    material_name = Column(String, nullable=True)
    supplier_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    task = relationship("InquiryTask")
    buyer = relationship("User")

class OperationLog(Base):
    """
    系统操作日志
    """
    __tablename__ = "operation_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action_type = Column(String, nullable=False, comment="LOGIN, CREATE_USER, DELETE_USER, APPROVE_SUPPLIER, CREATE_INQUIRY, SEND_WARNING")
    module = Column(String, nullable=True, comment="所属模块")
    target_type = Column(String, nullable=True, comment="操作对象类型")
    target_name = Column(String, nullable=True, comment="操作对象名称")
    result = Column(String, nullable=True, default="success", comment="操作结果")
    detail = Column(String, nullable=True)
    extra_data = Column(JSON, nullable=True, comment="补充明细")
    ip_address = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.now)

    user = relationship("User")

# 依赖注入 Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class PurchaseOrderHistory(Base):
    """
    采购订单历史明细表：用于 AI 价格分析与前端趋势展示
    """
    __tablename__ = "purchase_order_history"
    
    id = Column(Integer, primary_key=True, index=True)
    erp_entry_id = Column(String, unique=True, index=True, comment="ERP订单明细内码(唯一)")
    bill_no = Column(String, index=True, comment="采购订单号")
    project_number = Column(String, index=True, nullable=True, comment="项目号")
    supplier_code = Column(String, index=True, comment="供应商编码")
    supplier_name = Column(String, comment="供应商名称")
    material_code = Column(String, index=True, comment="物料编码")
    material_name = Column(String, comment="物料名称")
    qty = Column(Float, comment="采购数量")
    price = Column(Float, comment="单价(不含税)")
    tax_net_price = Column(Float, comment="含税净价(实付价)")
    date = Column(DateTime, index=True, comment="订单日期")
    created_at = Column(DateTime, default=datetime.now)
