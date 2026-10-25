"""Channel registry. In AGENT_CHANNEL_MODE=mock every channel is replaced by a recording mock."""
from typing import Dict

from app.channels.base import Channel, ChannelError, InboundMessage, MediaRef, OutboundMessage
from app.channels.mock import MockChannel
from app.core.config import settings

_live_cache: Dict[str, Channel] = {}


def is_mock_mode() -> bool:
    return (settings.AGENT_CHANNEL_MODE or "mock").lower() != "live"


def get_channel(name: str) -> Channel:
    if is_mock_mode() or name == "mock":
        return MockChannel(name)
    if name not in _live_cache:
        if name == "whatsapp":
            from app.channels.whatsapp import WhatsAppChannel
            _live_cache[name] = WhatsAppChannel()
        elif name == "email":
            from app.channels.email import EmailChannel
            _live_cache[name] = EmailChannel()
        else:
            raise ChannelError(f"Unknown channel '{name}'")
    return _live_cache[name]


__all__ = ["Channel", "ChannelError", "InboundMessage", "MediaRef", "OutboundMessage",
           "get_channel", "is_mock_mode"]
