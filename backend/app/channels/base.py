"""Channel-agnostic message types and the Channel interface."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class MediaRef:
    """An attachment. `data` is filled once downloaded (WhatsApp) or immediately (email/mock)."""
    id: str
    mime_type: str
    filename: str
    data: Optional[bytes] = None

    @property
    def size(self) -> int:
        return len(self.data or b"")


@dataclass
class InboundMessage:
    channel: str            # whatsapp | email | mock
    sender: str             # raw phone number or email address
    text: str = ""
    media: List[MediaRef] = field(default_factory=list)
    button_payload: Optional[str] = None
    external_id: Optional[str] = None
    sender_name: Optional[str] = None
    subject: Optional[str] = None
    received_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    # Newsletters, "no-reply" senders, bounces and auto-replies: never answered (see email.is_automated).
    automated: bool = False


@dataclass
class OutboundMessage:
    to: str
    text: str = ""
    buttons: List[Tuple[str, str]] = field(default_factory=list)   # (id, title)
    template: Optional[str] = None
    template_params: List[str] = field(default_factory=list)
    document: Optional[bytes] = None
    document_filename: Optional[str] = None
    document_mime: Optional[str] = None
    subject: Optional[str] = None


class ChannelError(Exception):
    pass


class Channel(ABC):
    name: str = "base"

    @abstractmethod
    def send(self, message: OutboundMessage) -> Dict[str, Any]:
        """Deliver a message. Returns provider details (e.g. message id)."""

    def download_media(self, media: MediaRef) -> MediaRef:
        """Fill media.data. Channels that receive bytes inline can return media unchanged."""
        return media

    @property
    def configured(self) -> bool:
        return True
