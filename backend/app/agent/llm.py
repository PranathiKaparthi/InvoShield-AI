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
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

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


# ------------------------------------------------------------------------------ Google Gemini
GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"
_GEMINI_TYPES = {"object": "OBJECT", "string": "STRING", "number": "NUMBER", "integer": "INTEGER",
                 "boolean": "BOOLEAN", "array": "ARRAY"}


def gemini_schema(schema: Dict[str, Any]) -> Dict[str, Any]:
    """Convert our JSON schema to the subset Gemini accepts (it rejects e.g. additionalProperties).
    Our own validator still enforces the full schema before any tool runs."""
    out: Dict[str, Any] = {}
    if "type" in schema:
        out["type"] = _GEMINI_TYPES.get(schema["type"], schema["type"].upper())
    for key in ("description", "enum", "required", "minimum", "maximum"):
        if key in schema:
            out[key] = schema[key]
    if "properties" in schema:
        out["properties"] = {k: gemini_schema(v) for k, v in schema["properties"].items()}
    if "items" in schema:
        out["items"] = gemini_schema(schema["items"])
    return out


def to_gemini_contents(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    names: Dict[str, str] = {}
    contents = []
    for m in messages:
        role = "model" if m["role"] == "assistant" else "user"
        content = m["content"]
        parts: List[Dict[str, Any]] = []
        if isinstance(content, str):
            parts = [{"text": content}] if content else []
        else:
            for b in content:
                kind = b.get("type")
                if "gemini_part" in b:  # replay Gemini's own part (keeps any thought signature)
                    parts.append(b["gemini_part"])
                    if kind == "tool_use":
                        names[b["id"]] = b["name"]
                elif kind == "text" and b.get("text"):
                    parts.append({"text": b["text"]})
                elif kind == "tool_use":
                    names[b["id"]] = b["name"]
                    parts.append({"functionCall": {"name": b["name"], "args": b.get("input") or {}}})
                elif kind == "tool_result":
                    try:
                        data = json.loads(b.get("content") or "{}")
                    except (TypeError, ValueError):
                        data = {"result": b.get("content")}
                    if not isinstance(data, dict):
                        data = {"result": data}
                    parts.append({"functionResponse": {"name": names.get(b.get("tool_use_id"), "tool"),
                                                       "response": data}})
        if parts:
            contents.append({"role": role, "parts": parts})
    return contents


class GeminiProvider(LLMProvider):
    """Google Gemini (generateContent REST API) with function calling."""
    name = "gemini"

    def __init__(self, api_key: str, model: str, max_tokens: int, client=None,
                 fallback_models: Optional[List[str]] = None, retry_wait: float = 1.5):
        import httpx
        self.api_key = api_key
        self.model = model.replace("models/", "")
        self.fallback_models = [m.strip() for m in (fallback_models if fallback_models is not None
                                                    else (settings.GEMINI_FALLBACK_MODELS or "").split(",")) if m.strip()]
        self.retry_wait = retry_wait
        # Newer Gemini models spend part of the output budget on internal reasoning.
        self.max_tokens = max(max_tokens, 4096)
        self.client = client or httpx.Client(timeout=60.0)

    def complete(self, system, messages, tools) -> LLMResponse:
        body: Dict[str, Any] = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": to_gemini_contents(messages),
            "generationConfig": {"maxOutputTokens": self.max_tokens, "temperature": 0.3},
        }
        if tools:
            body["tools"] = [{"functionDeclarations": [
                {"name": t["name"], "description": t.get("description", ""),
                 "parameters": gemini_schema(t["input_schema"])} for t in tools]}]
        resp = None
        # Busy or rate-limited (429/503/500): wait briefly and retry, then try the backup models.
        for model in [self.model, self.model] + [m for m in self.fallback_models if m != self.model]:
            resp = self.client.post(f"{GEMINI_BASE}/models/{model}:generateContent", json=body,
                                    headers={"x-goog-api-key": self.api_key})
            if resp.status_code not in (429, 500, 503):
                break
            logger.warning(f"Gemini model {model} busy ({resp.status_code}); retrying")
            time.sleep(self.retry_wait)
        if resp.status_code >= 400:
            try:
                detail = resp.json().get("error", {}).get("message", resp.text)
            except ValueError:
                detail = resp.text
            raise RuntimeError(f"Gemini API error {resp.status_code}: {detail[:300]}")
        data = resp.json()
        candidates = data.get("candidates") or []
        if not candidates:
            raise RuntimeError(f"Gemini returned no answer: {json.dumps(data.get('promptFeedback', {}))[:200]}")
        texts, calls, content = [], [], []
        for part in (candidates[0].get("content") or {}).get("parts", []) or []:
            if part.get("thought"):
                continue
            if "functionCall" in part:
                fc = part["functionCall"]
                call = ToolCall(id=fc.get("id") or f"gem_{uuid.uuid4().hex[:10]}", name=fc.get("name", ""),
                                input=dict(fc.get("args") or {}))
                calls.append(call)
                content.append({"type": "tool_use", "id": call.id, "name": call.name, "input": call.input,
                                "gemini_part": part})
            elif part.get("text"):
                texts.append(part["text"])
                content.append({"type": "text", "text": part["text"], "gemini_part": part})
        return LLMResponse(text="\n".join(texts).strip(), tool_calls=calls, assistant_content=content,
                           stop_reason="tool_use" if calls else "end_turn")


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
LABELLED_NO = re.compile(r"\b(?:invoice|bill|inv)\s*(?:no\.?|number|num|#)?\s*[:#-]?\s*([A-Z0-9/-]*\d[A-Z0-9/-]*)",
                         re.IGNORECASE)
