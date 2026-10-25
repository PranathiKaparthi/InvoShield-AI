"""
Shared invoice processing pipeline.

Used by the web upload endpoint (app/api/invoices.py) AND by the InvoShield Assistant
(app/agent/tools.py) so there is exactly one implementation of:
Storage -> OCR -> Extraction -> Validation -> Duplicate check -> Fraud scoring -> Encryption -> Save.
"""
import hashlib
import json
from typing import Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.entities import (
    Invoice, InvoiceItem, ValidationResult, DuplicateCheck, FraudAlert, AuditLog
)
from app.services.cloud_storage_service import cloud_storage_service
from app.services.ocr_service import ocr_service
from app.services.invoice_extraction_service import invoice_extraction_service
from app.services.validation_service import validation_service
from app.services.duplicate_detection_service import duplicate_detection_service
from app.services.fraud_detection_service import fraud_detection_service
from app.services.encryption_service import encryption_service


def process_invoice_upload(
    db: Session,
    file_bytes: bytes,
    filename: str,
    organization: str,
    user_id: Optional[int] = None,
    source_contact_id: Optional[int] = None,
    source_channel: str = "web",
    force_status: Optional[str] = None,
    audit_actor_label: Optional[str] = None,
    demo_fallbacks: Optional[bool] = None,
) -> Invoice:
    """Run the full pipeline and persist the invoice. Returns the saved Invoice (committed)."""
    organization = organization or "General"

    # 1. Tamper-proof checksum
    sha256_hash = hashlib.sha256(file_bytes).hexdigest()

    # 2. Storage (pending folder)
    cloud_path = cloud_storage_service.upload_file(file_bytes, filename, folder="pending")

    # 3-4. OCR + structured extraction
    extracted_text, ocr_confidence = ocr_service.extract_text_and_confidence(file_bytes, filename)
    if demo_fallbacks is None:
        demo_fallbacks = settings.EXTRACTION_DEMO_FALLBACKS
    data = invoice_extraction_service.extract(extracted_text, base_confidence=ocr_confidence,
                                              demo_fallbacks=demo_fallbacks)

    # 5. Validation
    validation_items, val_status = validation_service.validate(data)

    # 6. Duplicate detection (tenant scoped)
    dup_score, dup_verdict, matched_id, dup_breakdown = duplicate_detection_service.check_duplicate(
        data, db, organization=organization
    )

    # 7. Fraud scoring (tenant scoped)
    risk_score, risk_level, risk_reasons = fraud_detection_service.analyze(
        data, dup_score, db, organization=organization
    )

    initial_status = "pending_review"
    if risk_level == "High" or dup_verdict == "Highly Likely Duplicate":
        initial_status = "flagged"
        cloud_path = cloud_storage_service.move_file(cloud_path, "flagged")
    if force_status:
        initial_status = force_status

    # 8. Encrypt sensitive identifiers
    invoice = Invoice(
        invoice_number=data.get("invoice_number"),
        vendor_name=data.get("vendor_name"),
        vendor_address=data.get("vendor_address"),
        customer_name=data.get("customer_name"),
        customer_address=data.get("customer_address"),
        gst_number=encryption_service.encrypt(data.get("gst_number")),
        tax_id=encryption_service.encrypt(data.get("tax_id")),
        bank_details=encryption_service.encrypt(data.get("bank_details")),
        po_number=data.get("po_number"),
        invoice_date=data.get("invoice_date"),
        due_date=data.get("due_date"),
        subtotal=data.get("subtotal", 0.0),
        tax_amount=data.get("tax_amount", 0.0),
        discount=data.get("discount", 0.0),
        total_amount=data.get("total_amount", 0.0),
        currency=data.get("currency", "USD"),
        cloud_file_path=cloud_path,
        original_filename=filename,
        status=initial_status,
        validation_status=val_status,
        risk_score=risk_score,
        risk_level=risk_level,
        duplicate_status=dup_verdict,
        sha256_checksum=sha256_hash,
        organization=organization,
        user_id=user_id,
        source_contact_id=source_contact_id,
        source_channel=source_channel,
        payment_status="unpaid",
    )
    db.add(invoice)
    db.flush()

    for itm in data.get("items", []):
        db.add(InvoiceItem(
            invoice_id=invoice.id,
            description=itm.get("description", "Item"),
            quantity=itm.get("quantity", 1.0),
            unit_price=itm.get("unit_price", 0.0),
            total_price=itm.get("total_price", 0.0),
        ))

    for v in validation_items:
        db.add(ValidationResult(
            invoice_id=invoice.id,
            field_name=v.get("field_name"),
            extracted_value=str(v.get("extracted_value") or ""),
            validation_status=v.get("validation_status"),
            confidence_score=v.get("confidence_score", 1.0),
            validation_message=v.get("validation_message"),
        ))

    db.add(DuplicateCheck(
        invoice_id=invoice.id,
        compared_invoice_id=matched_id,
        similarity_score=dup_score,
        duplicate_status=dup_verdict,
        matching_fields=json.dumps(dup_breakdown) if dup_breakdown else "{}",
    ))

    for reason in risk_reasons:
        db.add(FraudAlert(
            invoice_id=invoice.id,
            risk_score=risk_score,
            risk_level=risk_level,
            alert_reason=reason,
        ))

    via = f" via {source_channel}" if source_channel != "web" else ""
    actor = f" from {audit_actor_label}" if audit_actor_label else ""
    db.add(AuditLog(
        user_id=user_id,
        invoice_id=invoice.id,
        action="INVOICE_UPLOADED_AND_PROCESSED",
        details=(
            f"Uploaded '{filename}'{via}{actor}. Risk: {risk_level} ({risk_score}), "
            f"Duplicate: {dup_verdict} ({dup_score}%)."
        ),
    ))
    db.commit()
    db.refresh(invoice)
    return invoice
