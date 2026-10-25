"""Mock channel: records outbound messages in memory so everything is testable without Meta/SMTP."""
import uuid
from typing import Any, Dict, List

from app.channels.base import Channel, ChannelError, MediaRef, OutboundMessage

# Shared across mock channel instances so tests and the demo script can inspect what was "sent".
MOCK_OUTBOX: List[Dict[str, Any]] = []
# media_id -> (bytes, mime, filename); lets tests simulate WhatsApp media downloads.
MOCK_MEDIA: Dict[str, tuple] = {}


class MockChannel(Channel):
    def __init__(self, name: str = "mock"):
        self.name = name

    def send(self, message: OutboundMessage) -> Dict[str, Any]:
        record = {
            "id": f"mock-{uuid.uuid4().hex[:10]}",
            "channel": self.name,
            "to": message.to,
            "text": message.text,
            "buttons": list(message.buttons),
            "template": message.template,
            "template_params": list(message.template_params),
            "document_filename": message.document_filename,
            "subject": message.subject,
        }
        MOCK_OUTBOX.append(record)
        return {"id": record["id"], "mode": "mock"}

    def download_media(self, media: MediaRef) -> MediaRef:
        if media.data is not None:
            return media
        if media.id in MOCK_MEDIA:
            data, mime, filename = MOCK_MEDIA[media.id]
            media.data = data
            media.mime_type = media.mime_type or mime
            media.filename = media.filename or filename
            return media
        raise ChannelError(f"Mock media '{media.id}' not found")


def clear_mock_outbox():
    MOCK_OUTBOX.clear()
