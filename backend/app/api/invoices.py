import json
import mimetypes
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session
from sqlalchemy import desc, or_

from app.database.session import get_db
from app.api.deps import get_current_user, require_role
from app.models.entities import User, Invoice, InvoiceItem, ValidationResult, DuplicateCheck, FraudAlert, AuditLog
from app.schemas.schemas import (
    InvoiceResponse, InvoiceDetailResponse, InvoiceUpdate
)
from app.services.cloud_storage_service import cloud_storage_service
from app.services.validation_service import validation_service
from app.services.encryption_service import encryption_service
from app.services.invoice_pipeline import process_invoice_upload
from app.services import invoice_actions

router = APIRouter(prefix="/api/invoices", tags=["Invoices"])

def load_invoice_for_user(db: Session, invoice_id: int, user: User) -> Invoice:
    """Fetch an invoice the user is allowed to see, else 404 (never reveal other tenants' invoices).
    admin: any invoice; reviewer: own organization; user: invoices they uploaded."""
    query = db.query(Invoice).filter(Invoice.id == invoice_id)
    if user.role == "user":
        query = query.filter(Invoice.user_id == user.id)
    elif user.role == "reviewer":
        query = query.filter(Invoice.organization == (user.organization or "General"))
    invoice = query.first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found.")
    return invoice

def format_invoice_response(invoice: Invoice) -> dict:
    """Helper to decrypt sensitive fields before presenting in response."""
    return {
        "id": invoice.id,
        "invoice_number": invoice.invoice_number,
        "vendor_name": invoice.vendor_name,
        "vendor_address": invoice.vendor_address,
        "customer_name": invoice.customer_name,
        "customer_address": invoice.customer_address,
        "gst_number": encryption_service.decrypt(invoice.gst_number),
        "tax_id": encryption_service.decrypt(invoice.tax_id),
        "bank_details": encryption_service.decrypt(invoice.bank_details),
        "po_number": invoice.po_number,
        "invoice_date": invoice.invoice_date,
        "due_date": invoice.due_date,
        "subtotal": invoice.subtotal,
        "tax_amount": invoice.tax_amount,
        "discount": invoice.discount,
        "total_amount": invoice.total_amount,
        "currency": invoice.currency,
        "cloud_file_path": invoice.cloud_file_path,
        "original_filename": invoice.original_filename,
        "status": invoice.status,
        "validation_status": invoice.validation_status,
        "risk_score": invoice.risk_score,
        "risk_level": invoice.risk_level,
        "duplicate_status": invoice.duplicate_status,
        "sha256_checksum": invoice.sha256_checksum,
        "organization": invoice.organization,
        "user_id": invoice.user_id,
        "payment_status": getattr(invoice, "payment_status", None) or "unpaid",
        "source_channel": getattr(invoice, "source_channel", None) or "web",
        "created_at": invoice.created_at,
        "updated_at": invoice.updated_at,
    }

def format_invoice_detail(invoice: Invoice) -> dict:
    """Helper to convert invoice and all related entities to a clean serializable dictionary."""
    res = format_invoice_response(invoice)
    res["items"] = [
        {
            "id": itm.id,
            "invoice_id": itm.invoice_id,
            "description": itm.description,
            "quantity": itm.quantity,
            "unit_price": itm.unit_price,
            "total_price": itm.total_price
        } for itm in (invoice.items or [])
    ]
    res["validation_results"] = [
        {
            "id": val.id,
            "field_name": val.field_name,
            "extracted_value": val.extracted_value,
            "validation_status": val.validation_status,
            "confidence_score": val.confidence_score,
            "validation_message": val.validation_message
        } for val in (invoice.validation_results or [])
    ]
    res["duplicate_checks"] = [
        {
            "id": d.id,
            "invoice_id": d.invoice_id,
            "compared_invoice_id": d.compared_invoice_id,
            "similarity_score": d.similarity_score,
            "duplicate_status": d.duplicate_status,
            "matching_fields": d.matching_fields
        } for d in (invoice.duplicate_checks or [])
    ]
    res["fraud_alerts"] = [
        {
            "id": f.id,
            "invoice_id": f.invoice_id,
            "risk_score": f.risk_score,
            "risk_level": f.risk_level,
            "alert_reason": f.alert_reason,
            "created_at": f.created_at
        } for f in (invoice.fraud_alerts or [])
    ]
    res["audit_logs"] = [
        {
            "id": a.id,
            "user_id": a.user_id,
            "invoice_id": a.invoice_id,
            "action": a.action,
            "timestamp": a.timestamp,
            "details": a.details,
            "user_name": a.user.name if getattr(a, "user", None) else "System"
        } for a in (invoice.audit_logs or [])
    ]
    return res

