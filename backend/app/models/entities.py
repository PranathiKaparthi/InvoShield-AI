from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.database.session import Base

def utc_now():
    return datetime.now(timezone.utc)

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), default="user", nullable=False)  # admin, reviewer, user
    organization = Column(String(255), default="General", nullable=False)
    created_at = Column(DateTime, default=utc_now)

    invoices = relationship("Invoice", back_populates="user")
    audit_logs = relationship("AuditLog", back_populates="user")


class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True, index=True)
    invoice_number = Column(String(100), index=True, nullable=True)
    vendor_name = Column(String(255), index=True, nullable=True)
    vendor_address = Column(Text, nullable=True)
    customer_name = Column(String(255), nullable=True)
    customer_address = Column(Text, nullable=True)

    # Sensitive fields encrypted at rest using AES-256-GCM
    gst_number = Column(Text, nullable=True)
    tax_id = Column(Text, nullable=True)
    bank_details = Column(Text, nullable=True)

    po_number = Column(String(100), nullable=True)
    invoice_date = Column(String(50), nullable=True)
    due_date = Column(String(50), nullable=True)

    subtotal = Column(Float, default=0.0)
    tax_amount = Column(Float, default=0.0)
    discount = Column(Float, default=0.0)
    total_amount = Column(Float, default=0.0)
    currency = Column(String(10), default="USD")

    cloud_file_path = Column(String(500), nullable=False)
    original_filename = Column(String(255), nullable=True)
    status = Column(String(50), default="uploaded")  # uploaded, processing, pending_review, approved, rejected, flagged
    validation_status = Column(String(50), default="valid")  # valid, warning, invalid
    risk_score = Column(Integer, default=0)  # 0 to 100
    risk_level = Column(String(50), default="low")  # low, medium, high
    duplicate_status = Column(String(50), default="No Significant Duplicate")
    sha256_checksum = Column(String(64), nullable=True)  # Tamper-proof cryptographic seal
    organization = Column(String(120), default="General", index=True)  # Multi-tenant tenant scoping

    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    user = relationship("User", back_populates="invoices")
    items = relationship("InvoiceItem", back_populates="invoice", cascade="all, delete-orphan")
    validation_results = relationship("ValidationResult", back_populates="invoice", cascade="all, delete-orphan")
    duplicate_checks = relationship("DuplicateCheck", foreign_keys="DuplicateCheck.invoice_id", back_populates="invoice", cascade="all, delete-orphan")
    fraud_alerts = relationship("FraudAlert", back_populates="invoice", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="invoice", cascade="all, delete-orphan")


class InvoiceItem(Base):
    __tablename__ = "invoice_items"

    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=False)
    description = Column(String(255), nullable=False)
    quantity = Column(Float, default=1.0)
    unit_price = Column(Float, default=0.0)
    total_price = Column(Float, default=0.0)

    invoice = relationship("Invoice", back_populates="items")


class ValidationResult(Base):
    __tablename__ = "validation_results"

    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=False)
    field_name = Column(String(100), nullable=False)
    extracted_value = Column(Text, nullable=True)
    validation_status = Column(String(50), nullable=False)  # Valid, Warning, Invalid, Missing
    confidence_score = Column(Float, default=1.0)  # 0.0 to 1.0
    validation_message = Column(Text, nullable=True)

    invoice = relationship("Invoice", back_populates="validation_results")


class DuplicateCheck(Base):
    __tablename__ = "duplicate_checks"

    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=False)
    compared_invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=True)
    similarity_score = Column(Float, default=0.0)  # 0 to 100
    duplicate_status = Column(String(100), nullable=False)  # Highly Likely Duplicate, Possible Duplicate, No Significant Duplicate
    matching_fields = Column(Text, nullable=True)  # JSON string representation of matched fields & similarities

    invoice = relationship("Invoice", foreign_keys=[invoice_id], back_populates="duplicate_checks")


class FraudAlert(Base):
    __tablename__ = "fraud_alerts"

    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=False)
    risk_score = Column(Integer, default=0)
    risk_level = Column(String(50), default="low")  # low, medium, high
    alert_reason = Column(Text, nullable=False)
    created_at = Column(DateTime, default=utc_now)

    invoice = relationship("Invoice", back_populates="fraud_alerts")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=True)
    action = Column(String(100), nullable=False)
    timestamp = Column(DateTime, default=utc_now)
    details = Column(Text, nullable=True)

    user = relationship("User", back_populates="audit_logs")
    invoice = relationship("Invoice", back_populates="audit_logs")
