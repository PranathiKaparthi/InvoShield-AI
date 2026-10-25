"""
Identity resolution: map an inbound phone number / email to a known contact BEFORE any tool runs.
"""
import re
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.agent_entities import AgentContact
from app.models.entities import User

REVIEW_ROLES = ("admin", "reviewer")


def normalize_phone(raw: Optional[str]) -> Optional[str]:
    """Normalize to E.164. WhatsApp sends '919876543210'; 10-digit numbers are assumed Indian."""
    if not raw:
        return None
    digits = re.sub(r"\D", "", str(raw))
    if not digits:
        return None
    if len(digits) == 10:
        digits = "91" + digits
    if len(digits) == 11 and digits.startswith("0"):
        digits = "91" + digits[1:]
    return "+" + digits


def normalize_email(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    match = re.search(r"[\w.+-]+@[\w-]+(\.[\w-]+)+", str(raw))
    return match.group(0).lower() if match else None


def normalize_address(channel: str, raw: str) -> Optional[str]:
    return normalize_email(raw) if channel == "email" else normalize_phone(raw)


@dataclass
class Identity:
    channel: str
    address: str
    contact: Optional[AgentContact]
    user: Optional[User]
    kind: str  # vendor | staff | unknown
    role: str  # vendor | admin | reviewer | user | unknown
    organization: str
    verified: bool
    limited: bool = False  # self-registered vendor not yet verified by the owner

    @property
    def display_name(self) -> str:
        if self.contact:
            return self.contact.display_name
        return self.address

    @property
    def is_staff_reviewer(self) -> bool:
        return self.kind == "staff" and self.verified and self.role in REVIEW_ROLES

    @property
    def is_known(self) -> bool:
        return self.contact is not None and (self.verified or self.limited) and self.kind in ("vendor", "staff")

    @property
    def contact_id(self) -> Optional[int]:
        return self.contact.id if self.contact else None


def find_contact(db: Session, channel: str, address: str) -> Optional[AgentContact]:
    if channel == "email":
        return db.query(AgentContact).filter(func.lower(AgentContact.email) == address.lower()) \
            .order_by(AgentContact.verified.desc(), AgentContact.id).first()
    return db.query(AgentContact).filter(AgentContact.phone_e164 == address) \
        .order_by(AgentContact.verified.desc(), AgentContact.id).first()


def resolve_identity(db: Session, channel: str, raw_address: str) -> Identity:
    """Look up who is writing. Unknown senders get an unverified placeholder contact so their
    conversation and any invoice they send can be reviewed by the owner."""
    address = normalize_address(channel, raw_address) or str(raw_address)
    contact = find_contact(db, channel, address)

    if contact is None:
        contact = AgentContact(
            organization=settings.AGENT_DEFAULT_ORGANIZATION,
            display_name=f"Unknown {address}",
            kind="vendor",
            phone_e164=address if channel != "email" else None,
            email=address if channel == "email" else None,
            verified=False,
            notes="Auto-created when an unknown sender wrote in. Verify before granting access.",
        )
        db.add(contact)
        db.commit()
        db.refresh(contact)

    if not contact.verified:
        if contact.kind == "vendor" and contact.self_registered and contact.onboarding_step == "done":
            return Identity(channel, address, contact, None, "vendor", "vendor", contact.organization,
                            verified=False, limited=True)
        return Identity(channel, address, contact, None, "unknown", "unknown", contact.organization, False)

    if contact.kind == "staff":
        user = contact.user
        if user is None:
            return Identity(channel, address, contact, None, "unknown", "unknown", contact.organization, False)
        return Identity(channel, address, contact, user, "staff", user.role, contact.organization, True)

    return Identity(channel, address, contact, None, "vendor", "vendor", contact.organization, True)
