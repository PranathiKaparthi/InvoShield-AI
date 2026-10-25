"""
Welcoming new vendors / customers instead of turning them away.

First message from an unknown number or email:
    "Welcome to <business>! ... please tell me your name and business name."
    (any invoice attached is accepted straight away and acknowledged)
Their reply, e.g. "Ravi, Quantum Traders":
    "Thanks Ravi, you're all set!" + the vendor menu.

From then on they can use the assistant like any vendor, but ONLY for invoices they sent
themselves, until the owner verifies them in Assistant Inbox -> Contacts. The owner gets an
item in Approvals for every new contact.
"""
import json
import re
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.agent import approval, menu
from app.agent.formatting import format_money
from app.agent.identity import Identity
from app.channels import MediaRef
from app.models.agent_entities import AgentApproval, AgentConversation
from app.services.invoice_pipeline import process_invoice_upload

ASK_NAME = ("To set you up, please tell me your name and your business name. "
            "For example: Ravi, Quantum Traders")

_SPLIT = re.compile(r"\s*(?:,|\bfrom\b|\bof\b|-|–|\|)\s*", re.IGNORECASE)
_PREFIX = re.compile(r"^(?:hi|hello|hey|namaste|vanakkam|i am|i'm|im|this is|my name is|name is|name:|me)\s+",
                     re.IGNORECASE)


def parse_name_and_business(text: str) -> Tuple[Optional[str], Optional[str]]:
    """'Ravi, Quantum Traders' / 'I am Ravi from Quantum Traders' -> ('Ravi', 'Quantum Traders')."""
    t = " ".join((text or "").split()).strip(" .!")
    for _ in range(3):
        t2 = _PREFIX.sub("", t)
        if t2 == t:
            break
        t = t2
    if not t or len(t) > 120 or menu.is_greeting(t) or menu.parse_choice(t) is not None:
        return None, None
    parts = [p.strip(" .") for p in _SPLIT.split(t, maxsplit=1) if p.strip(" .")]
    if not parts or not re.search(r"[^\W\d_]", parts[0]):
        return None, None
    name = parts[0][:60]
    business = parts[1][:120] if len(parts) > 1 else None
    return name.title() if name.islower() else name, business


def _accept_invoices(db: Session, identity: Identity, attachments: Dict[str, MediaRef]) -> List[str]:
    lines = []
    for media in attachments.values():
        inv = process_invoice_upload(
            db, file_bytes=media.data, filename=media.filename, organization=identity.organization,
            source_contact_id=identity.contact_id, source_channel=identity.channel,
            audit_actor_label=f"new contact {identity.address}", demo_fallbacks=False,
        )
        number = inv.invoice_number or "(number not readable)"
        lines.append(f"Received invoice {number} for {format_money(inv.total_amount, inv.currency)}.")
    return lines


def _notify_owner(db: Session, identity: Identity, conv: AgentConversation, summary: str,
                  payload: dict) -> None:
    existing = db.query(AgentApproval).filter(AgentApproval.requested_by_contact_id == identity.contact_id,
                                              AgentApproval.type == "new_contact",
                                              AgentApproval.status == "pending").first()
    if existing:
        existing.summary = summary
        existing.payload_json = json.dumps(payload)
        db.commit()
        return
    approval.queue_item(db, identity.organization, "new_contact", summary=summary, payload=payload,
                        conversation_id=conv.id, contact_id=identity.contact_id)


def handle_new_contact(db: Session, identity: Identity, conv: AgentConversation, text: str,
                       attachments: Dict[str, MediaRef], problems: List[str], business: str,
                       channel_name: Optional[str]) -> str:
    """Returns the reply for a sender who is not (yet) a known contact."""
    contact = identity.contact
    receipts = _accept_invoices(db, identity, attachments)
    notes = ["Note: " + "; ".join(problems) + "."] if problems else []

    if contact.onboarding_step is None:
        contact.self_registered = True
        contact.onboarding_step = "ask_name"
        contact.notes = "Started chatting on their own. Check the details, then tick Verified."
        db.commit()
        _notify_owner(db, identity, conv,
                      summary=f"New contact {identity.address} started chatting"
                              + (f" and sent {len(receipts)} invoice(s)" if receipts else ""),
                      payload={"reason": "new_contact", "address": identity.address,
                               "name_from_channel": channel_name})
        lines = [f"Welcome to {business}! 👋 I'm the invoice assistant."]
        if receipts:
            lines += ["Thank you, " + receipts[0][0].lower() + receipts[0][1:]] + receipts[1:]
        return "\n".join(lines + notes + [ASK_NAME])

    # onboarding_step == "ask_name"
    name, company = parse_name_and_business(text)
    if not name:
        lines = (["Thank you! " + " ".join(receipts)] if receipts else []) + notes
        return "\n".join(lines + [ASK_NAME])

    contact.display_name = f"{name} ({company})" if company else name
    if company:
        contact.vendor_name = company  # suggestion for the owner; not used for access until verified
    contact.onboarding_step = "done"
    db.commit()
    _notify_owner(db, identity, conv,
                  summary=f"New vendor registered: {contact.display_name}, {identity.address}. "
                          f"Verify them in Contacts to link their existing invoices.",
                  payload={"reason": "new_contact", "address": identity.address,
                           "name": name, "business_name": company})

    welcomed = Identity(identity.channel, identity.address, contact, None, "vendor", "vendor",
                        identity.organization, verified=False, limited=True)
    lines = [f"Thanks {name}, you're all set! 🙂"]
    if receipts:
        lines += receipts
    lines += notes
    body = menu.build_menu(welcomed, business, multilingual=False).split("\n", 1)[1]  # drop the greeting line
    return "\n".join(lines + [body])
