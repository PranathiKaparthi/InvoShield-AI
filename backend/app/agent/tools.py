"""
Assistant tools: strict JSON schemas + thin wrappers around existing InvoShield services.

Rules enforced here (never delegated to the model):
  * the caller's identity decides which tools exist at all (policies.allowed_tools)
  * every query is scoped to what that identity may see (policies.scoped_invoices)
  * decrypted GST / tax ID / bank details are never returned
  * write actions only create confirmations or approval-queue items
  * every call is written to the audit log
"""
import json
import logging
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, Callable, Dict, List, Optional

from rapidfuzz import fuzz, process, utils
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.agent import approval
from app.agent.formatting import (fmt_dt, format_money, local_day_bounds_utc, local_today,
                                  parse_iso_date)
from app.agent.identity import Identity, normalize_email, normalize_phone
from app.agent.policies import allowed_tools, scoped_invoices, vendor_status
from app.channels import MediaRef
from app.models.agent_entities import AgentApproval, AgentContact, AgentConversation
from app.models.entities import AuditLog, DuplicateCheck, FraudAlert, Invoice, ValidationResult
from app.services.invoice_pipeline import process_invoice_upload

logger = logging.getLogger(__name__)

PENDING_STATUSES = ("uploaded", "processing", "pending_review", "flagged", "pending_verification")
MAX_LIST = 10


@dataclass
class ToolContext:
    db: Session
    identity: Identity
    conversation: AgentConversation
    attachments: Dict[str, MediaRef] = field(default_factory=dict)
    created_confirmations: List[AgentApproval] = field(default_factory=list)
    ingested_invoice_ids: List[int] = field(default_factory=list)


class ToolInputError(Exception):
    pass


# ======================================================================== schemas
DATE = {"type": "string", "description": "Date as YYYY-MM-DD"}

