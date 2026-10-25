"""
Shared invoice state-change actions (approve / reject / mark paid).

Used by the REST API and by the InvoShield Assistant so RBAC and Segregation-of-Duties rules
are enforced in exactly one place.
"""
import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.models.entities import Invoice, User, AuditLog
from app.services.cloud_storage_service import cloud_storage_service

logger = logging.getLogger(__name__)

REVIEW_ROLES = ("admin", "reviewer")


class InvoiceActionError(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def _check_reviewer(actor: User, invoice: Invoice) -> None:
    if actor is None or actor.role not in REVIEW_ROLES:
        raise InvoiceActionError(
            403,
            f"Access forbidden: Role '{getattr(actor, 'role', None)}' lacks permissions for this operation. "
            f"Required: {list(REVIEW_ROLES)}",
        )
    if actor.role == "reviewer" and invoice.organization != (actor.organization or "General"):
        raise InvoiceActionError(403, "Access denied: invoice belongs to another organization.")


def approve_invoice(db: Session, invoice: Invoice, actor: User, channel: str = "web") -> Invoice:
    _check_reviewer(actor, invoice)
    # Segregation of Duties (SoD) anti-fraud enforcement
    if invoice.user_id == actor.id and actor.role != "admin":
        raise InvoiceActionError(
            403,
            "Segregation of Duties (SoD) Violation: You cannot approve an invoice you submitted. "
            "An independent reviewer must verify and approve this invoice.",
        )
    invoice.status = "approved"
    invoice.cloud_file_path = cloud_storage_service.move_file(invoice.cloud_file_path, "processed")
    via = f" via {channel}" if channel != "web" else ""
    db.add(AuditLog(
        user_id=actor.id,
        invoice_id=invoice.id,
        action="INVOICE_APPROVED",
        details=f"Invoice #{invoice.invoice_number} approved by {actor.name} ({actor.role}){via}.",
    ))
    db.commit()
    db.refresh(invoice)
    _notify_vendor(db, invoice, "approved")
    return invoice


def reject_invoice(db: Session, invoice: Invoice, actor: User, reason: Optional[str] = None,
                   channel: str = "web") -> Invoice:
    _check_reviewer(actor, invoice)
    invoice.status = "rejected"
    via = f" via {channel}" if channel != "web" else ""
    why = f" Reason: {reason}" if reason else ""
    db.add(AuditLog(
        user_id=actor.id,
        invoice_id=invoice.id,
        action="INVOICE_REJECTED",
        details=f"Invoice #{invoice.invoice_number} rejected by {actor.name} ({actor.role}){via}.{why}",
    ))
    db.commit()
    db.refresh(invoice)
    _notify_vendor(db, invoice, "rejected", reason=reason)
    return invoice


def mark_invoice_paid(db: Session, invoice: Invoice, actor: User, channel: str = "web") -> Invoice:
    _check_reviewer(actor, invoice)
    if invoice.status != "approved":
        raise InvoiceActionError(409, "Only approved invoices can be marked as paid.")
    invoice.payment_status = "paid"
    via = f" via {channel}" if channel != "web" else ""
    db.add(AuditLog(
        user_id=actor.id,
        invoice_id=invoice.id,
        action="INVOICE_MARKED_PAID",
        details=f"Invoice #{invoice.invoice_number} marked paid by {actor.name} ({actor.role}){via}.",
    ))
    db.commit()
    db.refresh(invoice)
    _notify_vendor(db, invoice, "paid")
    return invoice


def _notify_vendor(db: Session, invoice: Invoice, event: str, reason: Optional[str] = None) -> None:
    """Best effort: tell the vendor (if they're a known assistant contact) about the change."""
    try:
        from app.agent.notifications import notify_vendor_of_status_change
        notify_vendor_of_status_change(db, invoice, event, reason=reason)
    except Exception as exc:  # never break the core action because of a notification
        logger.warning(f"Vendor notification skipped for invoice {invoice.id}: {exc}")