ATTACHMENT = re.compile(r"attachment_id=(\S+)")

# Words people actually use, including romanised Hindi/Tamil/Telugu and native scripts.
KW = {
    "handoff": r"complain|complaint|dispute|lawyer|legal|human|manager|talk to|speak to|call me|someone from|"
               r"real person|शिकायत|புகார்|ఫిర్యాదు",
    "thanks": r"^(?:(?:ok(?:ay)?|k|thanks?|thank you|thx|ty|nandri|nanri|dhanyavad|dhanyawad|shukriya|"
              r"dhanyavadalu|super|great|fine|done|good|got it|धन्यवाद|நன்றி|ధన్యవాదాలు)\s*)+"
              r"(?:(?:sir|madam|ji|bro|anna|so much|a lot)\s*)*$",
    "summary": r"summary|report|today|todays|aaj|inniki|ivvala|सारांश|சுருக்கம்|సారాంశం",
    "flagged": r"suspicious|fraud|risky|\brisk|flag|doubt|shady|fake|सस्पीशियस|சந்தேக",
    "duplicate": r"duplicate|double bill|twice|same bill|repeat",
    "copy": r"\bcopy\b|\bpdf\b|resend|send (me|it|again|the bill|the invoice)|bhejo|bhej do|anuppu|pampu|pampandi",
    "approve": r"\bapprove|\bpass (it|the)|\bok kar",
    "reject": r"\breject|\bcancel (the )?(invoice|bill)",
    "paid_action": r"mark(ed)? (it |as )?paid|paid mark|set (as )?paid",
    "payment": r"\bpaid\b|payment|\bpay\b|paisa|paise|panam|dabbu|kab milega|money|eppo|eppudu|when will|"
               r"पैसा|भुगतान|பணம்|கட்டணம்|చెల్లింపు|డబ్బు",
    "pending": r"pending|waiting|to review|review queue|baaki|baki",
    "bills": r"\bbills?\b|\binvoices?\b|status|update|received|\bgot\b|reached|\bmila\b|aaya|vandhucha|vanthucha|"
             r"kidaichucha|vachinda|andinda|बिल|स्थिति|பில்|நிலை|బిల్|స్థితి",
}
OWE_PATTERNS = [
    r"(?:how much (?:do )?(?:i|we) owe(?: to)?|owe(?: to)?|owed to)\s+(.+)",
    r"(?:balance|dues?|outstanding|pending (?:amount|payment))\s+(?:of|for|to|with)\s+(.+)",
    r"(.+?)\s+(?:balance|dues|outstanding)$",
    r"(.+?)\s+(?:ko )?kitna dena(?: hai)?$",
    r"kitna dena(?: hai)?\s+(.+)",
]


