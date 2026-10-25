"""
LLM providers behind one small interface so the provider can be swapped.

  AnthropicProvider : Claude Messages API with native tool use (production).
  OfflineProvider   : deterministic English-only intent router. Used automatically when no
                      ANTHROPIC_API_KEY is set, so the demo and tests run without network access.
  ScriptedProvider  : returns pre-scripted responses (tests).
"""
import json
import logging
import re
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class ToolCall:
    id: str
    name: str
    input: Dict[str, Any]


@dataclass
class LLMResponse:
    text: str = ""
    tool_calls: List[ToolCall] = field(default_factory=list)
    assistant_content: List[Dict[str, Any]] = field(default_factory=list)  # replayable blocks
    stop_reason: str = "end_turn"


class LLMProvider:
    name = "base"

    def complete(self, system: str, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]]) -> LLMResponse:
        raise NotImplementedError


def make_response(text: str = "", tool_calls: Optional[List[ToolCall]] = None) -> LLMResponse:
    content: List[Dict[str, Any]] = []
    if text:
        content.append({"type": "text", "text": text})
    for tc in tool_calls or []:
        content.append({"type": "tool_use", "id": tc.id, "name": tc.name, "input": tc.input})
    return LLMResponse(text=text, tool_calls=list(tool_calls or []), assistant_content=content,
                       stop_reason="tool_use" if tool_calls else "end_turn")


# ------------------------------------------------------------------------------ Anthropic
class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def __init__(self, api_key: str, model: str, max_tokens: int):
        import anthropic
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        self.max_tokens = max_tokens

    def complete(self, system, messages, tools) -> LLMResponse:
        kwargs: Dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "system": [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            "messages": messages,
        }
        if tools:
            kwargs["tools"] = tools
        resp = self.client.messages.create(**kwargs)
        texts, calls, content = [], [], []
        for block in resp.content:
            if block.type == "text":
                texts.append(block.text)
                content.append({"type": "text", "text": block.text})
            elif block.type == "tool_use":
                calls.append(ToolCall(id=block.id, name=block.name, input=dict(block.input or {})))
                content.append({"type": "tool_use", "id": block.id, "name": block.name, "input": block.input})
        return LLMResponse(text="\n".join(texts).strip(), tool_calls=calls, assistant_content=content,
                           stop_reason=resp.stop_reason or "end_turn")


# ------------------------------------------------------------------------------ Scripted
class ScriptedProvider(LLMProvider):
    """Test helper: each call pops the next response (or calls a function with the messages)."""
    name = "scripted"

    def __init__(self, script: List[Any]):
        self.script = list(script)
        self.calls: List[Dict[str, Any]] = []

    def complete(self, system, messages, tools) -> LLMResponse:
        self.calls.append({"system": system, "messages": json.loads(json.dumps(messages, default=str)),
                           "tools": [t["name"] for t in tools]})
        if not self.script:
            return make_response("(no more scripted responses)")
        step = self.script.pop(0)
        return step(messages) if callable(step) else step


# ------------------------------------------------------------------------------ Offline
INVOICE_NO = re.compile(r"\b((?=[A-Z0-9/-]*\d)[A-Z]{2,6}[-/]?[A-Z0-9][A-Z0-9/-]{1,24})\b", re.IGNORECASE)
ATTACHMENT = re.compile(r"attachment_id=(\S+)")


def _last_user_text(messages: List[Dict[str, Any]]) -> str:
    msg = messages[-1]
    content = msg["content"]
    if isinstance(content, str):
        return content
    return "\n".join(b.get("text", "") for b in content if b.get("type") == "text")


def _strip_wrappers(text: str) -> str:
    return re.sub(r"</?untrusted_content[^>]*>", " ", text)


