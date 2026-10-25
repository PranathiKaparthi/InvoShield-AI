"""
InvoShield Assistant: the agent loop.

handle_inbound(db, inbound) is the single entry point for every channel:
  rate limit -> identity -> conversation log -> deferred flush -> attachment checks
  -> unknown-sender handling -> deterministic YES/NO confirmations -> LLM tool loop
  -> held-reply (auto-reply off) or delivery (redaction, 24h window, audit).
"""
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.agent import approval, menu, onboarding
from app.agent.delivery import deliver, flush_deferred
from app.agent.identity import resolve_identity
from app.agent.llm import OfflineProvider, get_provider
from app.agent.memory import build_history, get_agent_settings, get_or_create_conversation, record_message
from app.agent.policies import rate_limiter, wrap_untrusted
from app.agent.prompts import build_system_prompt
from app.agent.tools import ToolContext, execute_tool, tool_definitions
from app.channels import ChannelError, InboundMessage, MediaRef, OutboundMessage, get_channel, is_mock_mode
from app.core.config import settings
from app.models.agent_entities import AgentApproval, AgentConversation, AgentMessage
from app.services.invoice_pipeline import process_invoice_upload

logger = logging.getLogger(__name__)

ALLOWED_MIME = {"application/pdf", "image/jpeg", "image/jpg", "image/png", "image/webp", "image/tiff"}
MOCK_EXTRA_MIME = {"text/plain"}  # sample .txt invoices in mock/demo mode only
EXT_FOR_MIME = {"application/pdf": ".pdf", "image/jpeg": ".jpg", "image/jpg": ".jpg", "image/png": ".png",
                "image/webp": ".webp", "image/tiff": ".tiff", "text/plain": ".txt"}

UNKNOWN_TEXT_REPLY = ("Hello! This number isn't registered with {business} yet, so I can't share invoice "
                      "details. Our team will get back to you. You can also send your invoice here as a "
                      "PDF or photo.")
UNKNOWN_MEDIA_REPLY = ("Thank you, we received your document. Our team will verify your details and get "
                       "back to you.")
RATE_LIMIT_REPLY = "You're sending messages very quickly. Please wait a minute and try again."
FALLBACK_REPLY = "Sorry, I couldn't complete that right now. I've passed this to the team."


@dataclass
class HandleResult:
    conversation_id: Optional[int] = None
    replies: List[str] = field(default_factory=list)
    status: str = "ok"            # ok | rate_limited | held | unknown_sender | ignored
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)


def _allowed_mime() -> set:
    return ALLOWED_MIME | (MOCK_EXTRA_MIME if is_mock_mode() else set())


def _prepare_attachments(inbound: InboundMessage) -> (Dict[str, MediaRef], List[str]):
    """Download and check every attachment. Returns (valid attachments by id, problems)."""
    channel = get_channel(inbound.channel)
    max_bytes = settings.AGENT_MAX_MEDIA_MB * 1024 * 1024
    valid: Dict[str, MediaRef] = {}
    problems: List[str] = []
    for i, media in enumerate(inbound.media[:5]):
        mime = (media.mime_type or "").split(";")[0].strip().lower()
        if mime not in _allowed_mime():
            problems.append(f"{media.filename or 'attachment'}: only PDF or photo (JPG/PNG) invoices are accepted")
            continue
        try:
            media = channel.download_media(media)
        except ChannelError as exc:
            logger.warning(f"Media download failed: {exc}")
            problems.append(f"{media.filename or 'attachment'}: could not be downloaded, please send it again")
            continue
        if media.size == 0:
            problems.append(f"{media.filename or 'attachment'}: the file is empty")
            continue
        if media.size > max_bytes:
            problems.append(f"{media.filename or 'attachment'}: larger than {settings.AGENT_MAX_MEDIA_MB} MB")
            continue
        if not media.filename or "." not in media.filename:
            media.filename = f"invoice{EXT_FOR_MIME.get(mime, '')}"
        media.mime_type = mime
        valid[f"att-{i + 1}"] = media
    if len(inbound.media) > 5:
        problems.append("only the first 5 attachments were processed")
    return valid, problems


def _reply(db: Session, conv: AgentConversation, text: str, result: HandleResult,
           buttons=None, tool_calls=None) -> None:
    deliver(db, conv, OutboundMessage(to=conv.sender_address, text=text, buttons=buttons or []),
            tool_calls=tool_calls)
    result.replies.append(text)