TOOL_SCHEMAS: Dict[str, Dict[str, Any]] = {
    "ingest_invoice": {
        "description": "Process an invoice file the sender attached in THIS message (PDF or photo) through "
                       "OCR, validation, duplicate and fraud checks, and save it. Returns a short receipt.",
        "input_schema": {"type": "object", "properties": {
            "attachment_id": {"type": "string", "description": "attachment_id listed with the message"},
        }, "required": ["attachment_id"], "additionalProperties": False},
    },
    "get_invoice_status": {
        "description": "Look up one invoice by its invoice number and return its current status.",
        "input_schema": {"type": "object", "properties": {
            "invoice_number": {"type": "string", "minLength": 1, "maxLength": 100},
        }, "required": ["invoice_number"], "additionalProperties": False},
    },
    "list_my_invoices": {
        "description": "List the caller's invoices (vendors: their own; reviewers: the business's), "
                       "optionally filtered by status and date range. Most recent first.",
        "input_schema": {"type": "object", "properties": {
            "status": {"type": "string", "enum": ["all", "pending", "approved", "rejected", "paid", "unpaid"]},
            "from_date": DATE, "to_date": DATE,
        }, "additionalProperties": False},
    },
    "get_vendor_balance": {
        "description": "How much the business owes a vendor: approved but unpaid invoices, plus invoices "
                       "still under review. Vendor name may be approximate.",
        "input_schema": {"type": "object", "properties": {
            "vendor_name": {"type": "string", "minLength": 2, "maxLength": 255},
        }, "required": ["vendor_name"], "additionalProperties": False},
    },
    "list_flagged_invoices": {
        "description": "Suspicious invoices with the fraud engine's plain-language reasons. "
                       "Defaults to High and Medium risk from the last 7 days.",
        "input_schema": {"type": "object", "properties": {
            "risk_level": {"type": "string", "enum": ["high", "medium", "high_and_medium"]},
            "from_date": DATE, "to_date": DATE,
        }, "additionalProperties": False},
    },
    "list_duplicates": {
        "description": "Recent possible / highly likely duplicate invoices with similarity percentage.",
        "input_schema": {"type": "object", "properties": {
            "min_similarity": {"type": "number", "minimum": 50, "maximum": 100},
            "days": {"type": "integer", "minimum": 1, "maximum": 365},
        }, "additionalProperties": False},
    },
    "get_daily_summary": {
        "description": "Summary for one day: invoices received, approved, flagged, total value, top vendors.",
        "input_schema": {"type": "object", "properties": {"date": DATE}, "additionalProperties": False},
    },
    "request_invoice_action": {
        "description": "Prepare approving, rejecting or marking-paid an invoice. This does NOT perform the "
                       "action: it creates a confirmation the user must answer YES to.",
        "input_schema": {"type": "object", "properties": {
            "invoice_number": {"type": "string", "minLength": 1, "maxLength": 100},
            "action": {"type": "string", "enum": ["approve", "reject", "mark_paid"]},
            "reason": {"type": "string", "maxLength": 500},
        }, "required": ["invoice_number", "action"], "additionalProperties": False},
    },
    "draft_reply": {
        "description": "Draft a message to a vendor or contact. It is put in the approval queue for the owner; "
                       "it is NOT sent now.",
        "input_schema": {"type": "object", "properties": {
            "recipient": {"type": "string", "description": "Contact name, vendor name, phone or email"},
            "message": {"type": "string", "minLength": 1, "maxLength": 2000},
        }, "required": ["recipient", "message"], "additionalProperties": False},
    },
    "send_document_copy": {
        "description": "Request sending a copy of an invoice file. Always waits for owner approval. "
                       "Vendors can only request their own invoices, sent to themselves.",
        "input_schema": {"type": "object", "properties": {
            "invoice_number": {"type": "string", "minLength": 1, "maxLength": 100},
            "recipient": {"type": "string", "description": "Reviewers only: contact name, phone or email"},
        }, "required": ["invoice_number"], "additionalProperties": False},
    },
    "handoff_to_human": {
        "description": "Pass the conversation to a human (disputes, complaints, legal, payment negotiation, "
                       "or anything you cannot answer from tool results).",
        "input_schema": {"type": "object", "properties": {
            "reason": {"type": "string", "maxLength": 200},
            "summary": {"type": "string", "maxLength": 1000},
        }, "required": ["reason"], "additionalProperties": False},
    },
}


def tool_definitions(identity: Identity) -> List[Dict[str, Any]]:
    """Anthropic tool definitions for the tools this identity may use."""
    names = allowed_tools(identity)
    return [{"name": n, **TOOL_SCHEMAS[n]} for n in TOOL_SCHEMAS if n in names]


# ======================================================================== validation
_TYPES = {"string": str, "number": (int, float), "integer": int, "object": dict, "boolean": bool}


def validate_args(schema: Dict[str, Any], args: Any) -> Dict[str, Any]:
    if not isinstance(args, dict):
        raise ToolInputError("Arguments must be an object.")
    props = schema.get("properties", {})
    for req in schema.get("required", []):
        if req not in args or args[req] in (None, ""):
            raise ToolInputError(f"Missing required field '{req}'.")
    clean: Dict[str, Any] = {}
    for key, value in args.items():
        if key not in props:
            if schema.get("additionalProperties") is False:
                raise ToolInputError(f"Unexpected field '{key}'.")
            continue
        spec = props[key]
        expected = _TYPES.get(spec.get("type"))
        if expected and (not isinstance(value, expected) or isinstance(value, bool) and spec.get("type") != "boolean"):
            raise ToolInputError(f"Field '{key}' must be {spec.get('type')}.")
        if "enum" in spec and value not in spec["enum"]:
            raise ToolInputError(f"Field '{key}' must be one of {spec['enum']}.")
        if isinstance(value, str):
            value = value.strip()
            if len(value) < spec.get("minLength", 0) or len(value) > spec.get("maxLength", 10**6):
                raise ToolInputError(f"Field '{key}' has an invalid length.")
            if spec is DATE and parse_iso_date(value) is None:
                raise ToolInputError(f"Field '{key}' must be a YYYY-MM-DD date.")
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if "minimum" in spec and value < spec["minimum"] or "maximum" in spec and value > spec["maximum"]:
                raise ToolInputError(f"Field '{key}' is out of range.")
        clean[key] = value
    return clean


