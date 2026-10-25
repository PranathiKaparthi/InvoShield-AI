"""
InvoShield Assistant API.

Webhooks (public, signature/secret protected):
  GET  /api/agent/webhooks/whatsapp   Meta verification handshake
  POST /api/agent/webhooks/whatsapp   inbound WhatsApp messages (X-Hub-Signature-256 required)
  POST /api/agent/webhooks/email      inbound email (X-InvoShield-Email-Secret required)

Assistant Inbox (admin / reviewer, scoped to their organization):
  conversations, messages, approval queue, contacts, settings, test console (simulate).
"""
import hmac
import json
import logging
from typing import Any, Dict, List, Optional

from fastapi import (APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, Request,
                     Response, UploadFile)
from pydantic import BaseModel, Field
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.agent import approval as approval_svc
from app.agent.core import handle_inbound
from app.agent.identity import normalize_email, normalize_phone
from app.agent.llm import provider_status
from app.agent.memory import get_agent_settings
from app.api.deps import require_role
from app.channels import InboundMessage, MediaRef, get_channel, is_mock_mode
from app.channels import email as email_channel
from app.channels import whatsapp as whatsapp_channel
from app.channels.mock import MOCK_OUTBOX
from app.channels.templates import TEMPLATES
from app.core.config import settings
from app.database.session import SessionLocal, get_db
from app.models.agent_entities import AgentApproval, AgentContact, AgentConversation, AgentMessage
from app.models.entities import AuditLog, User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/agent", tags=["InvoShield Assistant"])
staff = require_role(["admin", "reviewer"])


def _org(user: User) -> str:
    return user.organization or "General"


def _process_in_background(inbound: InboundMessage) -> None:
    db = SessionLocal()
    try:
        handle_inbound(db, inbound)
    except Exception:
        logger.exception("Failed to process inbound message")
    finally:
        db.close()


# ============================================================== WhatsApp webhook
@router.get("/webhooks/whatsapp")
def whatsapp_verify(
    hub_mode: Optional[str] = Query(None, alias="hub.mode"),
    hub_verify_token: Optional[str] = Query(None, alias="hub.verify_token"),
    hub_challenge: Optional[str] = Query(None, alias="hub.challenge"),
):
    expected = settings.WHATSAPP_VERIFY_TOKEN
    if hub_mode == "subscribe" and expected and hub_verify_token and \
            hmac.compare_digest(hub_verify_token, expected):
        return Response(content=hub_challenge or "", media_type="text/plain")
    raise HTTPException(status_code=403, detail="Verification failed.")


@router.post("/webhooks/whatsapp")
async def whatsapp_webhook(request: Request, background: BackgroundTasks):
    raw = await request.body()
    if not settings.WHATSAPP_APP_SECRET:
        raise HTTPException(status_code=503, detail="WhatsApp webhook is not configured (WHATSAPP_APP_SECRET).")
    if not whatsapp_channel.verify_signature(raw, request.headers.get("X-Hub-Signature-256"),
                                             settings.WHATSAPP_APP_SECRET):
        raise HTTPException(status_code=401, detail="Invalid or missing signature.")
    try:
        payload = json.loads(raw or b"{}")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid JSON.")
    messages = whatsapp_channel.parse_webhook(payload)
    for inbound in messages:
        background.add_task(_process_in_background, inbound)
    return {"received": len(messages)}


# ============================================================== Email webhook
class EmailAttachment(BaseModel):
    filename: str
    content_type: str = "application/octet-stream"
    content_base64: str


class EmailWebhook(BaseModel):
    from_: str = Field(alias="from")
    subject: Optional[str] = None
    text: Optional[str] = ""
    message_id: Optional[str] = None
    attachments: List[EmailAttachment] = []
    headers: Dict[str, str] = {}  # optional: original mail headers, used to skip automated mail


@router.post("/webhooks/email")
def email_webhook(body: EmailWebhook, request: Request, background: BackgroundTasks):
    secret = settings.EMAIL_WEBHOOK_SECRET
    provided = request.headers.get("X-InvoShield-Email-Secret") or ""
    if not secret:
        raise HTTPException(status_code=503, detail="Email webhook is not configured (EMAIL_WEBHOOK_SECRET).")
    if not hmac.compare_digest(provided, secret):
        raise HTTPException(status_code=401, detail="Invalid secret.")
    inbound = email_channel.parse_webhook(body.model_dump(by_alias=True))
    background.add_task(_process_in_background, inbound)
    return {"received": 1}