def _menu_shown_recently(db: Session, conv: AgentConversation, current_inbound_id: int,
                         lookback: int = 6) -> bool:
    """A bare number counts as a menu choice if the menu was among the last few replies, so
    "1" still works after, say, an invoice receipt."""
    recent = db.query(AgentMessage).filter(AgentMessage.conversation_id == conv.id,
                                           AgentMessage.direction == "outbound",
                                           AgentMessage.id < current_inbound_id) \
        .order_by(AgentMessage.id.desc()).limit(lookback).all()
    return any(menu.MENU_MARKER in (m.content or "") for m in recent)


def _handle_automated(db: Session, inbound: InboundMessage, result: HandleResult) -> HandleResult:
    """Never reply to newsletters / no-reply / bounce / auto-reply mail. Invoices that a KNOWN
    vendor's billing system sends from a no-reply address are still saved, silently."""
    from app.agent.identity import find_contact, normalize_address
    result.status = "ignored"
    address = normalize_address(inbound.channel, inbound.sender) or inbound.sender
    contact = find_contact(db, inbound.channel, address)
    if contact is None or not contact.verified or not inbound.media:
        logger.info(f"Ignored automated message from {inbound.sender}")
        return result
    attachments, _ = _prepare_attachments(inbound)
    for media in attachments.values():
        process_invoice_upload(db, file_bytes=media.data, filename=media.filename,
                               organization=contact.organization, source_contact_id=contact.id,
                               source_channel=inbound.channel, demo_fallbacks=False,
                               audit_actor_label=f"{contact.display_name} (automated email)")
    result.status = "saved_silently"
    return result


