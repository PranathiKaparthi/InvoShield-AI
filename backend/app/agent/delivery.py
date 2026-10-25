"""
Every outbound message goes through deliver(): redaction, WhatsApp 24-hour window handling,
channel send, conversation log and audit log.
"""
import json
import logging
from datetime import timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app.agent.memory import get_agent_settings, record_message, utcnow_naive
from app.agent.policies import redact
from app.channels import ChannelError, OutboundMessage, get_channel
from app.channels.templates import render
from app.models.agent_entities import AgentConversation, AgentMessage
from app.models.entities import AuditLog

logger = logging.getLogger(__name__)

WHATSAPP_WINDOW = timedelta(hours=24)


def within_whatsapp_window(conv: AgentConversation) -> bool:
    if conv.channel != "whatsapp":
        return True
    if not conv.last_inbound_at:
        return False
    return utcnow_naive() - conv.last_inbound_at <= WHATSAPP_WINDOW


def _audit(db: Session, conv: AgentConversation, text: str, status: str, actor_user_id: Optional[int],
           invoice_id: Optional[int] = None) -> None:
    db.add(AuditLog(
        user_id=actor_user_id,
        invoice_id=invoice_id,
        action="AGENT_MESSAGE_SENT" if status == "sent" else f"AGENT_MESSAGE_{status.upper()}",
        details=json.dumps({"conversation_id": conv.id, "channel": conv.channel,
                            "to": conv.sender_address, "status": status, "text": text[:500]}),
    ))
    db.commit()


def deliver(db: Session, conv: AgentConversation, out: OutboundMessage,
            actor_user_id: Optional[int] = None, tool_calls=None,
            invoice_id: Optional[int] = None) -> AgentMessage:
    """Redact, send (or defer outside the WhatsApp window), and record an outbound message."""
    out.to = conv.sender_address
    out.text = redact(out.text or "")
    out.template_params = [redact(str(p)) for p in out.template_params]
    log_text = render(out.template, out.template_params) if out.template else out.text

    channel = get_channel(conv.channel)

    # WhatsApp: free-form messages only inside 24h of the customer's last message.
    if not out.template and not within_whatsapp_window(conv):
        msg = record_message(db, conv, "outbound", log_text, tool_calls=tool_calls, status="deferred")
        org_settings = get_agent_settings(db, conv.organization)
        name = conv.contact.display_name if conv.contact else "there"
        nudge = OutboundMessage(to=conv.sender_address, template="team_follow_up",
                                template_params=[name, org_settings.business_name or "We"])
        try:
            channel.send(nudge)
            record_message(db, conv, "outbound", render(nudge.template, nudge.template_params))
        except ChannelError as exc:
            logger.warning(f"Template nudge failed for conversation {conv.id}: {exc}")
        _audit(db, conv, log_text, "deferred", actor_user_id, invoice_id)
        return msg

    status = "sent"
    try:
        channel.send(out)
    except ChannelError as exc:
        logger.error(f"Delivery failed for conversation {conv.id}: {exc}")
        status = "failed"
    msg = record_message(db, conv, "outbound", log_text, tool_calls=tool_calls, status=status)
    _audit(db, conv, log_text, status, actor_user_id, invoice_id)
    return msg


def flush_deferred(db: Session, conv: AgentConversation) -> int:
    """After the customer writes again (window re-opened), send messages that were deferred."""
    pending = db.query(AgentMessage).filter(AgentMessage.conversation_id == conv.id,
                                            AgentMessage.status == "deferred") \
        .order_by(AgentMessage.id).all()
    channel = get_channel(conv.channel)
    sent = 0
    for m in pending:
        try:
            channel.send(OutboundMessage(to=conv.sender_address, text=m.content or ""))
            m.status = "sent"
            sent += 1
        except ChannelError as exc:
            logger.warning(f"Deferred delivery failed for message {m.id}: {exc}")
            m.status = "failed"
        db.commit()
    return sent
