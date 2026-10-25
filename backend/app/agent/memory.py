"""Conversation storage and short-term history for the agent."""
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.agent.identity import Identity
from app.agent.policies import wrap_untrusted
from app.models.agent_entities import AgentContact, AgentConversation, AgentMessage, AgentSettings
from app.core.config import settings


def utcnow_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def get_agent_settings(db: Session, organization: str) -> AgentSettings:
    row = db.query(AgentSettings).filter(AgentSettings.organization == organization).first()
    if row is None:
        row = AgentSettings(organization=organization, business_name=settings.AGENT_BUSINESS_NAME,
                            default_language="auto", auto_reply=True, notify_vendors=True,
                            allow_new_contacts=True)
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


def get_or_create_conversation(db: Session, identity: Identity) -> AgentConversation:
    conv = db.query(AgentConversation).filter(
        AgentConversation.channel == identity.channel,
        AgentConversation.sender_address == identity.address,
    ).order_by(AgentConversation.id.desc()).first()
    if conv is None:
        conv = AgentConversation(channel=identity.channel, sender_address=identity.address,
                                 organization=identity.organization, contact_id=identity.contact_id)
        db.add(conv)
        db.commit()
        db.refresh(conv)
    elif conv.contact_id != identity.contact_id or conv.organization != identity.organization:
        conv.contact_id = identity.contact_id
        conv.organization = identity.organization
        db.commit()
    return conv


def conversation_for_contact(db: Session, contact: AgentContact) -> Optional[AgentConversation]:
    """Most recent conversation with a contact, or a new one on their preferred address."""
    conv = db.query(AgentConversation).filter(AgentConversation.contact_id == contact.id) \
        .order_by(AgentConversation.last_message_at.desc(), AgentConversation.id.desc()).first()
    if conv:
        return conv
    if contact.phone_e164:
        channel, address = "whatsapp", contact.phone_e164
    elif contact.email:
        channel, address = "email", contact.email.lower()
    else:
        return None
    conv = AgentConversation(channel=channel, sender_address=address,
                             organization=contact.organization, contact_id=contact.id)
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv


def record_message(db: Session, conv: AgentConversation, direction: str, content: str,
                   media: Optional[List[Dict[str, Any]]] = None,
                   tool_calls: Optional[List[Dict[str, Any]]] = None,
                   status: str = "sent") -> AgentMessage:
    msg = AgentMessage(
        conversation_id=conv.id, direction=direction, content=content, status=status,
        media_json=json.dumps(media) if media else None,
        tool_calls_json=json.dumps(tool_calls, default=str) if tool_calls else None,
    )
    now = utcnow_naive()
    conv.last_message_at = now
    if direction == "inbound":
        conv.last_inbound_at = now
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg


def build_history(db: Session, conv: AgentConversation, exclude_message_id: Optional[int],
                  turns: Optional[int] = None) -> List[Dict[str, Any]]:
    """Last N text turns as Anthropic-style messages (user/assistant alternating, starting with user)."""
    turns = turns or settings.AGENT_HISTORY_TURNS
    q = db.query(AgentMessage).filter(AgentMessage.conversation_id == conv.id)
    if exclude_message_id:
        q = q.filter(AgentMessage.id != exclude_message_id)
    rows = list(reversed(q.order_by(AgentMessage.id.desc()).limit(turns).all()))

    out: List[Dict[str, Any]] = []
    for m in rows:
        if m.direction == "inbound":
            role, text = "user", wrap_untrusted(m.content or "", f"{conv.channel} message (earlier)")
        else:
            if m.status in ("failed", "held", "deferred"):
                continue
            role, text = "assistant", m.content or ""
        if not text:
            continue
        if out and out[-1]["role"] == role:
            out[-1]["content"] += "\n\n" + text
        else:
            out.append({"role": role, "content": text})
    while out and out[0]["role"] != "user":
        out.pop(0)
    return out