@router.post("/upload", response_model=InvoiceDetailResponse, status_code=status.HTTP_201_CREATED)
async def upload_invoice(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Workflow Step 1-7:
    Upload file -> Cloud Storage -> OCR Extraction -> Validation -> Duplicate Check -> Fraud Risk Scoring -> Save
    (implemented once in app/services/invoice_pipeline.py and shared with the InvoShield Assistant)
    """
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    new_invoice = process_invoice_upload(
        db,
        file_bytes=file_bytes,
        filename=file.filename,
        organization=current_user.organization or "General",
        user_id=current_user.id,
        source_channel="web",
    )
    # Build clean response with decrypted sensitive fields and serialized relations
    return format_invoice_detail(new_invoice)

@router.get("", response_model=dict)
def get_invoices(
    search: Optional[str] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    risk_filter: Optional[str] = Query(None, alias="risk_level"),
    validation_filter: Optional[str] = Query(None, alias="validation_status"),
    sort_by: str = "created_at",
    sort_desc: bool = True,
    page: int = 1,
    limit: int = 10,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Searchable, filterable, sortable, paginated invoice list.
    RBAC: Regular user only views their own invoices. Admin/Reviewer views all.
    """
    query = db.query(Invoice)

    if current_user.role == "user":
        query = query.filter(Invoice.user_id == current_user.id)
    elif current_user.role == "reviewer":
        # Multi-tenant isolation: Reviewer only accesses company's invoices
        query = query.filter(Invoice.organization == (current_user.organization or "General"))

    if search:
        s = f"%{search.strip()}%"
        query = query.filter(or_(
            Invoice.invoice_number.ilike(s),
            Invoice.vendor_name.ilike(s),
            Invoice.customer_name.ilike(s)
        ))

    if status_filter:
        query = query.filter(Invoice.status == status_filter)
    if risk_filter:
        query = query.filter(Invoice.risk_level.ilike(risk_filter))
    if validation_filter:
        query = query.filter(Invoice.validation_status.ilike(validation_filter))

    total = query.count()

    # Sorting
    sort_col = getattr(Invoice, sort_by, Invoice.created_at)
    if sort_desc:
        query = query.order_by(desc(sort_col))
    else:
        query = query.order_by(sort_col)

    offset = (page - 1) * limit
    invoices = query.offset(offset).limit(limit).all()

    formatted_items = [format_invoice_response(inv) for inv in invoices]
    return {
        "items": formatted_items,
        "total": total,
        "page": page,
        "limit": limit,
        "total_pages": (total + limit - 1) // limit if limit > 0 else 1
    }

@router.get("/{invoice_id}", response_model=InvoiceDetailResponse)
def get_invoice(
    invoice_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get complete invoice details, line items, validation history, duplicate checks, fraud alerts, and audit trail."""
    invoice = load_invoice_for_user(db, invoice_id, current_user)

    return format_invoice_detail(invoice)

@router.put("/{invoice_id}", response_model=InvoiceDetailResponse)
def update_invoice(
    invoice_id: int,
    invoice_update: InvoiceUpdate,
    current_user: User = Depends(require_role(["admin", "reviewer"])),
    db: Session = Depends(get_db)
):
    """Inline editing of extracted invoice fields with automatic re-encryption of sensitive fields."""
    invoice = load_invoice_for_user(db, invoice_id, current_user)

    update_dict = invoice_update.model_dump(exclude_unset=True)
    items_data = update_dict.pop("items", None)

    # Re-encrypt sensitive fields if updated
    if "gst_number" in update_dict and update_dict["gst_number"]:
        update_dict["gst_number"] = encryption_service.encrypt(update_dict["gst_number"])
    if "tax_id" in update_dict and update_dict["tax_id"]:
        update_dict["tax_id"] = encryption_service.encrypt(update_dict["tax_id"])
    if "bank_details" in update_dict and update_dict["bank_details"]:
        update_dict["bank_details"] = encryption_service.encrypt(update_dict["bank_details"])

    for key, val in update_dict.items():
        if hasattr(invoice, key):
            setattr(invoice, key, val)

    if items_data is not None:
        db.query(InvoiceItem).filter(InvoiceItem.invoice_id == invoice.id).delete()
        for item in items_data:
            db_item = InvoiceItem(
                invoice_id=invoice.id,
                description=item.get("description", ""),
                quantity=item.get("quantity", 1.0),
                unit_price=item.get("unit_price", 0.0),
                total_price=item.get("total_price", 0.0),
            )
            db.add(db_item)

    audit = AuditLog(
        user_id=current_user.id,
        invoice_id=invoice.id,
        action="INVOICE_UPDATED",
        details=f"Invoice #{invoice.invoice_number} modified by {current_user.name}."
    )
    db.add(audit)
    db.commit()
    db.refresh(invoice)

    return format_invoice_detail(invoice)

@router.post("/{invoice_id}/validate", response_model=InvoiceDetailResponse)
def revalidate_invoice(
    invoice_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Re-run data validation on the invoice."""
    invoice = load_invoice_for_user(db, invoice_id, current_user)

    decrypted_data = format_invoice_response(invoice)
    validation_items, val_status = validation_service.validate(decrypted_data)

    invoice.validation_status = val_status
    db.query(ValidationResult).filter(ValidationResult.invoice_id == invoice.id).delete()

    for v in validation_items:
        val_entry = ValidationResult(
            invoice_id=invoice.id,
            field_name=v.get("field_name"),
            extracted_value=str(v.get("extracted_value") or ""),
            validation_status=v.get("validation_status"),
            confidence_score=v.get("confidence_score", 1.0),
            validation_message=v.get("validation_message")
        )
        db.add(val_entry)

    audit = AuditLog(
        user_id=current_user.id,
        invoice_id=invoice.id,
        action="INVOICE_REVALIDATED",
        details=f"Revalidated with result: {val_status}."
    )
    db.add(audit)
    db.commit()
    db.refresh(invoice)

    return format_invoice_detail(invoice)

@router.post("/{invoice_id}/approve", response_model=InvoiceResponse)
def approve_invoice(
    invoice_id: int,
    current_user: User = Depends(require_role(["admin", "reviewer"])),
    db: Session = Depends(get_db)
):
    """Role-based approval: Reviewer or Admin only (SoD enforced in invoice_actions)."""
    invoice = load_invoice_for_user(db, invoice_id, current_user)
    try:
        invoice = invoice_actions.approve_invoice(db, invoice, current_user)
    except invoice_actions.InvoiceActionError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    return format_invoice_response(invoice)

@router.post("/{invoice_id}/reject", response_model=InvoiceResponse)
def reject_invoice(
    invoice_id: int,
    current_user: User = Depends(require_role(["admin", "reviewer"])),
    db: Session = Depends(get_db)
):
    """Role-based rejection: Reviewer or Admin only."""
    invoice = load_invoice_for_user(db, invoice_id, current_user)
    try:
        invoice = invoice_actions.reject_invoice(db, invoice, current_user)
    except invoice_actions.InvoiceActionError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    return format_invoice_response(invoice)

@router.post("/{invoice_id}/mark-paid", response_model=InvoiceResponse)
def mark_invoice_paid(
    invoice_id: int,
    current_user: User = Depends(require_role(["admin", "reviewer"])),
    db: Session = Depends(get_db)
):
    """Mark an approved invoice as paid (used by the assistant's balance and vendor status answers)."""
    invoice = load_invoice_for_user(db, invoice_id, current_user)
    try:
        invoice = invoice_actions.mark_invoice_paid(db, invoice, current_user)
    except invoice_actions.InvoiceActionError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    return format_invoice_response(invoice)

@router.get("/{invoice_id}/duplicates", response_model=dict)
def get_invoice_duplicates(
    invoice_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get duplicate comparison details, matched invoice, similarity score, and field matching breakdown."""
    invoice = load_invoice_for_user(db, invoice_id, current_user)

    dup_check = db.query(DuplicateCheck).filter(DuplicateCheck.invoice_id == invoice_id).first()
    matched_invoice = None
    breakdown = {}

    if dup_check:
        if dup_check.compared_invoice_id:
            matched_inv = db.query(Invoice).filter(Invoice.id == dup_check.compared_invoice_id).first()
            if matched_inv:
                matched_invoice = format_invoice_response(matched_inv)
        if dup_check.matching_fields:
            try:
                breakdown = json.loads(dup_check.matching_fields)
            except Exception:
                breakdown = {}

    return {
        "current_invoice": format_invoice_response(invoice),
        "similarity_score": dup_check.similarity_score if dup_check else 0.0,
        "duplicate_status": dup_check.duplicate_status if dup_check else "No Significant Duplicate",
        "matched_invoice": matched_invoice,
        "breakdown": breakdown
    }

@router.get("/{invoice_id}/risk-analysis", response_model=dict)
def get_invoice_risk_analysis(
    invoice_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get risk score, risk level, and plain-language alert reasons."""
    invoice = load_invoice_for_user(db, invoice_id, current_user)

    alerts = db.query(FraudAlert).filter(FraudAlert.invoice_id == invoice_id).all()
    reasons = [a.alert_reason for a in alerts]
    alerts_data = [
        {
            "id": a.id,
            "invoice_id": a.invoice_id,
            "risk_score": a.risk_score,
            "risk_level": a.risk_level,
            "alert_reason": a.alert_reason,
            "created_at": a.created_at.isoformat() if a.created_at else None
        }
        for a in alerts
    ]

    return {
        "invoice_id": invoice.id,
        "invoice_number": invoice.invoice_number,
        "vendor_name": invoice.vendor_name,
        "total_amount": invoice.total_amount,
        "risk_score": invoice.risk_score,
        "risk_level": invoice.risk_level,
        "reasons": reasons,
        "alerts": alerts_data
    }

@router.get("/{invoice_id}/file")
def get_invoice_file(
    invoice_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Serve invoice file for preview."""
    invoice = load_invoice_for_user(db, invoice_id, current_user)

    try:
        content = cloud_storage_service.get_file(invoice.cloud_file_path)
        filename = invoice.original_filename or "document.pdf"
        media_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        return Response(content=content, media_type=media_type)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"File not found: {str(e)}")