# ======================================================================== helpers
def _money(inv: Invoice) -> str:
    return format_money(inv.total_amount, inv.currency)


def _find_by_number(ctx: ToolContext, number: str) -> List[Invoice]:
    q = scoped_invoices(ctx.db, ctx.identity)
    exact = q.filter(func.lower(Invoice.invoice_number) == number.strip().lower()) \
        .order_by(Invoice.created_at.desc()).limit(5).all()
    if exact:
        return exact
    return q.filter(Invoice.invoice_number.ilike(f"%{number.strip()}%")) \
        .order_by(Invoice.created_at.desc()).limit(5).all()


def _approved_on(db: Session, invoice: Invoice) -> Optional[str]:
    row = db.query(AuditLog).filter(AuditLog.invoice_id == invoice.id, AuditLog.action == "INVOICE_APPROVED") \
        .order_by(AuditLog.timestamp.desc()).first()
    return fmt_dt(row.timestamp) if row else None


def _validation_issues(db: Session, invoice: Invoice) -> List[str]:
    rows = db.query(ValidationResult).filter(ValidationResult.invoice_id == invoice.id,
                                             ValidationResult.validation_status.in_(["Invalid", "Warning", "Missing"])).all()
    issues = []
    for r in rows:
        if r.field_name in ("gst_number", "tax_id", "bank_details"):
            issues.append(f"{r.field_name.replace('_', ' ')}: {r.validation_status.lower()}")
        else:
            issues.append(r.validation_message or f"{r.field_name}: {r.validation_status}")
    return issues[:6]


def _risk_reasons(db: Session, invoice: Invoice, limit: int = 3) -> List[str]:
    rows = db.query(FraudAlert).filter(FraudAlert.invoice_id == invoice.id).limit(limit).all()
    return [r.alert_reason for r in rows if not r.alert_reason.startswith("Low Risk")]


def invoice_view(ctx: ToolContext, inv: Invoice, detail: bool = False) -> Dict[str, Any]:
    """A safe, role-appropriate view of an invoice. Never includes GST / tax ID / bank details."""
    view: Dict[str, Any] = {
        "invoice_number": inv.invoice_number,
        "vendor_name": inv.vendor_name,
        "amount": _money(inv),
        "invoice_date": inv.invoice_date,
        "due_date": inv.due_date,
        "payment_status": inv.payment_status or "unpaid",
        "received_on": fmt_dt(inv.created_at),
    }
    if ctx.identity.kind == "vendor":
        view["status"] = vendor_status(inv)
        if inv.status == "approved":
            view["approved_on"] = _approved_on(ctx.db, inv)
    else:
        view["status"] = inv.status
        view["invoice_id"] = inv.id
        view["risk_level"] = inv.risk_level
        view["duplicate_status"] = inv.duplicate_status
        if detail:
            view["risk_reasons"] = _risk_reasons(ctx.db, inv)
            view["validation_issues"] = _validation_issues(ctx.db, inv)
            if inv.status == "approved":
                view["approved_on"] = _approved_on(ctx.db, inv)
    return view


def _date_range(args: Dict[str, Any], default_days: Optional[int]):
    start_d = parse_iso_date(args.get("from_date"))
    end_d = parse_iso_date(args.get("to_date"))
    if start_d is None and default_days:
        start_d = local_today() - timedelta(days=default_days - 1)
    start = local_day_bounds_utc(start_d)[0] if start_d else None
    end = local_day_bounds_utc(end_d)[1] if end_d else None
    return start, end


