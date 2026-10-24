import json
import hashlib
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session
from sqlalchemy import desc, or_

from app.database.session import get_db
from app.api.deps import get_current_user, require_role
from app.models.entities import User, Invoice, InvoiceItem, ValidationResult, DuplicateCheck, FraudAlert, AuditLog
from app.schemas.schemas import (
    InvoiceResponse, InvoiceDetailResponse, InvoiceUpdate,
    ValidationResultResponse, DuplicateCheckResponse, FraudAlertResponse
)
from app.services.cloud_storage_service import cloud_storage_service
from app.services.ocr_service import ocr_service
from app.services.invoice_extraction_service import invoice_extraction_service
from app.services.validation_service import validation_service
from app.services.duplicate_detection_service import duplicate_detection_service
from app.services.fraud_detection_service import fraud_detection_service
from app.services.encryption_service import encryption_service

router = APIRouter(prefix="/api/invoices", tags=["Invoices"])

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
    """
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    # 1. Cryptographic File Integrity Checksum (Tamper-Proof SHA-256 Seal)
    sha256_hash = hashlib.sha256(file_bytes).hexdigest()

    # 2. Cloud storage upload (initial pending folder)
    cloud_path = cloud_storage_service.upload_file(file_bytes, file.filename, folder="pending")

    # 3. OCR Text Extraction & Confidence
    extracted_text, ocr_confidence = ocr_service.extract_text_and_confidence(file_bytes, file.filename)

    # 4. Intelligent Data Extraction
    data = invoice_extraction_service.extract(extracted_text, base_confidence=ocr_confidence)

    # 5. Data Validation Rules
    validation_items, val_status = validation_service.validate(data)

    # 6. RapidFuzz Duplicate Detection (Strictly scoped to current organization)
    user_org = current_user.organization or "General"
    dup_score, dup_verdict, matched_id, dup_breakdown = duplicate_detection_service.check_duplicate(
        data, db, organization=user_org
    )

    # 7. Fraud / Anomaly Risk Scoring Engine (Scoped to current organization)
    risk_score, risk_level, risk_reasons = fraud_detection_service.analyze(
        data, dup_score, db, organization=user_org
    )

    # Determine initial processing status & folder
    initial_status = "pending_review"
    if risk_level == "High" or dup_verdict == "Highly Likely Duplicate":
        initial_status = "flagged"
        cloud_path = cloud_storage_service.move_file(cloud_path, "flagged")

    # 8. AES Encryption of Sensitive Fields
    encrypted_gst = encryption_service.encrypt(data.get("gst_number"))
    encrypted_tax = encryption_service.encrypt(data.get("tax_id"))
    encrypted_bank = encryption_service.encrypt(data.get("bank_details"))

    # Create Invoice Record
    new_invoice = Invoice(
        invoice_number=data.get("invoice_number"),
        vendor_name=data.get("vendor_name"),
        vendor_address=data.get("vendor_address"),
        customer_name=data.get("customer_name"),
        customer_address=data.get("customer_address"),
        gst_number=encrypted_gst,
        tax_id=encrypted_tax,
        bank_details=encrypted_bank,
        po_number=data.get("po_number"),
        invoice_date=data.get("invoice_date"),
        due_date=data.get("due_date"),
        subtotal=data.get("subtotal", 0.0),
        tax_amount=data.get("tax_amount", 0.0),
        discount=data.get("discount", 0.0),
        total_amount=data.get("total_amount", 0.0),
        currency=data.get("currency", "USD"),
        cloud_file_path=cloud_path,
        original_filename=file.filename,
        status=initial_status,
        validation_status=val_status,
        risk_score=risk_score,
        risk_level=risk_level,
        duplicate_status=dup_verdict,
        sha256_checksum=sha256_hash,
        organization=user_org,
        user_id=current_user.id
    )
    db.add(new_invoice)
    db.flush()

    # Save Line Items
    for itm in data.get("items", []):
        line_item = InvoiceItem(
            invoice_id=new_invoice.id,
            description=itm.get("description", "Item"),
            quantity=itm.get("quantity", 1.0),
            unit_price=itm.get("unit_price", 0.0),
            total_price=itm.get("total_price", 0.0)
        )
        db.add(line_item)

    # Save Validation Results
    for v in validation_items:
        val_entry = ValidationResult(
            invoice_id=new_invoice.id,
            field_name=v.get("field_name"),
            extracted_value=str(v.get("extracted_value") or ""),
            validation_status=v.get("validation_status"),
            confidence_score=v.get("confidence_score", 1.0),
            validation_message=v.get("validation_message")
        )
        db.add(val_entry)

    # Save Duplicate Check
    dup_entry = DuplicateCheck(
        invoice_id=new_invoice.id,
        compared_invoice_id=matched_id,
        similarity_score=dup_score,
        duplicate_status=dup_verdict,
        matching_fields=json.dumps(dup_breakdown) if dup_breakdown else "{}"
    )
    db.add(dup_entry)

    # Save Fraud Alert
    for reason in risk_reasons:
        fraud_alert = FraudAlert(
            invoice_id=new_invoice.id,
            risk_score=risk_score,
            risk_level=risk_level,
            alert_reason=reason
        )
        db.add(fraud_alert)

    # Save Audit Log
    audit = AuditLog(
        user_id=current_user.id,
        invoice_id=new_invoice.id,
        action="INVOICE_UPLOADED_AND_PROCESSED",
        details=f"Uploaded '{file.filename}'. Risk: {risk_level} ({risk_score}), Duplicate: {dup_verdict} ({dup_score}%)."
    )
    db.add(audit)
    db.commit()
    db.refresh(new_invoice)

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
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found.")

    if current_user.role == "user" and invoice.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied to this invoice.")

    return format_invoice_detail(invoice)

@router.put("/{invoice_id}", response_model=InvoiceDetailResponse)
def update_invoice(
    invoice_id: int,
    invoice_update: InvoiceUpdate,
    current_user: User = Depends(require_role(["admin", "reviewer"])),
    db: Session = Depends(get_db)
):
    """Inline editing of extracted invoice fields with automatic re-encryption of sensitive fields."""
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found.")

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
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found.")

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
    """Role-based approval: Reviewer or Admin only."""
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found.")

    # Segregation of Duties (SoD) Anti-Fraud Enforcement
    if invoice.user_id == current_user.id and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Segregation of Duties (SoD) Violation: You cannot approve an invoice you submitted. An independent reviewer must verify and approve this invoice."
        )

    invoice.status = "approved"
    # Move cloud storage file to processed folder
    new_path = cloud_storage_service.move_file(invoice.cloud_file_path, "processed")
    invoice.cloud_file_path = new_path

    audit = AuditLog(
        user_id=current_user.id,
        invoice_id=invoice.id,
        action="INVOICE_APPROVED",
        details=f"Invoice #{invoice.invoice_number} approved by {current_user.name} ({current_user.role})."
    )
    db.add(audit)
    db.commit()
    db.refresh(invoice)
    return format_invoice_response(invoice)

@router.post("/{invoice_id}/reject", response_model=InvoiceResponse)
def reject_invoice(
    invoice_id: int,
    current_user: User = Depends(require_role(["admin", "reviewer"])),
    db: Session = Depends(get_db)
):
    """Role-based rejection: Reviewer or Admin only."""
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found.")

    invoice.status = "rejected"

    audit = AuditLog(
        user_id=current_user.id,
        invoice_id=invoice.id,
        action="INVOICE_REJECTED",
        details=f"Invoice #{invoice.invoice_number} rejected by {current_user.name} ({current_user.role})."
    )
    db.add(audit)
    db.commit()
    db.refresh(invoice)
    return format_invoice_response(invoice)

@router.get("/{invoice_id}/duplicates", response_model=dict)
def get_invoice_duplicates(
    invoice_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get duplicate comparison details, matched invoice, similarity score, and field matching breakdown."""
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found.")

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
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found.")

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
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found.")

    try:
        content = cloud_storage_service.get_file(invoice.cloud_file_path)
        filename = invoice.original_filename or "document.pdf"
        media_type = "application/pdf" if filename.lower().endswith(".pdf") else "image/png"
        return Response(content=content, media_type=media_type)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"File not found: {str(e)}")
