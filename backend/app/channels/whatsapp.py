"""
Meta WhatsApp Business Cloud API channel.

Docs: https://developers.facebook.com/docs/whatsapp/cloud-api
  - Webhook verification: GET with hub.mode / hub.verify_token / hub.challenge
  - Webhook signature:    X-Hub-Signature-256 = "sha256=" + HMAC_SHA256(app_secret, raw_body)
  - Send:                 POST /{version}/{phone_number_id}/messages
  - Media download:       GET /{version}/{media_id} -> {url}, then GET url (Bearer token)
"""
import hashlib
import hmac
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx

from app.channels.base import Channel, ChannelError, InboundMessage, MediaRef, OutboundMessage
from app.core.config import settings

logger = logging.getLogger(__name__)

GRAPH_BASE = "https://graph.facebook.com"
MAX_BUTTONS = 3
MAX_BUTTON_TITLE = 20


def verify_signature(raw_body: bytes, signature_header: Optional[str], app_secret: Optional[str]) -> bool:
    """Constant-time check of Meta's X-Hub-Signature-256 header."""
    if not app_secret or not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = hmac.new(app_secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header.split("=", 1)[1].strip())


def parse_webhook(payload: Dict[str, Any]) -> List[InboundMessage]:
    """Convert a WhatsApp webhook payload into normalized inbound messages.
    Status callbacks (sent/delivered/read) carry no messages and are ignored."""
    out: List[InboundMessage] = []
    for entry in payload.get("entry", []) or []:
        for change in entry.get("changes", []) or []:
            value = change.get("value", {}) or {}
            names = {c.get("wa_id"): (c.get("profile") or {}).get("name") for c in value.get("contacts", []) or []}
            for msg in value.get("messages", []) or []:
                sender = msg.get("from", "")
                mtype = msg.get("type")
                inbound = InboundMessage(
                    channel="whatsapp",
                    sender=sender,
                    external_id=msg.get("id"),
                    sender_name=names.get(sender),
                )
                try:
                    inbound.received_at = datetime.fromtimestamp(int(msg.get("timestamp")), tz=timezone.utc)
                except (TypeError, ValueError):
                    pass
                if mtype == "text":
                    inbound.text = (msg.get("text") or {}).get("body", "")
                elif mtype in ("image", "document"):
                    body = msg.get(mtype) or {}
                    mime = body.get("mime_type", "application/octet-stream")
                    default_name = "invoice.pdf" if mime == "application/pdf" else f"invoice.{mime.split('/')[-1]}"
                    inbound.media.append(MediaRef(
                        id=body.get("id", ""), mime_type=mime,
                        filename=body.get("filename") or default_name,
                    ))
                    inbound.text = body.get("caption", "") or ""
                elif mtype == "interactive":
                    inter = msg.get("interactive") or {}
                    reply = inter.get("button_reply") or inter.get("list_reply") or {}
                    inbound.button_payload = reply.get("id")
                    inbound.text = reply.get("title", "")
                elif mtype == "button":  # quick reply on a template
                    btn = msg.get("button") or {}
                    inbound.button_payload = btn.get("payload")
                    inbound.text = btn.get("text", "")
                else:
                    inbound.text = f"[unsupported message type: {mtype}]"
                out.append(inbound)
    return out


class WhatsAppChannel(Channel):
    name = "whatsapp"

    def __init__(self, client: Optional[httpx.Client] = None):
        self.client = client or httpx.Client(timeout=20.0)

    @property
    def configured(self) -> bool:
        return bool(settings.WHATSAPP_PHONE_NUMBER_ID and settings.WHATSAPP_ACCESS_TOKEN)

    def _url(self, path: str) -> str:
        return f"{GRAPH_BASE}/{settings.WHATSAPP_API_VERSION}/{path}"

    def _headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}"}

    def _post_message(self, body: Dict[str, Any]) -> Dict[str, Any]:
        if not self.configured:
            raise ChannelError("WhatsApp is not configured (WHATSAPP_PHONE_NUMBER_ID / WHATSAPP_ACCESS_TOKEN).")
        resp = self.client.post(self._url(f"{settings.WHATSAPP_PHONE_NUMBER_ID}/messages"),
                                json=body, headers=self._headers())
        if resp.status_code >= 400:
            raise ChannelError(f"WhatsApp send failed ({resp.status_code}): {resp.text[:300]}")
        data = resp.json()
        msg_id = (data.get("messages") or [{}])[0].get("id")
        return {"id": msg_id, "mode": "live"}

    @staticmethod
    def _to(number: str) -> str:
        return "".join(ch for ch in number if ch.isdigit())

    def build_payload(self, message: OutboundMessage, media_id: Optional[str] = None) -> Dict[str, Any]:
        base = {"messaging_product": "whatsapp", "recipient_type": "individual", "to": self._to(message.to)}
        if message.template:
            base.update({"type": "template", "template": {
                "name": message.template,
                "language": {"code": settings.WHATSAPP_TEMPLATE_LANGUAGE},
                "components": [{"type": "body", "parameters": [
                    {"type": "text", "text": str(p)} for p in message.template_params
                ]}] if message.template_params else [],
            }})
        elif media_id:
            base.update({"type": "document", "document": {
                "id": media_id, "filename": message.document_filename or "invoice.pdf",
                "caption": (message.text or "")[:1024],
            }})
        elif message.buttons:
            base.update({"type": "interactive", "interactive": {
                "type": "button",
                "body": {"text": message.text[:1024]},
                "action": {"buttons": [
                    {"type": "reply", "reply": {"id": bid[:256], "title": title[:MAX_BUTTON_TITLE]}}
                    for bid, title in message.buttons[:MAX_BUTTONS]
                ]},
            }})
        else:
            base.update({"type": "text", "text": {"preview_url": False, "body": message.text[:4096]}})
        return base

    def _upload_media(self, data: bytes, filename: str, mime: str) -> str:
        resp = self.client.post(
            self._url(f"{settings.WHATSAPP_PHONE_NUMBER_ID}/media"),
            headers=self._headers(),
            data={"messaging_product": "whatsapp", "type": mime},
            files={"file": (filename, data, mime)},
        )
        if resp.status_code >= 400:
            raise ChannelError(f"WhatsApp media upload failed ({resp.status_code}): {resp.text[:300]}")
        return resp.json()["id"]

    def send(self, message: OutboundMessage) -> Dict[str, Any]:
        media_id = None
        if message.document:
            media_id = self._upload_media(message.document, message.document_filename or "invoice.pdf",
                                          message.document_mime or "application/pdf")
        return self._post_message(self.build_payload(message, media_id))

    def download_media(self, media: MediaRef) -> MediaRef:
        if media.data is not None:
            return media
        if not self.configured:
            raise ChannelError("WhatsApp is not configured; cannot download media.")
        meta = self.client.get(self._url(media.id), headers=self._headers())
        if meta.status_code >= 400:
            raise ChannelError(f"WhatsApp media lookup failed ({meta.status_code})")
        info = meta.json()
        max_bytes = settings.AGENT_MAX_MEDIA_MB * 1024 * 1024
        if int(info.get("file_size") or 0) > max_bytes:
            raise ChannelError("Attachment is larger than the allowed size.")
        file_resp = self.client.get(info["url"], headers=self._headers())
        if file_resp.status_code >= 400:
            raise ChannelError(f"WhatsApp media download failed ({file_resp.status_code})")
        media.data = file_resp.content
        media.mime_type = info.get("mime_type") or media.mime_type
        return media