def _match_contact(ctx: ToolContext, text: str) -> Dict[str, Any]:
    org = ctx.identity.organization
    contacts = ctx.db.query(AgentContact).filter(AgentContact.organization == org,
                                                 AgentContact.verified.is_(True)).all()
    phone, email = normalize_phone(text), normalize_email(text)
    for c in contacts:
        if (email and c.email and c.email.lower() == email) or (phone and len(phone) >= 11 and c.phone_e164 == phone):
            return {"contact": c}
    choices = {}
    for c in contacts:
        for label in filter(None, [c.display_name, c.vendor_name]):
            choices[f"{c.id}|{label}"] = label
    matches = process.extract(text, choices, scorer=fuzz.WRatio, processor=utils.default_process, limit=3)
    good = [(key, score) for _, score, key in matches if score >= 80]
    ids = list(dict.fromkeys(int(k.split("|")[0]) for k, _ in good))
    if len(ids) == 1:
        return {"contact": next(c for c in contacts if c.id == ids[0])}
    if len(ids) > 1:
        return {"ambiguous": [next(c.display_name for c in contacts if c.id == i) for i in ids]}
    return {}


# ======================================================================== tools
def t_ingest_invoice(ctx: ToolContext, args: Dict[str, Any]) -> Dict[str, Any]:
    media = ctx.attachments.get(args["attachment_id"])
    if media is None or media.data is None:
        return {"error": "No such attachment in this message."}
    ident = ctx.identity
    inv = process_invoice_upload(
        ctx.db, file_bytes=media.data, filename=media.filename,
        organization=ident.organization,
        user_id=ident.user.id if ident.kind == "staff" else None,
        source_contact_id=ident.contact_id,
        source_channel=ident.channel,
        audit_actor_label=f"{ident.display_name} ({ident.address})",
        demo_fallbacks=False,
    )
    ctx.ingested_invoice_ids.append(inv.id)
    receipt = invoice_view(ctx, inv, detail=ident.kind != "vendor")
    receipt["problems_found"] = [
        i for i in _validation_issues(ctx.db, inv)
        if not any(s in i.lower() for s in ("gst", "tax id", "bank"))
    ] if ident.kind == "vendor" else receipt.get("validation_issues", [])
    if not inv.invoice_number:
        receipt["note"] = "The invoice number could not be read clearly."
    return {"saved": True, "invoice": receipt}


def t_get_invoice_status(ctx: ToolContext, args: Dict[str, Any]) -> Dict[str, Any]:
    found = _find_by_number(ctx, args["invoice_number"])
    if not found:
        return {"found": False, "message": "No invoice with that number is visible to this sender."}
    return {"found": True, "invoices": [invoice_view(ctx, i, detail=True) for i in found]}


def t_list_my_invoices(ctx: ToolContext, args: Dict[str, Any]) -> Dict[str, Any]:
    q = scoped_invoices(ctx.db, ctx.identity)
    status = args.get("status", "all")
    if status == "pending":
        q = q.filter(Invoice.status.in_(PENDING_STATUSES))
    elif status in ("approved", "rejected"):
        q = q.filter(Invoice.status == status)
    elif status == "paid":
        q = q.filter(Invoice.payment_status == "paid")
    elif status == "unpaid":
        q = q.filter(Invoice.status == "approved", or_(Invoice.payment_status.is_(None), Invoice.payment_status != "paid"))
    start, end = _date_range(args, None)
    if start:
        q = q.filter(Invoice.created_at >= start)
    if end:
        q = q.filter(Invoice.created_at < end)
    total = q.count()
    rows = q.order_by(Invoice.created_at.desc()).limit(MAX_LIST).all()
    return {"total": total, "showing": len(rows), "invoices": [invoice_view(ctx, i) for i in rows]}