class OfflineProvider(LLMProvider):
    """A small rule-based stand-in for the model (English only). Good enough to demo every tool."""
    name = "offline"

    def complete(self, system, messages, tools) -> LLMResponse:
        allowed = {t["name"] for t in tools}
        last = messages[-1]
        if isinstance(last["content"], list) and any(b.get("type") == "tool_result" for b in last["content"]):
            return make_response(self._render(messages))
        text = _last_user_text(messages)
        call = self._route(text, allowed)
        if isinstance(call, str):
            return make_response(call)
        return make_response(tool_calls=call)

    # ---- intent routing
    def _route(self, raw: str, allowed: set):
        def tc(name, args):
            return ToolCall(id=f"offline_{uuid.uuid4().hex[:8]}", name=name, input=args)

        attachments = ATTACHMENT.findall(raw)
        if attachments and "ingest_invoice" in allowed:
            return [tc("ingest_invoice", {"attachment_id": a}) for a in attachments]

        body = _strip_wrappers(raw).split("Attachments:")[0]
        t = " ".join(body.lower().split())
        numbers = [m for m in INVOICE_NO.findall(body) if not m.lower().startswith(("http", "untrusted"))]
        number = numbers[0] if numbers else None

        def can(name):
            return name in allowed

        if re.search(r"\b(complain|complaint|dispute|lawyer|legal|human|manager|talk to someone)\b", t) and can("handoff_to_human"):
            return [tc("handoff_to_human", {"reason": "Sender asked for a person", "summary": body.strip()[:500]})]
        if "summary" in t and can("get_daily_summary"):
            return [tc("get_daily_summary", {})]
        if re.search(r"suspicious|flagged|fraud|risky|risk", t) and can("list_flagged_invoices"):
            return [tc("list_flagged_invoices", {})]
        if "duplicate" in t and can("list_duplicates"):
            return [tc("list_duplicates", {})]
        m = re.search(r"\b(?:owe|owed to|balance (?:for|of|with)|outstanding (?:for|to|with))\s+(.+?)[\s?.!]*$", t)
        if m and can("get_vendor_balance"):
            return [tc("get_vendor_balance", {"vendor_name": m.group(1).strip()})]
        if number and re.search(r"\bapprove\b", t) and can("request_invoice_action"):
            return [tc("request_invoice_action", {"invoice_number": number, "action": "approve"})]
        if number and re.search(r"\breject\b", t) and can("request_invoice_action"):
            reason = re.split(r"\bbecause\b", body, maxsplit=1, flags=re.IGNORECASE)
            args = {"invoice_number": number, "action": "reject"}
            if len(reason) > 1:
                args["reason"] = reason[1].strip()[:500]
            return [tc("request_invoice_action", args)]
        if number and re.search(r"mark(ed)? .*paid|\bpaid\b.*\bmark", t) and can("request_invoice_action"):
            return [tc("request_invoice_action", {"invoice_number": number, "action": "mark_paid"})]
        if number and re.search(r"\b(copy|resend|send me)\b", t) and can("send_document_copy"):
            return [tc("send_document_copy", {"invoice_number": number})]
        if number and can("get_invoice_status"):
            return [tc("get_invoice_status", {"invoice_number": number})]
        if re.search(r"\b(status|bill|bills|invoice|invoices|paid|payment|received|get my|pending)\b", t) and can("list_my_invoices"):
            status = "pending" if "pending" in t else "all"
            return [tc("list_my_invoices", {"status": status})]
        if re.search(r"\b(hi|hello|hey|namaste|vanakkam|good (morning|evening))\b", t):
            return "Hello! You can send an invoice here as a PDF or photo, or ask me about an invoice's status."
        if not allowed:
            return "Sorry, I can't help with that here."
        return ("I can help with invoices: send one as a PDF or photo, ask for the status of an invoice "
                "number, or ask about your bills. For anything else I can pass you to the team.")

    # ---- rendering tool results
    def _render(self, messages) -> str:
        names = {}
        for m in messages:
            if m["role"] == "assistant" and isinstance(m["content"], list):
                for b in m["content"]:
                    if b.get("type") == "tool_use":
                        names[b["id"]] = b["name"]
        parts = []
        for block in messages[-1]["content"]:
            if block.get("type") != "tool_result":
                continue
            try:
                data = json.loads(block.get("content") or "{}")
            except (TypeError, ValueError):
                data = {}
            parts.append(self._render_one(names.get(block.get("tool_use_id"), ""), data))
        return "\n\n".join(p for p in parts if p)

    @staticmethod
    def _inv_line(i: Dict[str, Any]) -> str:
        bits = [i.get("invoice_number") or "(no number)", i.get("amount", "")]
        if i.get("vendor_name") and "risk_level" in i:
            bits.insert(1, i["vendor_name"])
        status = i.get("status", "")
        if i.get("payment_status") == "paid":
            status += ", paid"
        return " - ".join(b for b in bits if b) + f" ({status})"

    def _render_one(self, name: str, d: Dict[str, Any]) -> str:
        if d.get("error") == "not_permitted":
            return "Sorry, I can't do that for you."
        if d.get("error"):
            return f"Sorry: {d.get('message') or d['error']}"
        if d.get("ambiguous"):
            cands = d.get("candidates", [])
            labels = [c if isinstance(c, str) else c.get("invoice_number") or "?" for c in cands]
            return "Which one do you mean: " + ", ".join(labels) + "?"
        if name == "ingest_invoice":
            inv = d.get("invoice", {})
            msg = f"Received invoice {inv.get('invoice_number') or '(number unclear)'} for {inv.get('amount')}."
            probs = inv.get("problems_found") or []
            if probs:
                msg += " Please check: " + "; ".join(p.rstrip(". ") for p in probs[:3]) + "."
            else:
                msg += f" Status: {inv.get('status')}."
            if inv.get("risk_level"):
                msg += f" Risk: {inv['risk_level']}, duplicates: {inv.get('duplicate_status')}."
            return msg
        if name == "get_invoice_status":
            if not d.get("found"):
                return "I couldn't find an invoice with that number for you."
            lines = []
            for i in d["invoices"]:
                line = self._inv_line(i)
                if i.get("approved_on"):
                    line += f", approved on {i['approved_on']}"
                if i.get("risk_reasons"):
                    line += ". Flags: " + "; ".join(i["risk_reasons"][:2])
                lines.append(line)
            return "\n".join(lines)
        if name == "list_my_invoices":
            if not d.get("total"):
                return "I don't see any invoices for that."
            head = f"{d['total']} invoice(s)" + (f", latest {d['showing']}:" if d["total"] > d["showing"] else ":")
            return head + "\n" + "\n".join(self._inv_line(i) for i in d["invoices"])
        if name == "get_vendor_balance":
            if not d.get("found"):
                closest = d.get("closest") or []
                return "I couldn't find that vendor." + (f" Did you mean {', '.join(closest)}?" if closest else "")
            return (f"{d['vendor_name']}: you owe {', '.join(d['approved_unpaid_total'])} across "
                    f"{d['approved_unpaid_count']} approved unpaid invoice(s). Another "
                    f"{', '.join(d['under_review_total'])} ({d['under_review_count']} invoice(s)) is still under review.")
        if name == "list_flagged_invoices":
            if not d.get("total"):
                return "No suspicious invoices in that period."
            lines = [f"{d['total']} flagged invoice(s):"]
            for i in d["invoices"][:5]:
                lines.append(f"- {self._inv_line(i)}: " + "; ".join(i.get("reasons", [])[:2]))
            return "\n".join(lines)
        if name == "list_duplicates":
            if not d.get("count"):
                return "No likely duplicates found recently."
            return "Possible duplicates:\n" + "\n".join(
                f"- {x.get('invoice_number')} matches {x.get('matches_invoice')} ({x.get('similarity_percent')}%)"
                for x in d["duplicates"][:5])
        if name == "get_daily_summary":
            top = ", ".join(f"{v['vendor']} {v['amount']}" for v in d.get("top_vendors", [])) or "none"
            return (f"Summary for {d['date']}: {d['received']} received ({', '.join(d['received_value'])}), "
                    f"{d['approved']} approved, {d['flagged']} flagged. Top vendors: {top}. "
                    f"{d['waiting_for_review_overall']} waiting for review overall.")
        if name == "request_invoice_action":
            inv = d.get("invoice", {})
            verb = {"approve": "approve", "reject": "reject", "mark_paid": "mark as paid"}.get(d.get("action"), d.get("action"))
            return (f"Please confirm: {verb} invoice {inv.get('invoice_number')} from {inv.get('vendor_name')} "
                    f"for {inv.get('amount')}? Reply YES to confirm or NO to cancel.")
        if name == "draft_reply":
            return f"Draft to {d.get('recipient')} saved. It will be sent after approval in the Assistant Inbox."
        if name == "send_document_copy":
            return "Your request is noted. The copy will be sent once the team approves it."
        if name == "handoff_to_human":
            return "I've passed this to the team. Someone will get back to you soon."
        return json.dumps(d)[:500]


# ------------------------------------------------------------------------------ registry
_override: Optional[LLMProvider] = None
_cached: Optional[LLMProvider] = None


def set_provider(provider: Optional[LLMProvider]) -> None:
    """Tests/demos: force a provider (None restores the configured one)."""
    global _override
    _override = provider


def get_provider() -> LLMProvider:
    global _cached
    if _override is not None:
        return _override
    if _cached is None:
        choice = (settings.AGENT_LLM_PROVIDER or "anthropic").lower()
        if choice == "anthropic" and settings.ANTHROPIC_API_KEY:
            _cached = AnthropicProvider(settings.ANTHROPIC_API_KEY, settings.AGENT_MODEL, settings.AGENT_MAX_TOKENS)
        else:
            if choice == "anthropic":
                logger.warning("ANTHROPIC_API_KEY not set: InvoShield Assistant is using the offline (English-only) provider.")
            _cached = OfflineProvider()
    return _cached


def provider_status() -> Dict[str, Any]:
    p = get_provider()
    return {"provider": p.name, "model": getattr(p, "model", None)}
