from pydantic import BaseModel, Field
from typing import Optional, List, Any
from datetime import datetime
from enum import Enum

# --- Auth Schemas ---
class Token(BaseModel):
    access_token: str
    token_type: str
    role: Optional[str] = None

class TokenData(BaseModel):
    username: Optional[str] = None

class UserBase(BaseModel):
    username: str
    role: Optional[str] = "buyer"
    department: Optional[str] = "采购部"

class UserCreate(UserBase):
    password: str
    company_name: Optional[str] = None
    contact_person: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None

class User(UserBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

# --- Inquiry Pool Schemas ---

class InquiryRequestBase(BaseModel):
    erp_request_id: str
    bill_no: Optional[str] = None
    bill_type: Optional[str] = None
    project_info: Optional[dict] = None
    material_code: str
    material_name: str
    material_model: Optional[str] = None
    qty: float
    delivery_date: Optional[datetime] = None
    purchaser_name: Optional[str] = None
    purchaser_detail_name: Optional[str] = None
    purchaser_base_name: Optional[str] = None
    remark: Optional[str] = None
    remark_detail: Optional[str] = None
    remark_base: Optional[str] = None
    technician_name: Optional[str] = None

class InquiryRequestCreate(InquiryRequestBase):
    target_price: Optional[float] = None
    supplier_ids: Optional[List[int]] = None

class InquiryRequest(InquiryRequestBase):
    id: Optional[int] = None # Make id optional for non-persisted data
    status: str
    target_price: Optional[float] = None
    created_at: Optional[datetime] = None # Make optional

    class Config:
        from_attributes = True

# --- Task Schemas ---

class StrategyConfig(BaseModel):
    max_rounds: int = 3
    bargain_ratio: float = 0.05
    target_price_rule: Optional[dict] = None


class InquiryAttachment(BaseModel):
    name: str
    file_path: str
    preview_file_path: Optional[str] = None
    size: Optional[int] = None
    uploaded_at: Optional[datetime] = None

class InquiryTaskBase(BaseModel):
    title: str
    type: str = "auto"
    strategy_config: Optional[StrategyConfig] = None
    deadline: Optional[datetime] = None

class InquiryTaskCreate(InquiryTaskBase):
    deadline: Optional[datetime] = None
    request_ids: Optional[List[int]] = None
    raw_requests: Optional[List[InquiryRequestCreate]] = None
    supplier_ids: Optional[List[int]] = None
    buyer_comment: Optional[str] = None
    attachments: Optional[List[InquiryAttachment]] = None

class InquiryTask(InquiryTaskBase):
    deadline: Optional[datetime] = None
    id: int
    status: Optional[str] = None
    buyer_id: Optional[int] = None
    approved_by: Optional[int] = None
    approved_at: Optional[datetime] = None
    approval_comment: Optional[str] = None
    created_by: Optional[int] = None
    created_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class TaskCloseItemAllocation(BaseModel):
    item_id: int
    allocated_ratio: Optional[float] = Field(default=None, ge=0, le=100)
    allocated_qty: Optional[float] = Field(default=None, ge=0)


class TaskCloseAllocation(BaseModel):
    link_id: int
    allocated_ratio: Optional[float] = Field(default=None, ge=0, le=100)
    allocated_qty: Optional[float] = Field(default=None, ge=0)
    item_allocations: Optional[List[TaskCloseItemAllocation]] = None


class TaskClosePayload(BaseModel):
    allocations: List[TaskCloseAllocation]


class TaskApprovalPayload(BaseModel):
    comment: Optional[str] = None

class ContractBase(BaseModel):
    task_id: int
    inquiry_supplier_id: int
    pdf_path: Optional[str] = None
    total_amount: Optional[float] = None
    buyer_company_name: Optional[str] = None
    history_versions: Optional[List[dict]] = None
    address: Optional[str] = None
    legal_representative: Optional[str] = None
    agent: Optional[str] = None
    contact_phone: Optional[str] = None
    bank_name: Optional[str] = None
    bank_account: Optional[str] = None
    tax_id: Optional[str] = None
    fax: Optional[str] = None
    postal_code: Optional[str] = None
    status: Optional[str] = "generated"
    generated_by: Optional[int] = None

class ContractCreate(ContractBase):
    pass

class Contract(ContractBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class ContractTemplateBase(BaseModel):
    name: str
    file_path: str
    default_buyer_name: Optional[str] = None
    is_active: bool = False

class ContractTemplateCreate(ContractTemplateBase):
    pass

class ContractTemplate(ContractTemplateBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# --- LLM Schemas ---

class ChatMessage(BaseModel):
    role: str
    content: str

class LLMResponse(BaseModel):
    content: str
    raw_response: Any = None
