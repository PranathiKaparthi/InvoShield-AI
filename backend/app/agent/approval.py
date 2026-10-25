"""
Human-in-the-loop controls.

1. Chat confirmations: a reviewer asks the assistant to approve/reject/mark-paid an invoice ->
   an `invoice_action` item with status `awaiting_confirmation` is created -> the action runs ONLY
   when the same verified person replies YES (or taps the button). This is handled
   deterministically in code; the language model never executes the action itself.
2. Approval queue: messages to third parties, document copies, held replies and hand-offs wait
   for an owner/reviewer decision in the Assistant Inbox.
"""
import json
import re
from datetime import timedelta
from typing import Any, Dict, Optional, Tuple

from sqlalchemy.orm import Session

from app.agent.delivery import deliver
from app.agent.formatting import format_money
from app.agent.identity import Identity
from app.agent.memory import conversation_for_contact, utcnow_naive
from app.agent.policies import scoped_invoices
from app.channels import OutboundMessage
from app.core.config import settings
from app.models.agent_entities import AgentApproval, AgentContact, AgentConversation
from app.models.entities import AuditLog, Invoice, User
from app.services import invoice_actions
from app.services.cloud_storage_service import cloud_storage_service

YES_WORDS = {"yes", "y", "yes confirm", "confirm", "confirmed", "ok confirm", "haan", "ha", "haa", "ji haan",
             "aamam", "aama", "aam", "avunu", "sari", "ஆம்", "ஆமாம்", "हाँ", "हां", "అవును"}
NO_WORDS = {"no", "n", "cancel", "stop", "nahi", "nahin", "venda", "illai", "vaddu", "வேண்டாம்", "नहीं", "వద్దు"}

ACTION_LABELS = {"approve": "approve", "reject": "reject", "mark_paid": "mark as paid"}


def _norm(text: str) -> str:
    return re.sub(r"[^\w\sऀ-෿]", "", (text or "").strip().lower()).strip()


def classify_confirmation_reply(text: str, button_payload: Optional[str]) -> Tuple[Optional[str], Optional[int]]:
    """Returns ("confirm"|"cancel"|None, approval_id or None)."""
    if button_payload:
        m = re.fullmatch(r"(confirm|cancel):(\d+)", button_payload.strip())
        if m:
            return m.group(1), int(m.group(2))
    word = _norm(text)
    if word in YES_WORDS:
        return "confirm", None
    if word in NO_WORDS:
        return "cancel", None
    return None, None