def _last_user_text(messages: List[Dict[str, Any]]) -> str:
    for msg in reversed(messages):
        if msg["role"] != "user":
            continue
        content = msg["content"]
        if isinstance(content, str):
            return content
        texts = [b.get("text", "") for b in content if b.get("type") == "text"]
        if texts:
            return "\n".join(texts)
    return ""


def _previous_assistant_text(messages: List[Dict[str, Any]]) -> str:
    if len(messages) >= 2 and messages[-2]["role"] == "assistant" and isinstance(messages[-2]["content"], str):
        return messages[-2]["content"]
    return ""


def _strip_wrappers(text: str) -> str:
    text = re.sub(r"<untrusted_content[^>]*>\s*", "", text)
    text = text.replace("</untrusted_content>", "")
    return text.split("\nAttachments:")[0].split("\nAttachment problems")[0]


def _latest_message_body(raw: str) -> str:
    """The text of the newest message only (history may be merged into the same user turn)."""
    blocks = re.findall(r"<untrusted_content[^>]*>\n?(.*?)\n?</untrusted_content>", raw, re.S)
    return (blocks[-1] if blocks else _strip_wrappers(raw)).strip()


def _invoice_number(text: str) -> Optional[str]:
    m = LABELLED_NO.search(text)
    if m:
        return m.group(1)
    for cand in INVOICE_NO.findall(text):
        if not cand.lower().startswith(("http", "untrusted")):
            return cand
    return None


def _count(n: int, word: str = "invoice") -> str:
    return f"{n} {word}" + ("" if n == 1 else "s")


def _clean_reason(reason: str) -> str:
    return reason.split(": ", 1)[-1].rstrip(".")