def t_get_vendor_balance(ctx: ToolContext, args: Dict[str, Any]) -> Dict[str, Any]:
    q = scoped_invoices(ctx.db, ctx.identity)
    names = [n for (n,) in q.with_entities(Invoice.vendor_name).distinct().all() if n]
    if not names:
        return {"found": False, "message": "There are no invoices yet."}
    matches = process.extract(args["vendor_name"], names, scorer=fuzz.WRatio, processor=utils.default_process, limit=4)
    strong = [(n, s) for n, s, _ in matches if s >= 85]
    if not strong:
        return {"found": False, "message": "No vendor with a similar name.",
                "closest": [n for n, s, _ in matches if s >= 60]}
    if len(strong) > 1 and strong[0][1] - strong[1][1] < 5:
        return {"ambiguous": True, "candidates": [n for n, _ in strong],
                "message": "Several vendors match. Ask which one."}
    vendor = strong[0][0]
    rows = q.filter(Invoice.vendor_name == vendor).all()
    owed: Dict[str, float] = {}
    in_review: Dict[str, float] = {}
    owed_count = review_count = 0
    for inv in rows:
        cur = (inv.currency or "INR").upper()
        if inv.status == "approved" and (inv.payment_status or "unpaid") != "paid":
            owed[cur] = owed.get(cur, 0.0) + float(inv.total_amount or 0)
            owed_count += 1
        elif inv.status in PENDING_STATUSES:
            in_review[cur] = in_review.get(cur, 0.0) + float(inv.total_amount or 0)
            review_count += 1
    return {
        "found": True, "vendor_name": vendor,
        "approved_unpaid_total": [format_money(v, c) for c, v in owed.items()] or [format_money(0, "INR")],
        "approved_unpaid_count": owed_count,
        "under_review_total": [format_money(v, c) for c, v in in_review.items()] or [format_money(0, "INR")],
        "under_review_count": review_count,
    }


def t_list_flagged_invoices(ctx: ToolContext, args: Dict[str, Any]) -> Dict[str, Any]:
    level = args.get("risk_level", "high_and_medium")
    levels = {"high": ["high"], "medium": ["medium"], "high_and_medium": ["high", "medium"]}[level]
    q = scoped_invoices(ctx.db, ctx.identity).filter(
        or_(func.lower(Invoice.risk_level).in_(levels), Invoice.status == "flagged"))
    start, end = _date_range(args, 7)
    if start:
        q = q.filter(Invoice.created_at >= start)
    if end:
        q = q.filter(Invoice.created_at < end)
    total = q.count()
    rows = q.order_by(Invoice.risk_score.desc(), Invoice.created_at.desc()).limit(MAX_LIST).all()
    return {"total": total, "invoices": [
        {**invoice_view(ctx, i), "risk_score": i.risk_score, "reasons": _risk_reasons(ctx.db, i)} for i in rows
    ]}


def t_list_duplicates(ctx: ToolContext, args: Dict[str, Any]) -> Dict[str, Any]:
    min_sim = float(args.get("min_similarity", 75))
    since = local_day_bounds_utc(local_today() - timedelta(days=int(args.get("days", 30)) - 1))[0]
    visible = scoped_invoices(ctx.db, ctx.identity).subquery()
    rows = ctx.db.query(DuplicateCheck, Invoice).join(Invoice, Invoice.id == DuplicateCheck.invoice_id) \
        .filter(Invoice.id.in_(ctx.db.query(visible.c.id)),
                DuplicateCheck.similarity_score >= min_sim,
                DuplicateCheck.duplicate_status != "No Significant Duplicate",
                Invoice.created_at >= since) \
        .order_by(DuplicateCheck.similarity_score.desc()).limit(MAX_LIST).all()
    out = []
    for dup, inv in rows:
        other = ctx.db.query(Invoice).filter(Invoice.id == dup.compared_invoice_id).first()
        out.append({**invoice_view(ctx, inv), "similarity_percent": round(dup.similarity_score, 1),
                    "verdict": dup.duplicate_status,
                    "matches_invoice": other.invoice_number if other else None,
                    "matches_received_on": fmt_dt(other.created_at) if other else None})
    return {"count": len(out), "duplicates": out}