# ============================================================== Test console (simulate)
@router.post("/simulate")
async def simulate_message(
    sender: str = Form(...),
    text: str = Form(""),
    channel: str = Form("whatsapp"),
    button_payload: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    current_user: User = Depends(staff),
    db: Session = Depends(get_db),
):
    """Send a message to the assistant as if it came from `sender` (mock mode only)."""
    if not is_mock_mode():
        raise HTTPException(status_code=403, detail="The test console is only available when AGENT_CHANNEL_MODE=mock.")
    if channel not in ("whatsapp", "email"):
        raise HTTPException(status_code=400, detail="channel must be whatsapp or email.")
    inbound = InboundMessage(channel=channel, sender=sender, text=text, button_payload=button_payload or None)
    if file is not None and file.filename:
        data = await file.read()
        inbound.media.append(MediaRef(id="console-upload", mime_type=file.content_type or "application/octet-stream",
                                      filename=file.filename, data=data))
    before = len(MOCK_OUTBOX)
    result = handle_inbound(db, inbound)
    db.add(AuditLog(user_id=current_user.id, action="AGENT_SIMULATED_MESSAGE",
                    details=f"Test console message as {sender} via {channel}"))
    db.commit()
    return {"conversation_id": result.conversation_id, "status": result.status,
            "replies": result.replies, "tool_calls": result.tool_calls,
            "outbox": MOCK_OUTBOX[before:]}


# ============================================================== Conversations
def _contact_dict(c: Optional[AgentContact]) -> Optional[Dict[str, Any]]:
    if c is None:
        return None
    return {"id": c.id, "display_name": c.display_name, "kind": c.kind, "vendor_name": c.vendor_name,
            "user_id": c.user_id, "user_email": c.user.email if c.user else None,
            "user_role": c.user.role if c.user else None,
            "phone_e164": c.phone_e164, "email": c.email, "verified": c.verified,
            "preferred_language": c.preferred_language, "notes": c.notes,
            "self_registered": bool(c.self_registered), "onboarding_step": c.onboarding_step,
            "created_at": c.created_at}


@router.get("/conversations")
def list_conversations(current_user: User = Depends(staff), db: Session = Depends(get_db)):
    convs = db.query(AgentConversation).filter(AgentConversation.organization == _org(current_user)) \
        .order_by(desc(AgentConversation.last_message_at)).limit(100).all()
    out = []
    for c in convs:
        last = db.query(AgentMessage).filter(AgentMessage.conversation_id == c.id) \
            .order_by(AgentMessage.id.desc()).first()
        out.append({"id": c.id, "channel": c.channel, "sender_address": c.sender_address,
                    "contact": _contact_dict(c.contact), "last_message_at": c.last_message_at,
                    "last_inbound_at": c.last_inbound_at,
                    "last_message": (last.content or "")[:140] if last else "",
                    "last_direction": last.direction if last else None})
    return out


@router.get("/conversations/{conversation_id}/messages")
def conversation_messages(conversation_id: int, current_user: User = Depends(staff), db: Session = Depends(get_db)):
    conv = db.query(AgentConversation).filter(AgentConversation.id == conversation_id,
                                              AgentConversation.organization == _org(current_user)).first()
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return {"conversation": {"id": conv.id, "channel": conv.channel, "sender_address": conv.sender_address,
                             "contact": _contact_dict(conv.contact)},
            "messages": [{"id": m.id, "direction": m.direction, "content": m.content, "status": m.status,
                          "media": json.loads(m.media_json) if m.media_json else [],
                          "tool_calls": json.loads(m.tool_calls_json) if m.tool_calls_json else [],
                          "created_at": m.created_at} for m in conv.messages]}


# ============================================================== Approvals
def _approval_dict(a: AgentApproval) -> Dict[str, Any]:
    payload = json.loads(a.payload_json or "{}")
    return {"id": a.id, "type": a.type, "status": a.status, "summary": a.summary, "payload": payload,
            "conversation_id": a.conversation_id, "requested_by": _contact_dict(a.requested_by),
            "decided_by": a.decided_by, "decided_at": a.decided_at, "expires_at": a.expires_at,
            "created_at": a.created_at}


@router.get("/approvals")
def list_approvals(status: str = "pending", current_user: User = Depends(staff), db: Session = Depends(get_db)):
    q = db.query(AgentApproval).filter(AgentApproval.organization == _org(current_user))
    if status != "all":
        q = q.filter(AgentApproval.status == status)
    return [_approval_dict(a) for a in q.order_by(desc(AgentApproval.created_at)).limit(200).all()]


