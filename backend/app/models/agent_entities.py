"""Database models for the InvoShield Assistant (conversational agent)."""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship

from app.database.session import Base
from app.models.entities import utc_now


class AgentContact(Base):
    """
    A person the assistant may talk to, identified by WhatsApp number and/or email.
      kind="vendor": an external supplier; can only see invoices for `vendor_name` (or ones they sent).
      kind="staff":  an internal user; permissions come from the linked `user` (admin / reviewer / user).
    Contacts are created by the business owner (or auto-created as unverified when an unknown
    number writes in).
    """
    __tablename__ = "agent_contacts"

    id = Column(Integer, primary_key=True, index=True)
    organization = Column(String(120), default="General", index=True, nullable=False)
    display_name = Column(String(255), nullable=False)
    kind = Column(String(20), default="vendor", nullable=False)  # vendor | staff
    vendor_name = Column(String(255), nullable=True)  # matches Invoice.vendor_name for vendors
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # for staff
    phone_e164 = Column(String(20), index=True, nullable=True)  # e.g. +919876543210
    email = Column(String(255), index=True, nullable=True)
    verified = Column(Boolean, default=False, nullable=False)
    preferred_language = Column(String(10), default="auto")  # auto | en | ta | te | hi
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now)

    user = relationship("User")


class AgentConversation(Base):
    __tablename__ = "agent_conversations"

    id = Column(Integer, primary_key=True, index=True)
    organization = Column(String(120), default="General", index=True, nullable=False)
    channel = Column(String(20), nullable=False)  # whatsapp | email | mock
    sender_address = Column(String(255), index=True, nullable=False)  # phone (E.164) or email
    contact_id = Column(Integer, ForeignKey("agent_contacts.id"), nullable=True)
    started_at = Column(DateTime, default=utc_now)
    last_inbound_at = Column(DateTime, nullable=True)
    last_message_at = Column(DateTime, default=utc_now)

    contact = relationship("AgentContact")
    messages = relationship("AgentMessage", back_populates="conversation",
                            cascade="all, delete-orphan", order_by="AgentMessage.id")


class AgentMessage(Base):
    __tablename__ = "agent_messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("agent_conversations.id"), nullable=False, index=True)
    direction = Column(String(10), nullable=False)  # inbound | outbound
    content = Column(Text, nullable=True)
    media_json = Column(Text, nullable=True)
    tool_calls_json = Column(Text, nullable=True)
    status = Column(String(20), default="sent")  # received | sent | held | deferred | failed
    created_at = Column(DateTime, default=utc_now)

    conversation = relationship("AgentConversation", back_populates="messages")


class AgentApproval(Base):
    """
    Anything the assistant may not do on its own.
      invoice_action  : approve / reject / mark_paid requested in chat; waits for the requester's YES.
      outbound_message: a reply drafted for someone else; waits for owner approval in the Inbox.
      document_copy   : sending an invoice file; waits for owner approval.
      held_reply      : auto-reply is off, so every vendor reply waits for owner approval.
      handoff         : a conversation the assistant passed to a human.
    """
    __tablename__ = "agent_approvals"

    id = Column(Integer, primary_key=True, index=True)
    organization = Column(String(120), default="General", index=True, nullable=False)
    type = Column(String(30), nullable=False)
    status = Column(String(30), default="pending", index=True)
    summary = Column(Text, nullable=True)
    payload_json = Column(Text, nullable=True)
    conversation_id = Column(Integer, ForeignKey("agent_conversations.id"), nullable=True)
    requested_by_contact_id = Column(Integer, ForeignKey("agent_contacts.id"), nullable=True)
    created_by_agent = Column(Boolean, default=True)
    decided_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    decided_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utc_now)

    conversation = relationship("AgentConversation")
    requested_by = relationship("AgentContact")


class AgentSettings(Base):
    __tablename__ = "agent_settings"

    id = Column(Integer, primary_key=True, index=True)
    organization = Column(String(120), unique=True, nullable=False)
    business_name = Column(String(255), nullable=True)
    default_language = Column(String(10), default="auto")
    auto_reply = Column(Boolean, default=True)
    notify_vendors = Column(Boolean, default=True)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)