def t_get_daily_summary(ctx: ToolContext, args: Dict[str, Any]) -> Dict[str, Any]:
    day = parse_iso_date(args.get("date")) or local_today()
    start, end = local_day_bounds_utc(day)
    scope = scoped_invoices(ctx.db, ctx.identity)
    received = scope.filter(Invoice.created_at >= start, Invoice.created_at < end).all()
    visible_ids = scope.with_entities(Invoice.id).subquery()
    approved = ctx.db.query(func.count(func.distinct(AuditLog.invoice_id))).filter(
        AuditLog.action == "INVOICE_APPROVED", AuditLog.timestamp >= start, AuditLog.timestamp < end,
        AuditLog.invoice_id.in_(ctx.db.query(visible_ids.c.id))).scalar() or 0
    totals: Dict[str, float] = {}
    by_vendor: Dict[str, float] = {}
    for inv in received:
        cur = (inv.currency or "INR").upper()
        totals[cur] = totals.get(cur, 0.0) + float(inv.total_amount or 0)
        by_vendor[inv.vendor_name or "Unknown"] = by_vendor.get(inv.vendor_name or "Unknown", 0.0) + float(inv.total_amount or 0)
    top = sorted(by_vendor.items(), key=lambda kv: kv[1], reverse=True)[:3]
    cur0 = received[0].currency if received else "INR"
    return {
        "date": day.isoformat(),
        "received": len(received),
        "approved": int(approved),
        "flagged": sum(1 for i in received if i.status == "flagged" or (i.risk_level or "").lower() == "high"),
        "received_value": [format_money(v, c) for c, v in totals.items()] or [format_money(0, "INR")],
        "top_vendors": [{"vendor": v, "amount": format_money(a, cur0)} for v, a in top],
        "waiting_for_review_overall": scope.filter(Invoice.status.in_(PENDING_STATUSES)).count(),
    }


def t_request_invoice_action(ctx: ToolContext, args: Dict[str, Any]) -> Dict[str, Any]:
    found = _find_by_number(ctx, args["invoice_number"])
    if not found:
        return {"error": "No invoice with that number was found."}
    exact = [i for i in found if (i.invoice_number or "").lower() == args["invoice_number"].strip().lower()]
    candidates = exact or found
    if len(candidates) > 1:
        return {"ambiguous": True, "message": "More than one invoice matches. Ask which one.",
                "candidates": [invoice_view(ctx, i) for i in candidates]}
    inv = candidates[0]
    action = args["action"]
    if action == "approve" and inv.status == "approved":
        return {"error": f"Invoice {inv.invoice_number} is already approved."}
    if action == "reject" and inv.status == "rejected":
        return {"error": f"Invoice {inv.invoice_number} is already rejected."}
    if action == "mark_paid" and inv.status != "approved":
        return {"error": "Only approved invoices can be marked as paid."}
    if action == "mark_paid" and inv.payment_status == "paid":
        return {"error": f"Invoice {inv.invoice_number} is already marked as paid."}
    item = approval.create_confirmation(ctx.db, ctx.identity, ctx.conversation, inv, action, args.get("reason"))
    ctx.created_confirmations.append(item)
    return {
        "confirmation_required": True,
        "action_performed": False,
        "invoice": invoice_view(ctx, inv, detail=True),
        "action": action,
        "instruction": "Nothing has changed yet. Ask the user to reply YES to confirm or NO to cancel.",
    }


def t_draft_reply(ctx: ToolContext, args: Dict[str, Any]) -> Dict[str, Any]:
    match = _match_contact(ctx, args["recipient"])
    if "ambiguous" in match:
        return {"ambiguous": True, "candidates": match["ambiguous"], "message": "Ask which contact."}
    contact = match.get("contact")
    if contact is None:
        return {"error": "No verified contact matches that recipient."}
    item = approval.queue_item(
        ctx.db, ctx.identity.organization, "outbound_message",
        summary=f"Message to {contact.display_name} drafted for {ctx.identity.display_name}",
        payload={"contact_id": contact.id, "text": args["message"]},
        conversation_id=ctx.conversation.id, contact_id=ctx.identity.contact_id,
    )
    return {"queued": True, "approval_id": item.id, "recipient": contact.display_name, "sent": False,
            "message": "Draft saved to the approval queue. It will be sent after approval in the Assistant Inbox."}


