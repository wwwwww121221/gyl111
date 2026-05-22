from pydantic import BaseModel, Field
from typing import List, Optional, Union
from datetime import datetime, date

class QuoteItem(BaseModel):
    request_id: int
    qty: Optional[float] = None
    price: float
    delivery_date: Optional[Union[datetime, date, str]] = None
    remark: Optional[str] = None

class QuoteSubmission(BaseModel):
    items: List[QuoteItem]
    force_submit: Optional[bool] = False

class SupplierQuoteResponse(BaseModel):
    message: str
    next_action: str # "wait", "re-quote", "deal"
    ai_feedback: Optional[str] = None

class SupplierUpdate(BaseModel):
    status: Optional[str] = None
    level: Optional[str] = None
    grade: Optional[str] = None
    review_comment: Optional[str] = None


class SupplierCreatePayload(BaseModel):
    name: str
    code: Optional[str] = None
    contact_person: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    status: Optional[str] = "approved"
    grade: Optional[str] = "一般"
    level: Optional[str] = "general"
    username: Optional[str] = None
    password: Optional[str] = None


class SupplierAccountUpdatePayload(BaseModel):
    username: Optional[str] = None
    password: Optional[str] = None


class SupplierProfileUpdatePayload(BaseModel):
    contact_person: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    short_name: Optional[str] = None
    social_credit_code: Optional[str] = None
    onboarding_note: Optional[str] = None
    application_attachments: Optional[list] = None
    change_description: Optional[str] = Field(
        default=None,
        description="资料变更时请说明本次修改了哪些文件或信息",
    )


class SupplierContractInfoSubmit(BaseModel):
    address: str = Field(..., min_length=1)
    legal_representative: str = Field(..., min_length=1)
    agent: Optional[str] = None
    contact_phone: str = Field(..., min_length=1)
    bank_name: str = Field(..., min_length=1)
    bank_account: str = Field(..., min_length=1)
    tax_id: str = Field(..., min_length=1)
    fax: str = Field(..., min_length=1)
    postal_code: str = Field(..., min_length=1)
    buyer_company_name: Optional[str] = None

class SupplierChangePasswordPayload(BaseModel):
    old_password: str = Field(..., min_length=1, description="原密码")
    new_password: str = Field(..., min_length=6, description="新密码，至少6位")