class ApprovalDecision(BaseModel):
    text: Optional[str] = Field(None, max_length=4000)


def _get_approval(db: Session, approval_id: int, user: User) -> AgentApproval:
    item = db.query(AgentApproval).filter(AgentApproval.id == approval_id,
                                          AgentApproval.organization == _org(user)).first()
    if item is None:
        raise HTTPException(status_code=404, detail="Approval item not found.")
    return item


@router.post("/approvals/{approval_id}/approve")
def approve_item(approval_id: int, body: ApprovalDecision = ApprovalDecision(),
                 current_user: User = Depends(staff), db: Session = Depends(get_db)):
    item = _get_approval(db, approval_id, current_user)
    try:
        approval_svc.decide(db, item, current_user, approve=True, edited_text=body.text)
    except approval_svc.ApprovalError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    return _approval_dict(item)


@router.post("/approvals/{approval_id}/reject")
def reject_item(approval_id: int, current_user: User = Depends(staff), db: Session = Depends(get_db)):
    item = _get_approval(db, approval_id, current_user)
    try:
        approval_svc.decide(db, item, current_user, approve=False)
    except approval_svc.ApprovalError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    return _approval_dict(item)


# ============================================================== Contacts
class ContactIn(BaseModel):
    display_name: str = Field(..., min_length=1, max_length=255)
    kind: str = Field("vendor", pattern="^(vendor|staff)$")
    vendor_name: Optional[str] = Field(None, max_length=255)
    user_email: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    verified: bool = True
    preferred_language: str = Field("auto", pattern="^(auto|en|ta|te|hi)$")
    notes: Optional[str] = Field(None, max_length=1000)


def _apply_contact(db: Session, contact: AgentContact, body: ContactIn, user: User) -> None:
    phone = normalize_phone(body.phone) if body.phone else None
    email = normalize_email(body.email) if body.email else None
    if body.phone and not phone:
        raise HTTPException(status_code=400, detail="Invalid phone number.")
    if body.email and not email:
        raise HTTPException(status_code=400, detail="Invalid email address.")
    if not phone and not email:
        raise HTTPException(status_code=400, detail="A phone number or email is required.")
    for field_name, value in (("phone_e164", phone), ("email", email)):
        if value:
            clash = db.query(AgentContact).filter(getattr(AgentContact, field_name) == value,
                                                  AgentContact.id != (contact.id or -1),
                                                  AgentContact.verified.is_(True)).first()
            if clash and body.verified:
                raise HTTPException(status_code=409,
                                    detail=f"{value} already belongs to verified contact '{clash.display_name}'.")
    linked_user = None
    if body.kind == "staff":
        if not body.user_email:
            raise HTTPException(status_code=400, detail="Staff contacts must be linked to a user account (user_email).")
        linked_user = db.query(User).filter(func.lower(User.email) == body.user_email.strip().lower()).first()
        if linked_user is None:
            raise HTTPException(status_code=404, detail="No user with that email.")
        if user.role != "admin" and linked_user.organization != user.organization:
            raise HTTPException(status_code=403, detail="That user belongs to another organization.")
    elif not body.vendor_name:
        raise HTTPException(status_code=400, detail="Vendor contacts need the vendor name as it appears on invoices.")

    contact.organization = _org(user)
    contact.display_name = body.display_name.strip()
    contact.kind = body.kind
    contact.vendor_name = body.vendor_name.strip() if body.vendor_name and body.kind == "vendor" else None
    contact.user_id = linked_user.id if linked_user else None
    contact.phone_e164 = phone
    contact.email = email
    contact.verified = body.verified
    contact.preferred_language = body.preferred_language
    contact.notes = body.notes


@router.get("/contacts")
def list_contacts(current_user: User = Depends(staff), db: Session = Depends(get_db)):
    rows = db.query(AgentContact).filter(AgentContact.organization == _org(current_user)) \
        .order_by(AgentContact.verified.desc(), AgentContact.display_name).all()
    return [_contact_dict(c) for c in rows]


@router.post("/contacts", status_code=201)
def create_contact(body: ContactIn, current_user: User = Depends(staff), db: Session = Depends(get_db)):
    contact = AgentContact()
    _apply_contact(db, contact, body, current_user)
    db.add(contact)
    db.add(AuditLog(user_id=current_user.id, action="AGENT_CONTACT_CREATED",
                    details=f"Contact '{contact.display_name}' ({contact.kind}) created by {current_user.email}"))
    db.commit()
    db.refresh(contact)
    return _contact_dict(contact)


