from datetime import datetime
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, EmailStr, Field, ConfigDict

# User Schemas
class UserCreate(BaseModel):
    name: str = "User"
    email: str
    password: str
    confirm_password: Optional[str] = None
    organization: Optional[str] = "General"
    role: Optional[str] = "user"

class UserLogin(BaseModel):
    email: str
    password: str

class UserResponse(BaseModel):
    id: int
    name: str
    email: str
    role: str
    organization: str
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

# Line Items
class InvoiceItemBase(BaseModel):
    description: str
    quantity: float = 1.0
    unit_price: float = 0.0
    total_price: float = 0.0

class InvoiceItemCreate(InvoiceItemBase):
    pass

class InvoiceItemResponse(InvoiceItemBase):
    id: int
    invoice_id: int

    model_config = ConfigDict(from_attributes=True)

# Validation Result
class ValidationResultResponse(BaseModel):
    id: Optional[int] = None
    field_name: str
    extracted_value: Optional[str] = None
    validation_status: str  # Valid, Warning, Invalid, Missing
    confidence_score: float = 1.0
    validation_message: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

# Duplicate Check
class DuplicateCheckResponse(BaseModel):
    id: Optional[int] = None
    invoice_id: int
    compared_invoice_id: Optional[int] = None
    similarity_score: float
    duplicate_status: str
    matching_fields: Optional[Any] = None

    model_config = ConfigDict(from_attributes=True)

# Fraud Alert
class FraudAlertResponse(BaseModel):
    id: Optional[int] = None
    invoice_id: int
    risk_score: int
    risk_level: str
    alert_reason: str
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

# Audit Log
class AuditLogResponse(BaseModel):
    id: int
    user_id: Optional[int] = None
    invoice_id: Optional[int] = None
    action: str
    timestamp: datetime
    details: Optional[str] = None
    user_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

# Invoices
class InvoiceBase(BaseModel):
    invoice_number: Optional[str] = None
    vendor_name: Optional[str] = None
    vendor_address: Optional[str] = None
    customer_name: Optional[str] = None
    customer_address: Optional[str] = None
    gst_number: Optional[str] = None
    tax_id: Optional[str] = None
    bank_details: Optional[str] = None
    po_number: Optional[str] = None
    invoice_date: Optional[str] = None
    due_date: Optional[str] = None
    subtotal: float = 0.0
    tax_amount: float = 0.0
    discount: float = 0.0
    total_amount: float = 0.0
    currency: str = "USD"

class InvoiceUpdate(InvoiceBase):
    status: Optional[str] = None
    items: Optional[List[InvoiceItemBase]] = None

class InvoiceResponse(InvoiceBase):
    id: int
    cloud_file_path: str
    original_filename: Optional[str] = None
    status: str
    validation_status: str
    risk_score: int
    risk_level: str
    duplicate_status: str
    sha256_checksum: Optional[str] = None
    organization: Optional[str] = None
    user_id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class InvoiceDetailResponse(InvoiceResponse):
    items: List[InvoiceItemResponse] = []
    validation_results: List[ValidationResultResponse] = []
    duplicate_checks: List[DuplicateCheckResponse] = []
    fraud_alerts: List[FraudAlertResponse] = []
    audit_logs: List[AuditLogResponse] = []

    model_config = ConfigDict(from_attributes=True, arbitrary_types_allowed=True)

# Analytics & Dashboard
class DashboardStatistics(BaseModel):
    total_invoices: int = 0
    pending_invoices: int = 0
    approved_invoices: int = 0
    rejected_invoices: int = 0
    flagged_invoices: int = 0
    duplicate_alerts: int = 0
    high_risk_count: int = 0
    total_amount_processed: float = 0.0

class StatusDistribution(BaseModel):
    name: str
    count: int
    color: str

class RiskDistribution(BaseModel):
    level: str
    count: int
    color: str

class MonthlyTrend(BaseModel):
    month: str
    count: int
    amount: float

class VendorDistribution(BaseModel):
    vendor: str
    count: int
    total_amount: float

class DashboardAnalytics(BaseModel):
    processing_over_time: List[Dict[str, Any]]
    status_distribution: List[StatusDistribution]
    risk_distribution: List[RiskDistribution]
    vendor_distribution: List[VendorDistribution]
    monthly_totals: List[MonthlyTrend]
    recent_activities: List[AuditLogResponse]