def t_send_document_copy(ctx: ToolContext, args: Dict[str, Any]) -> Dict[str, Any]:
    found = _find_by_number(ctx, args["invoice_number"])
    exact = [i for i in found if (i.invoice_number or "").lower() == args["invoice_number"].strip().lower()]
    candidates = exact or found
    if not candidates:
        return {"error": "No invoice with that number is visible to this sender."}
    if len(candidates) > 1:
        return {"ambiguous": True, "candidates": [invoice_view(ctx, i) for i in candidates]}
    inv = candidates[0]
    if ctx.identity.kind == "vendor" or not args.get("recipient"):
        contact = ctx.identity.contact
    else:
        match = _match_contact(ctx, args["recipient"])
        if "ambiguous" in match:
            return {"ambiguous": True, "candidates": match["ambiguous"], "message": "Ask which contact."}
        contact = match.get("contact")
        if contact is None:
            return {"error": "No verified contact matches that recipient."}
    item = approval.queue_item(
        ctx.db, ctx.identity.organization, "document_copy",
        summary=f"Send copy of invoice {inv.invoice_number} to {contact.display_name} "
                f"(requested by {ctx.identity.display_name})",
        payload={"invoice_id": inv.id, "contact_id": contact.id},
        conversation_id=ctx.conversation.id, contact_id=ctx.identity.contact_id,
    )
    return {"queued": True, "approval_id": item.id, "sent": False,
            "message": "Request saved. The copy will be sent after the team approves it."}


def t_handoff_to_human(ctx: ToolContext, args: Dict[str, Any]) -> Dict[str, Any]:
    item = approval.queue_item(
        ctx.db, ctx.identity.organization, "handoff",
        summary=f"{ctx.identity.display_name}: {args['reason']}",
        payload={"reason": args["reason"], "summary": args.get("summary", "")},
        conversation_id=ctx.conversation.id, contact_id=ctx.identity.contact_id,
    )
    return {"handed_off": True, "approval_id": item.id,
            "message": "The team has been notified and will follow up."}


TOOL_FUNCS: Dict[str, Callable[[ToolContext, Dict[str, Any]], Dict[str, Any]]] = {
    "ingest_invoice": t_ingest_invoice,
    "get_invoice_status": t_get_invoice_status,
    "list_my_invoices": t_list_my_invoices,
    "get_vendor_balance": t_get_vendor_balance,
    "list_flagged_invoices": t_list_flagged_invoices,
    "list_duplicates": t_list_duplicates,
    "get_daily_summary": t_get_daily_summary,
    "request_invoice_action": t_request_invoice_action,
    "draft_reply": t_draft_reply,
    "send_document_copy": t_send_document_copy,
    "handoff_to_human": t_handoff_to_human,
}


def execute_tool(ctx: ToolContext, name: str, args: Any) -> Dict[str, Any]:
    """Permission check -> input validation -> run -> audit. Never raises to the caller."""
    ident = ctx.identity
    if name not in TOOL_FUNCS:
        result: Dict[str, Any] = {"error": f"Unknown tool '{name}'."}
    elif name not in allowed_tools(ident):
        result = {"error": "not_permitted", "message": "This sender is not allowed to use that tool."}
    else:
        try:
            clean = validate_args(TOOL_SCHEMAS[name]["input_schema"], args)
            result = TOOL_FUNCS[name](ctx, clean)
        except ToolInputError as exc:
            result = {"error": "invalid_input", "message": str(exc)}
        except Exception as exc:  # keep the conversation alive; details go to logs only
            logger.exception(f"Tool {name} failed")
            ctx.db.rollback()
            result = {"error": "tool_failed", "message": "Something went wrong while looking that up."}

    ctx.db.add(AuditLog(
        user_id=ident.user.id if ident.user else None,
        action=f"AGENT_TOOL_CALL",
        details=json.dumps({"tool": name, "args": args, "caller": ident.address, "role": ident.role,
                            "conversation_id": ctx.conversation.id,
                            "outcome": result.get("error", "ok")}, default=str)[:2000],
    ))
    ctx.db.commit()
    return result