@router.put("/contacts/{contact_id}")
def update_contact(contact_id: int, body: ContactIn, current_user: User = Depends(staff), db: Session = Depends(get_db)):
    contact = db.query(AgentContact).filter(AgentContact.id == contact_id,
                                            AgentContact.organization == _org(current_user)).first()
    if contact is None:
        raise HTTPException(status_code=404, detail="Contact not found.")
    _apply_contact(db, contact, body, current_user)
    db.add(AuditLog(user_id=current_user.id, action="AGENT_CONTACT_UPDATED",
                    details=f"Contact #{contact.id} '{contact.display_name}' updated by {current_user.email} "
                            f"(verified={contact.verified})"))
    db.commit()
    db.refresh(contact)
    return _contact_dict(contact)


@router.delete("/contacts/{contact_id}", status_code=204)
def delete_contact(contact_id: int, current_user: User = Depends(staff), db: Session = Depends(get_db)):
    contact = db.query(AgentContact).filter(AgentContact.id == contact_id,
                                            AgentContact.organization == _org(current_user)).first()
    if contact is None:
        raise HTTPException(status_code=404, detail="Contact not found.")
    # Keep history intact: unverify instead of hard delete when the contact has conversations.
    has_history = db.query(AgentConversation).filter(AgentConversation.contact_id == contact.id).first()
    if has_history:
        contact.verified = False
        contact.self_registered = False
        contact.onboarding_step = "blocked"  # removed by the owner: no automatic re-onboarding
        contact.notes = (contact.notes or "") + "\n[Removed by owner]"
    else:
        db.delete(contact)
    db.add(AuditLog(user_id=current_user.id, action="AGENT_CONTACT_REMOVED",
                    details=f"Contact #{contact_id} removed by {current_user.email}"))
    db.commit()
    return Response(status_code=204)


# ============================================================== Settings
class SettingsIn(BaseModel):
    business_name: str = Field(..., min_length=1, max_length=255)
    default_language: str = Field("auto", pattern="^(auto|en|ta|te|hi)$")
    auto_reply: bool = True
    notify_vendors: bool = True
    allow_new_contacts: bool = True


def _settings_dict(db: Session, org: str) -> Dict[str, Any]:
    s = get_agent_settings(db, org)
    wa = get_channel("whatsapp") if not is_mock_mode() else None
    em = get_channel("email") if not is_mock_mode() else None
    return {
        "organization": org,
        "business_name": s.business_name,
        "default_language": s.default_language,
        "auto_reply": s.auto_reply,
        "notify_vendors": s.notify_vendors,
        "allow_new_contacts": s.allow_new_contacts if s.allow_new_contacts is not None else True,
        "channel_mode": "mock" if is_mock_mode() else "live",
        "llm": provider_status(),
        "whatsapp": {"configured": bool(wa and wa.configured),
                     "webhook_secret_set": bool(settings.WHATSAPP_APP_SECRET),
                     "verify_token_set": bool(settings.WHATSAPP_VERIFY_TOKEN),
                     "webhook_path": "/api/agent/webhooks/whatsapp"},
        "email": {"configured": bool(em and em.configured),
                  "webhook_secret_set": bool(settings.EMAIL_WEBHOOK_SECRET),
                  "imap_configured": bool(settings.EMAIL_IMAP_HOST),
                  "webhook_path": "/api/agent/webhooks/email"},
        "templates": {name: t["body"] for name, t in TEMPLATES.items()},
    }


@router.get("/settings")
def read_settings(current_user: User = Depends(staff), db: Session = Depends(get_db)):
    return _settings_dict(db, _org(current_user))


@router.put("/settings")
def write_settings(body: SettingsIn, current_user: User = Depends(staff), db: Session = Depends(get_db)):
    s = get_agent_settings(db, _org(current_user))
    s.business_name = body.business_name.strip()
    s.default_language = body.default_language
    s.auto_reply = body.auto_reply
    s.notify_vendors = body.notify_vendors
    s.allow_new_contacts = body.allow_new_contacts
    db.add(AuditLog(user_id=current_user.id, action="AGENT_SETTINGS_UPDATED",
                    details=json.dumps(body.model_dump())))
    db.commit()
    return _settings_dict(db, _org(current_user))