def handle_inbound(db: Session, inbound: InboundMessage) -> HandleResult:
    result = HandleResult()
    if not settings.AGENT_ENABLED:
        result.status = "ignored"
        return result

    if inbound.automated:
        return _handle_automated(db, inbound, result)

    identity = resolve_identity(db, inbound.channel, inbound.sender)
    conv = get_or_create_conversation(db, identity)
    result.conversation_id = conv.id

    media_log = [{"filename": m.filename, "mime_type": m.mime_type} for m in inbound.media]
    text_for_log = inbound.text or ("[attachment]" if inbound.media else "")
    if inbound.subject:
        text_for_log = f"Subject: {inbound.subject}\n{text_for_log}"

    if not rate_limiter.allow(identity.address, settings.AGENT_RATE_LIMIT_PER_MINUTE):
        record_message(db, conv, "inbound", text_for_log, media=media_log, status="rate_limited")
        result.status = "rate_limited"
        # one notice per burst: only when the previous message wasn't already limited
        prev = [m for m in conv.messages if m.direction == "inbound"][-2:-1]
        if not prev or prev[0].status != "rate_limited":
            _reply(db, conv, RATE_LIMIT_REPLY, result)
        return result

    inbound_msg = record_message(db, conv, "inbound", text_for_log, media=media_log, status="received")
    flush_deferred(db, conv)
    org_settings = get_agent_settings(db, identity.organization)
    business = org_settings.business_name or settings.AGENT_BUSINESS_NAME

    attachments, problems = _prepare_attachments(inbound) if inbound.media else ({}, [])

    # ---------------------------------------------------------------- unknown / unverified sender
    if not identity.is_known and org_settings.allow_new_contacts and identity.contact \
            and identity.contact.kind == "vendor" and identity.contact.onboarding_step in (None, "ask_name"):
        # New vendor/customer: welcome them, accept their invoices, ask who they are.
        result.status = "new_contact"
        text = onboarding.handle_new_contact(db, identity, conv, inbound.text or "", attachments, problems,
                                             business, inbound.sender_name)
        _reply(db, conv, text, result)
        return result

    if not identity.is_known:
        result.status = "unknown_sender"
        for media in attachments.values():
            process_invoice_upload(
                db, file_bytes=media.data, filename=media.filename, organization=identity.organization,
                source_contact_id=identity.contact_id, source_channel=identity.channel,
                force_status="pending_verification",
                audit_actor_label=f"unverified sender {identity.address}",
                demo_fallbacks=False,
            )
        open_item = db.query(AgentApproval).filter(AgentApproval.requested_by_contact_id == identity.contact_id,
                                                   AgentApproval.type == "handoff",
                                                   AgentApproval.status == "pending").first()
        if open_item is None:
            approval.queue_item(db, identity.organization, "handoff",
                                summary=f"Unknown sender {identity.address} wrote in. Verify the contact.",
                                payload={"reason": "unverified_sender", "address": identity.address,
                                         "name_from_channel": inbound.sender_name},
                                conversation_id=conv.id, contact_id=identity.contact_id)
        text = UNKNOWN_MEDIA_REPLY if attachments else UNKNOWN_TEXT_REPLY.format(business=business)
        if problems:
            text += " Note: " + "; ".join(problems) + "."
        _reply(db, conv, text, result)
        return result

    # ---------------------------------------------------------------- YES / NO confirmations (no LLM)
    decision, approval_id = approval.classify_confirmation_reply(inbound.text, inbound.button_payload)
    if decision and not inbound.media:
        item = approval.find_open_confirmation(db, identity, approval_id)
        if item is not None:
            text = approval.execute_confirmation(db, identity, item, decision)
            _reply(db, conv, text, result)
            return result

    # ---------------------------------------------------------------- numbered menu (no LLM needed)
    request_text = inbound.text or ""
    if not inbound.media and not inbound.subject:
        if menu.is_greeting(request_text):
            multilingual = not isinstance(get_provider(), OfflineProvider)
            _reply(db, conv, menu.build_menu(identity, business, multilingual), result)
            return result
        choice = menu.parse_choice(request_text)
        if choice is not None and _menu_shown_recently(db, conv, inbound_msg.id):
            run, ask = menu.resolve_choice(identity, choice)
            if ask:
                _reply(db, conv, ask, result)
                return result
            if run:
                request_text = run  # the chosen option, phrased as a normal request
            else:
                _reply(db, conv, "Please reply with a number from the list, or type MENU to see it again.", result)
                return result

    # ---------------------------------------------------------------- LLM tool loop
    ctx = ToolContext(db=db, identity=identity, conversation=conv, attachments=attachments)
    tools = tool_definitions(identity)
    system = build_system_prompt(identity, business, [t["name"] for t in tools], org_settings.default_language)

    user_text = wrap_untrusted(request_text, f"{identity.channel} message from {identity.display_name}")
    if inbound.subject:
        user_text = wrap_untrusted(f"Subject: {inbound.subject}", "email subject") + "\n" + user_text
    if attachments:
        user_text += "\nAttachments: " + " ".join(
            f"[attachment_id={aid} filename={m.filename!r} type={m.mime_type}]" for aid, m in attachments.items())
    if problems:
        user_text += "\nAttachment problems (tell the sender): " + "; ".join(problems)

    messages = build_history(db, conv, exclude_message_id=inbound_msg.id)
    if messages and messages[-1]["role"] == "user":
        messages[-1]["content"] += "\n\n" + user_text
    else:
        messages.append({"role": "user", "content": user_text})

    provider = get_provider()
    final_text = ""
    try:
        for _ in range(settings.AGENT_MAX_TOOL_ROUNDS):
            resp = provider.complete(system, messages, tools)
            if not resp.tool_calls:
                final_text = resp.text
                break
            messages.append({"role": "assistant", "content": resp.assistant_content})
            tool_results = []
            for call in resp.tool_calls:
                output = execute_tool(ctx, call.name, call.input)
                result.tool_calls.append({"name": call.name, "input": call.input,
                                          "outcome": output.get("error", "ok")})
                tool_results.append({"type": "tool_result", "tool_use_id": call.id,
                                     "content": json.dumps(output, default=str)})
            messages.append({"role": "user", "content": tool_results})
        else:
            raise RuntimeError("Tool loop limit reached")
    except Exception as exc:
        logger.exception(f"Assistant failed for conversation {conv.id}: {exc}")
        db.rollback()
        approval.queue_item(db, identity.organization, "handoff",
                            summary=f"Assistant could not answer {identity.display_name}",
                            payload={"reason": "assistant_error", "error": str(exc)[:300]},
                            conversation_id=conv.id, contact_id=identity.contact_id)
        final_text = FALLBACK_REPLY

    final_text = (final_text or "").strip()
    if not final_text:
        return result

    buttons = []
    if ctx.created_confirmations and identity.channel == "whatsapp":
        cid = ctx.created_confirmations[-1].id
        buttons = [(f"confirm:{cid}", "Yes, confirm"), (f"cancel:{cid}", "Cancel")]

    # Auto-reply off: replies to vendors wait for the owner in the approval queue.
    if identity.kind == "vendor" and not org_settings.auto_reply:
        record_message(db, conv, "outbound", final_text, tool_calls=result.tool_calls, status="held")
        approval.queue_item(db, identity.organization, "held_reply",
                            summary=f"Reply to {identity.display_name} waiting for approval",
                            payload={"text": final_text}, conversation_id=conv.id,
                            contact_id=identity.contact_id)
        result.status = "held"
        return result

    _reply(db, conv, final_text, result, buttons=buttons, tool_calls=result.tool_calls)
    return result