class OfflineProvider(LLMProvider):
    """A small rule-based stand-in for the model. Understands common English, Hinglish/Tanglish and
    a few native-script words; always answers in simple English. Good enough to demo every tool."""
    name = "offline"

    def complete(self, system, messages, tools) -> LLMResponse:
        allowed = {t["name"] for t in tools}
        last = messages[-1]
        if isinstance(last["content"], list) and any(b.get("type") == "tool_result" for b in last["content"]):
            return make_response(self._render(messages))
        call = self._route(messages, allowed)
        if isinstance(call, str):
            return make_response(call)
        return make_response(tool_calls=call)

    # ---- intent routing
    def _route(self, messages, allowed: set):
        from app.agent import menu  # local import keeps llm.py free of agent-package cycles

        def tc(name, args):
            return ToolCall(id=f"offline_{uuid.uuid4().hex[:8]}", name=name, input=args)

        def can(name):
            return name in allowed

        raw = messages[-1]["content"] if isinstance(messages[-1]["content"], str) else _last_user_text(messages)
        attachments = ATTACHMENT.findall(raw.split("\nAttachments:")[-1]) if "\nAttachments:" in raw else []
        if attachments and can("ingest_invoice"):
            return [tc("ingest_invoice", {"attachment_id": a}) for a in attachments]

        body = _latest_message_body(raw)
        t = " ".join(body.lower().split()).strip(" ?!.")
        number = _invoice_number(body)
        prev = _previous_assistant_text(messages)

        def has(key):
            return re.search(KW[key], t) is not None

        # ---- answers to a question the assistant just asked
        if prev and t:
            if menu.ASK_COPY in prev and can("send_document_copy"):
                return [tc("send_document_copy", {"invoice_number": number or body.strip()[:100]})]
            if menu.ASK_STATUS in prev and can("get_invoice_status"):
                return [tc("get_invoice_status", {"invoice_number": number or body.strip()[:100]})]
            if menu.ASK_TEAM in prev and can("handoff_to_human"):
                return [tc("handoff_to_human", {"reason": "Message for the team", "summary": body.strip()[:1000]})]
            if (menu.ASK_VENDOR in prev or "Which vendor do you mean" in prev) and can("get_vendor_balance"):
                return [tc("get_vendor_balance", {"vendor_name": body.strip()[:255]})]
            m = re.search(r"Did you mean (.+?)\?", prev)
            if m and re.fullmatch(r"(yes|y|yeah|yep|haan|ha|aama|avunu|correct|right)", t) and can("get_vendor_balance"):
                return [tc("get_vendor_balance", {"vendor_name": m.group(1).split(", ")[0]})]

        if not t:
            return "Please type your question, or reply MENU to see what I can do."
        if re.search(KW["thanks"], t):
            return "You're welcome! Reply MENU anytime to see what I can do."
        if has("handoff") and can("handoff_to_human"):
            return [tc("handoff_to_human", {"reason": "Sender asked for a person", "summary": body.strip()[:500]})]

        # ---- actions on one invoice (need an invoice number)
        if number and has("approve") and can("request_invoice_action"):
            return [tc("request_invoice_action", {"invoice_number": number, "action": "approve"})]
        if number and has("reject") and can("request_invoice_action"):
            args = {"invoice_number": number, "action": "reject"}
            reason = re.split(r"\bbecause\b|\breason\b|\bas\b", body, maxsplit=1, flags=re.IGNORECASE)
            if len(reason) > 1 and reason[1].strip(" :"):
                args["reason"] = reason[1].strip(" :")[:500]
            return [tc("request_invoice_action", args)]
        if number and has("paid_action") and can("request_invoice_action"):
            return [tc("request_invoice_action", {"invoice_number": number, "action": "mark_paid"})]
        if number and has("copy") and can("send_document_copy"):
            return [tc("send_document_copy", {"invoice_number": number})]
        if (has("approve") or has("reject")) and not number and can("request_invoice_action"):
            return menu.ASK_ACTION

        # ---- owner questions
        if has("summary") and can("get_daily_summary"):
            return [tc("get_daily_summary", {})]
        if has("flagged") and can("list_flagged_invoices"):
            return [tc("list_flagged_invoices", {})]
        if has("duplicate") and not number and can("list_duplicates"):
            return [tc("list_duplicates", {})]
        if can("get_vendor_balance"):
            for pat in OWE_PATTERNS:
                m = re.search(pat, t)
                if m:
                    name = re.sub(r"^(to|the|for)\s+", "", m.group(1)).strip(" ?.")
                    if name and name not in ("i", "we", "me"):
                        return [tc("get_vendor_balance", {"vendor_name": name})]
            if re.search(r"\b(owe|balance|dues|outstanding|kitna dena)\b", t):
                return menu.ASK_VENDOR

        # ---- one invoice / my invoices
        if number and can("get_invoice_status"):
            return [tc("get_invoice_status", {"invoice_number": number})]
        if has("copy") and can("send_document_copy"):
            return menu.ASK_COPY
        if has("pending") and can("list_my_invoices"):
            return [tc("list_my_invoices", {"status": "pending"})]
        if (has("payment") or has("bills")) and can("list_my_invoices"):
            return [tc("list_my_invoices", {"status": "all"})]

        if not allowed:
            return "Sorry, I can't help with that here."
        return ("Sorry, I didn't catch that. Reply MENU to see what I can do, or send an invoice as a PDF "
                "or photo.")

    # ---- rendering tool results
    def _render(self, messages) -> str:
        names = {}
        for m in messages:
            if m["role"] == "assistant" and isinstance(m["content"], list):
                for b in m["content"]:
                    if b.get("type") == "tool_use":
                        names[b["id"]] = b["name"]
        asked = " ".join(_latest_message_body(_last_user_text(messages)).lower().split())
        parts = []
        for block in messages[-1]["content"]:
            if block.get("type") != "tool_result":
                continue
            try:
                data = json.loads(block.get("content") or "{}")
            except (TypeError, ValueError):
                data = {}
            parts.append(self._render_one(names.get(block.get("tool_use_id"), ""), data, asked))
        return "\n\n".join(p for p in parts if p)

    @staticmethod
    def _status_text(i: Dict[str, Any]) -> str:
        status = i.get("status", "")
        if i.get("payment_status") == "paid":
            return "paid"
        if status == "approved":
            return "approved, payment pending"
        return status

    def _inv_line(self, i: Dict[str, Any], with_vendor: bool = False) -> str:
        bits = [i.get("invoice_number") or "(no number)"]
        if with_vendor and i.get("vendor_name"):
            bits.append(i["vendor_name"])
        bits.append(i.get("amount", ""))
        bits.append(self._status_text(i))
        return "• " + " · ".join(b for b in bits if b)

    def _render_one(self, name: str, d: Dict[str, Any], asked: str = "") -> str:
        staff = lambda inv: "risk_level" in inv  # noqa: E731  (staff views carry risk info)
        if d.get("error") == "not_permitted":
            return "Sorry, I can't do that for you. Reply MENU to see what I can help with."
        if d.get("error"):
            return f"Sorry, {(d.get('message') or d['error']).rstrip('.')}."
        if d.get("ambiguous"):
            cands = d.get("candidates", [])
            labels = [c if isinstance(c, str) else c.get("invoice_number") or "?" for c in cands]
            if name == "get_vendor_balance":
                return "Which vendor do you mean: " + ", ".join(labels) + "?"
            return "Which one do you mean: " + ", ".join(labels) + "?"

        if name == "ingest_invoice":
            inv = d.get("invoice", {})
            lines = [f"Thank you! Received invoice {inv.get('invoice_number') or '(number not readable)'} "
                     f"for {inv.get('amount')}."]
            probs = inv.get("problems_found") or []
            if probs:
                lines.append("Please check: " + "; ".join(p.rstrip(". ") for p in probs[:3]) + ".")
                lines.append("If needed, send a corrected copy here.")
            if inv.get("note"):
                lines.append(inv["note"])
            if staff(inv):
                lines.append(f"Risk: {inv.get('risk_level')}. Duplicate check: {inv.get('duplicate_status')}.")
            else:
                lines.append("We'll update you here once it has been reviewed.")
            return "\n".join(lines)

        if name == "get_invoice_status":
            if not d.get("found"):
                return "I couldn't find an invoice with that number for you. Please check the number and try again."
            lines = []
            for i in d["invoices"]:
                line = self._inv_line(i, with_vendor=staff(i))
                if i.get("approved_on"):
                    line += f" (approved on {i['approved_on']})"
                lines.append(line)
                if i.get("risk_reasons"):
                    lines.append("  Reason to check: " + "; ".join(_clean_reason(r) for r in i["risk_reasons"][:2]))
            return "\n".join(lines)

        if name == "list_my_invoices":
            if not d.get("total"):
                return "I don't see any invoices for that yet."
            invs = d["invoices"]
            is_staff = any(staff(i) for i in invs)
            head = (_count(d['total']) if is_staff else f"You have {_count(d['total'])} with us") + (
                f", latest {d['showing']}:" if d["total"] > d["showing"] else ":")
            lines = [head] + [self._inv_line(i, with_vendor=is_staff) for i in invs]
            if not is_staff and re.search(KW["payment"], asked):
                lines.append("I can't give a payment date, but you'll get a message here as soon as an "
                             "invoice is marked paid.")
            return "\n".join(lines)

        if name == "get_vendor_balance":
            if not d.get("found"):
                closest = d.get("closest") or []
                return "I couldn't find that vendor." + (f" Did you mean {', '.join(closest)}?" if closest else "")
            owed = ", ".join(d["approved_unpaid_total"])
            review = ", ".join(d["under_review_total"])
            if d["approved_unpaid_count"]:
                text = (f"You owe {d['vendor_name']} {owed} "
                        f"({_count(d['approved_unpaid_count'], 'approved invoice')} not paid yet).")
            else:
                text = f"Nothing approved is unpaid for {d['vendor_name']} right now."
            if d["under_review_count"]:
                text += f" Another {review} ({_count(d['under_review_count'])}) is still waiting for review."
            return text

        if name == "list_flagged_invoices":
            if not d.get("total"):
                return "Good news: no suspicious invoices in the last 7 days."
            lines = [f"{_count(d['total'])} " + ("needs" if d['total'] == 1 else "need") + " a closer look:"]
            for i in d["invoices"][:5]:
                lines.append(self._inv_line(i, with_vendor=True))
                if i.get("reasons"):
                    lines.append("  Why: " + "; ".join(_clean_reason(r) for r in i["reasons"][:2]))
            lines.append("Reply \"approve <number>\" or \"reject <number> because ...\" to act on one.")
            return "\n".join(lines)

        if name == "list_duplicates":
            if not d.get("count"):
                return "No likely duplicate invoices in the last 30 days."
            lines = ["Possible duplicates:"] + [
                f"• {x.get('invoice_number')} looks like {x.get('matches_invoice')} ({x.get('similarity_percent')}% similar)"
                for x in d["duplicates"][:5]]
            return "\n".join(lines)

        if name == "get_daily_summary":
            top = ", ".join(f"{v['vendor']} {v['amount']}" for v in d.get("top_vendors", [])) or "none"
            return (f"Summary for {d['date']}:\n"
                    f"• Received: {_count(d['received'])}, {', '.join(d['received_value'])}\n"
                    f"• Approved: {d['approved']}\n"
                    f"• Flagged: {d['flagged']}\n"
                    f"• Top vendors: {top}\n"
                    f"• Waiting for review overall: {d['waiting_for_review_overall']}")

        if name == "request_invoice_action":
            inv = d.get("invoice", {})
            verb = {"approve": "Approve", "reject": "Reject", "mark_paid": "Mark as paid"}.get(d.get("action"), d.get("action"))
            return (f"Please confirm: {verb} invoice {inv.get('invoice_number')} from {inv.get('vendor_name')} "
                    f"for {inv.get('amount')}?\nReply YES to confirm or NO to cancel.")
        if name == "draft_reply":
            return f"Draft to {d.get('recipient')} saved. It will be sent after you approve it in the Assistant Inbox."
        if name == "send_document_copy":
            return "Your request is noted. The copy will be sent here once the team approves it."
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
        if choice == "gemini" and settings.GOOGLE_API_KEY:
            _cached = GeminiProvider(settings.GOOGLE_API_KEY, settings.GEMINI_MODEL, settings.AGENT_MAX_TOKENS)
        elif choice == "anthropic" and settings.ANTHROPIC_API_KEY:
            _cached = AnthropicProvider(settings.ANTHROPIC_API_KEY, settings.AGENT_MODEL, settings.AGENT_MAX_TOKENS)
        else:
            if choice in ("anthropic", "gemini"):
                logger.warning(f"No API key for '{choice}': InvoShield Assistant is using the offline "
                               "(English-only) provider.")
            _cached = OfflineProvider()
    return _cached


def provider_status() -> Dict[str, Any]:
    p = get_provider()
    return {"provider": p.name, "model": getattr(p, "model", None)}
