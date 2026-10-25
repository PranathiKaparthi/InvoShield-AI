"""Proactive vendor notifications (template messages) when an invoice changes state."""
import logging
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.agent.delivery import deliver
from app.agent.formatting import format_money
from app.agent.memory import conversation_for_contact, get_agent_settings
from app.core.config import settings
from app.channels import OutboundMessage
from app.models.agent_entities import AgentContact
from app.models.entities import Invoice

logger = logging.getLogger(__name__)


def vendor_contact_for_invoice(db: Session, invoice: Invoice) -> Optional[AgentContact]:
    if invoice.source_contact_id:
        contact = db.query(AgentContact).filter(AgentContact.id == invoice.source_contact_id).first()
        if contact and (contact.verified or contact.self_registered) and contact.kind == "vendor":
            return contact
    if invoice.vendor_name:
        return db.query(AgentContact).filter(
            AgentContact.organization == invoice.organization,
            AgentContact.kind == "vendor",
            AgentContact.verified.is_(True),
            func.lower(AgentContact.vendor_name) == invoice.vendor_name.strip().lower(),
        ).first()
    return None


def notify_vendor_of_status_change(db: Session, invoice: Invoice, event: str, reason: Optional[str] = None) -> bool:
    if not settings.AGENT_ENABLED:
        return False
    org_settings = get_agent_settings(db, invoice.organization or "General")
    if not org_settings.notify_vendors:
        return False
    contact = vendor_contact_for_invoice(db, invoice)
    if contact is None:
        return False
    conv = conversation_for_contact(db, contact)
    if conv is None:
        return False

    business = org_settings.business_name or settings.AGENT_BUSINESS_NAME
    amount = format_money(invoice.total_amount, invoice.currency)
    number = invoice.invoice_number or f"#{invoice.id}"
    if event == "approved":
        out = OutboundMessage(to=conv.sender_address, template="invoice_approved",
                              template_params=[contact.display_name, number, amount, business])
    elif event == "rejected":
        issue = reason or "please contact us for details"
        out = OutboundMessage(to=conv.sender_address, template="invoice_needs_correction",
                              template_params=[contact.display_name, number, issue])
    elif event == "paid":
        out = OutboundMessage(to=conv.sender_address, template="payment_processed",
                              template_params=[contact.display_name, number, amount, business])
    else:
        return False
    deliver(db, conv, out, invoice_id=invoice.id)
    return True
