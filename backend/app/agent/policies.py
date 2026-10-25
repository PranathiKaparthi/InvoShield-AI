"""
Permission, data-scoping and redaction rules for the assistant.

These are enforced in code. The system prompt repeats them, but the model is never trusted to
enforce them on its own.
"""
import re
import time
from collections import defaultdict, deque
from typing import Deque, Dict, Set

from sqlalchemy import func, or_
from sqlalchemy.orm import Query, Session

from app.agent.identity import Identity
from app.models.entities import Invoice

# ---------------------------------------------------------------- tool permissions
VENDOR_TOOLS: Set[str] = {
    "ingest_invoice", "get_invoice_status", "list_my_invoices", "send_document_copy", "handoff_to_human",
}
STAFF_USER_TOOLS: Set[str] = {
    "ingest_invoice", "get_invoice_status", "list_my_invoices", "handoff_to_human",
}
REVIEWER_TOOLS: Set[str] = {
    "ingest_invoice", "get_invoice_status", "list_my_invoices", "get_vendor_balance",
    "list_flagged_invoices", "list_duplicates", "get_daily_summary", "request_invoice_action",
    "draft_reply", "send_document_copy", "handoff_to_human",
}


def allowed_tools(identity: Identity) -> Set[str]:
    if not identity.is_known:
        return set()
    if identity.kind == "vendor":
        return VENDOR_TOOLS
    if identity.role in ("admin", "reviewer"):
        return REVIEWER_TOOLS
    return STAFF_USER_TOOLS


# ---------------------------------------------------------------- data scoping
def scoped_invoices(db: Session, identity: Identity) -> Query:
    """Invoices this identity may see. Always tenant scoped to the contact's organization."""
    q = db.query(Invoice).filter(Invoice.organization == identity.organization)
    if not identity.is_known:
        return q.filter(Invoice.id == -1)
    if identity.kind == "vendor":
        contact = identity.contact
        conditions = [Invoice.source_contact_id == contact.id]
        if contact.vendor_name:
            conditions.append(func.lower(Invoice.vendor_name) == contact.vendor_name.strip().lower())
        return q.filter(or_(*conditions))
    if identity.role in ("admin", "reviewer"):
        return q
    # staff with plain "user" role: only invoices they submitted
    return q.filter(Invoice.user_id == identity.user.id)


# ---------------------------------------------------------------- vendor-safe statuses
VENDOR_STATUS_LABELS = {
    "uploaded": "received, under review",
    "processing": "received, under review",
    "pending_review": "received, under review",
    "flagged": "under review",
    "pending_verification": "received, waiting for verification",
    "approved": "approved",
    "rejected": "rejected",
}


def vendor_status(invoice: Invoice) -> str:
    return VENDOR_STATUS_LABELS.get(invoice.status or "", "under review")


# ---------------------------------------------------------------- redaction
_GSTIN = re.compile(r"\b\d{2}[A-Z]{5}\d{4}[A-Z][0-9A-Z]Z[0-9A-Z]\b", re.IGNORECASE)
_PAN = re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b", re.IGNORECASE)
_IFSC = re.compile(r"\b[A-Z]{4}0[A-Z0-9]{6}\b", re.IGNORECASE)
_AADHAAR = re.compile(r"\b\d{4}[ -]\d{4}[ -]\d{4}\b")
_CARD = re.compile(r"\b(?:\d[ -]?){13,19}\b")
_LONG_DIGITS = re.compile(r"(?<![\d+₹$])(?<!\d[.,])\d{9,18}(?!\d|[.,]\d)")


def _tail(value: str, keep: int = 3) -> str:
    compact = re.sub(r"[^0-9A-Za-z]", "", value)
    return compact[-keep:]


def redact(text: str) -> str:
    """Mask GSTIN, PAN, IFSC, Aadhaar, card and bank account numbers in any outbound text."""
    if not text:
        return text
    text = _GSTIN.sub(lambda m: f"[GSTIN ending {_tail(m.group(0))}]", text)
    text = _PAN.sub(lambda m: f"[PAN ending {_tail(m.group(0))}]", text)
    text = _IFSC.sub(lambda m: f"[IFSC ending {_tail(m.group(0))}]", text)
    text = _AADHAAR.sub(lambda m: f"[ID ending {_tail(m.group(0), 4)}]", text)
    text = _CARD.sub(lambda m: f"[number ending {_tail(m.group(0), 4)}]"
                     if len(re.sub(r'\D', '', m.group(0))) >= 13 else m.group(0), text)
    text = _LONG_DIGITS.sub(lambda m: f"[account ending {_tail(m.group(0), 4)}]", text)
    return text


# ---------------------------------------------------------------- untrusted data wrapping
UNTRUSTED_TAG = "untrusted_content"


def wrap_untrusted(text: str, source: str) -> str:
    """Delimit text that came from outside (messages, OCR) so the model treats it as data."""
    safe = (text or "").replace(f"</{UNTRUSTED_TAG}", f"&lt;/{UNTRUSTED_TAG}")
    return f'<{UNTRUSTED_TAG} source="{source}">\n{safe}\n</{UNTRUSTED_TAG}>'


# ---------------------------------------------------------------- rate limiting
class RateLimiter:
    """Simple in-process sliding window limiter keyed by sender address."""

    def __init__(self):
        self._events: Dict[str, Deque[float]] = defaultdict(deque)

    def allow(self, key: str, limit_per_minute: int) -> bool:
        if limit_per_minute <= 0:
            return True
        now = time.monotonic()
        window = self._events[key]
        while window and now - window[0] > 60:
            window.popleft()
        if len(window) >= limit_per_minute:
            return False
        window.append(now)
        return True

    def reset(self):
        self._events.clear()


rate_limiter = RateLimiter()
