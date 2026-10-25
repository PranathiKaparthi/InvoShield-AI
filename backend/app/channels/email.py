"""
Email channel.

Inbound, two options:
  1. Webhook: POST /api/agent/webhooks/email with header X-InvoShield-Email-Secret and JSON
     {"from": "...", "subject": "...", "text": "...",
      "attachments": [{"filename": "...", "content_type": "...", "content_base64": "..."}]}
     (works with Mailgun/SendGrid/Postmark inbound routes via a tiny adapter, or Zapier/Make).
  2. IMAP polling: `python -m scripts.email_poller` reads unseen mail from EMAIL_IMAP_*.
Outbound: SMTP (EMAIL_SMTP_*).
"""
import base64
import email
import imaplib
import logging
import smtplib
from email.message import EmailMessage
from email.utils import parseaddr
from typing import Any, Dict, List

from app.channels.base import Channel, ChannelError, InboundMessage, MediaRef, OutboundMessage
from app.core.config import settings

logger = logging.getLogger(__name__)


def parse_webhook(payload: Dict[str, Any]) -> InboundMessage:
    sender_name, sender = parseaddr(str(payload.get("from", "")))
    inbound = InboundMessage(
        channel="email",
        sender=sender,
        sender_name=sender_name or None,
        subject=payload.get("subject"),
        text=str(payload.get("text") or ""),
        external_id=payload.get("message_id"),
    )
    for i, att in enumerate(payload.get("attachments") or []):
        try:
            data = base64.b64decode(att.get("content_base64") or "", validate=True)
        except Exception:
            continue
        inbound.media.append(MediaRef(
            id=f"email-att-{i}",
            mime_type=att.get("content_type") or "application/octet-stream",
            filename=att.get("filename") or f"attachment-{i}",
            data=data,
        ))
    return inbound


def parse_raw_email(raw: bytes) -> InboundMessage:
    msg = email.message_from_bytes(raw)
    sender_name, sender = parseaddr(msg.get("From", ""))
    inbound = InboundMessage(channel="email", sender=sender, sender_name=sender_name or None,
                             subject=msg.get("Subject"), external_id=msg.get("Message-ID"))
    texts: List[str] = []
    for i, part in enumerate(msg.walk()):
        if part.is_multipart():
            continue
        disposition = (part.get("Content-Disposition") or "").lower()
        ctype = part.get_content_type()
        payload = part.get_payload(decode=True) or b""
        if "attachment" in disposition or part.get_filename():
            inbound.media.append(MediaRef(id=f"imap-att-{i}", mime_type=ctype,
                                          filename=part.get_filename() or f"attachment-{i}", data=payload))
        elif ctype == "text/plain":
            texts.append(payload.decode(part.get_content_charset() or "utf-8", errors="ignore"))
    inbound.text = "\n".join(texts).strip()
    return inbound


def fetch_unseen_imap() -> List[InboundMessage]:
    """Fetch and mark-as-seen unread messages from the configured IMAP inbox."""
    if not (settings.EMAIL_IMAP_HOST and settings.EMAIL_IMAP_USER and settings.EMAIL_IMAP_PASSWORD):
        raise ChannelError("IMAP is not configured (EMAIL_IMAP_HOST / EMAIL_IMAP_USER / EMAIL_IMAP_PASSWORD).")
    messages: List[InboundMessage] = []
    with imaplib.IMAP4_SSL(settings.EMAIL_IMAP_HOST) as imap:
        imap.login(settings.EMAIL_IMAP_USER, settings.EMAIL_IMAP_PASSWORD)
        imap.select(settings.EMAIL_IMAP_FOLDER)
        _, ids = imap.search(None, "UNSEEN")
        for num in (ids[0] or b"").split():
            _, data = imap.fetch(num, "(RFC822)")
            if data and data[0]:
                messages.append(parse_raw_email(data[0][1]))
            imap.store(num, "+FLAGS", "\\Seen")
    return messages


class EmailChannel(Channel):
    name = "email"

    @property
    def configured(self) -> bool:
        return bool(settings.EMAIL_SMTP_HOST and settings.EMAIL_FROM_ADDRESS)

    def build_message(self, message: OutboundMessage) -> EmailMessage:
        msg = EmailMessage()
        msg["From"] = settings.EMAIL_FROM_ADDRESS or "no-reply@localhost"
        msg["To"] = message.to
        msg["Subject"] = message.subject or f"{settings.AGENT_BUSINESS_NAME}: invoice update"
        msg.set_content(message.text or "")
        if message.document:
            maintype, _, subtype = (message.document_mime or "application/pdf").partition("/")
            msg.add_attachment(message.document, maintype=maintype, subtype=subtype or "octet-stream",
                               filename=message.document_filename or "invoice.pdf")
        return msg

    def send(self, message: OutboundMessage) -> Dict[str, Any]:
        if not self.configured:
            raise ChannelError("Email is not configured (EMAIL_SMTP_HOST / EMAIL_FROM_ADDRESS).")
        msg = self.build_message(message)
        with smtplib.SMTP(settings.EMAIL_SMTP_HOST, settings.EMAIL_SMTP_PORT, timeout=20) as smtp:
            smtp.starttls()
            if settings.EMAIL_SMTP_USER:
                smtp.login(settings.EMAIL_SMTP_USER, settings.EMAIL_SMTP_PASSWORD or "")
            smtp.send_message(msg)
        return {"id": msg.get("Message-ID"), "mode": "live"}