# ------------------------------------------------------------------ confirmations
def create_confirmation(db: Session, identity: Identity, conv: AgentConversation, invoice: Invoice,
                        action: str, reason: Optional[str]) -> AgentApproval:
    # Only one open confirmation per person: newer request supersedes older ones.
    for old in db.query(AgentApproval).filter(AgentApproval.requested_by_contact_id == identity.contact_id,
                                              AgentApproval.status == "awaiting_confirmation").all():
        old.status = "superseded"
    label = ACTION_LABELS[action]
    item = AgentApproval(
        organization=identity.organization,
        type="invoice_action",
        status="awaiting_confirmation",
        summary=f"{identity.display_name} asked to {label} invoice {invoice.invoice_number} "
                f"({format_money(invoice.total_amount, invoice.currency)}, {invoice.vendor_name})",
        payload_json=json.dumps({"invoice_id": invoice.id, "action": action, "reason": reason}),
        conversation_id=conv.id,
        requested_by_contact_id=identity.contact_id,
        created_by_agent=True,
        expires_at=utcnow_naive() + timedelta(minutes=settings.AGENT_CONFIRMATION_TTL_MINUTES),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def find_open_confirmation(db: Session, identity: Identity, approval_id: Optional[int]) -> Optional[AgentApproval]:
    q = db.query(AgentApproval).filter(AgentApproval.requested_by_contact_id == identity.contact_id,
                                       AgentApproval.type == "invoice_action",
                                       AgentApproval.status == "awaiting_confirmation")
    if approval_id:
        q = q.filter(AgentApproval.id == approval_id)
    item = q.order_by(AgentApproval.id.desc()).first()
    if item and item.expires_at and item.expires_at < utcnow_naive():
        item.status = "expired"
        db.commit()
        return None
    return item


def execute_confirmation(db: Session, identity: Identity, item: AgentApproval, decision: str) -> str:
    """Run (or cancel) a confirmed invoice action. Permissions are re-checked at execution time."""
    payload = json.loads(item.payload_json or "{}")
    action = payload.get("action")
    item.decided_at = utcnow_naive()

    if decision == "cancel":
        item.status = "cancelled"
        db.commit()
        return "Okay, cancelled. Nothing was changed."

    if not identity.is_staff_reviewer:
        item.status = "rejected"
        db.commit()
        return "Sorry, you are not allowed to do that."

    invoice = scoped_invoices(db, identity).filter(Invoice.id == payload.get("invoice_id")).first()
    if invoice is None:
        item.status = "failed"
        db.commit()
        return "Sorry, I couldn't find that invoice any more."

    actor: User = identity.user
    try:
        if action == "approve":
            invoice_actions.approve_invoice(db, invoice, actor, channel=identity.channel)
            done = f"Done. Invoice {invoice.invoice_number} is approved."
        elif action == "reject":
            invoice_actions.reject_invoice(db, invoice, actor, reason=payload.get("reason"),
                                           channel=identity.channel)
            done = f"Done. Invoice {invoice.invoice_number} is rejected."
        elif action == "mark_paid":
            invoice_actions.mark_invoice_paid(db, invoice, actor, channel=identity.channel)
            done = f"Done. Invoice {invoice.invoice_number} is marked as paid."
        else:
            raise invoice_actions.InvoiceActionError(400, "Unknown action.")
    except invoice_actions.InvoiceActionError as exc:
        item.status = "failed"
        item.decided_by = actor.id
        db.commit()
        return f"I couldn't do that: {exc.detail}"

    item.status = "executed"
    item.decided_by = actor.id
    db.commit()
    return done


# ------------------------------------------------------------------ approval queue
def queue_item(db: Session, organization: str, item_type: str, summary: str, payload: Dict[str, Any],
               conversation_id: Optional[int] = None, contact_id: Optional[int] = None) -> AgentApproval:
    item = AgentApproval(organization=organization, type=item_type, status="pending", summary=summary,
                         payload_json=json.dumps(payload, default=str), conversation_id=conversation_id,
                         requested_by_contact_id=contact_id, created_by_agent=True)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


class ApprovalError(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def decide(db: Session, item: AgentApproval, user: User, approve: bool,
           edited_text: Optional[str] = None) -> AgentApproval:
    """Owner/reviewer decision from the Assistant Inbox."""
    if item.status != "pending":
        raise ApprovalError(409, f"This item is already {item.status}.")
    payload = json.loads(item.payload_json or "{}")
    item.decided_by = user.id
    item.decided_at = utcnow_naive()

    if not approve:
        item.status = "rejected"
        db.add(AuditLog(user_id=user.id, action="AGENT_APPROVAL_REJECTED",
                        details=f"Approval #{item.id} ({item.type}) rejected: {item.summary}"))
        db.commit()
        return item

    if item.type == "handoff":
        item.status = "resolved"
    elif item.type in ("outbound_message", "held_reply"):
        conv = _target_conversation(db, item, payload)
        text = (edited_text or payload.get("text") or "").strip()
        if not text:
            raise ApprovalError(400, "Message text is empty.")
        deliver(db, conv, OutboundMessage(to=conv.sender_address, text=text), actor_user_id=user.id)
        item.status = "sent"
    elif item.type == "document_copy":
        conv = _target_conversation(db, item, payload)
        invoice = db.query(Invoice).filter(Invoice.id == payload.get("invoice_id"),
                                           Invoice.organization == item.organization).first()
        if invoice is None:
            raise ApprovalError(404, "Invoice not found.")
        try:
            data = cloud_storage_service.get_file(invoice.cloud_file_path)
        except FileNotFoundError:
            raise ApprovalError(404, "The invoice file could not be found in storage.")
        filename = invoice.original_filename or f"{invoice.invoice_number or 'invoice'}.pdf"
        mime = "application/pdf" if filename.lower().endswith(".pdf") else "application/octet-stream"
        caption = edited_text or f"Copy of invoice {invoice.invoice_number}"
        deliver(db, conv, OutboundMessage(to=conv.sender_address, text=caption, document=data,
                                          document_filename=filename, document_mime=mime),
                actor_user_id=user.id, invoice_id=invoice.id)
        item.status = "sent"
    else:
        raise ApprovalError(400, f"Items of type '{item.type}' cannot be approved here.")

    db.add(AuditLog(user_id=user.id, action="AGENT_APPROVAL_APPROVED",
                    details=f"Approval #{item.id} ({item.type}) approved: {item.summary}"))
    db.commit()
    return item


def _target_conversation(db: Session, item: AgentApproval, payload: Dict[str, Any]) -> AgentConversation:
    contact_id = payload.get("contact_id")
    if contact_id:
        contact = db.query(AgentContact).filter(AgentContact.id == contact_id,
                                                AgentContact.organization == item.organization).first()
        if contact is None:
            raise ApprovalError(404, "Recipient contact not found.")
        conv = conversation_for_contact(db, contact)
        if conv is None:
            raise ApprovalError(400, "Recipient has no phone number or email.")
        return conv
    if item.conversation_id:
        conv = db.query(AgentConversation).filter(AgentConversation.id == item.conversation_id).first()
        if conv:
            return conv
    raise ApprovalError(400, "No recipient for this item.")
