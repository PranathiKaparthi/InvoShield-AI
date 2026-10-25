"""
Numbered menu: the easiest way for a busy vendor or shop owner to use the assistant.

"hi" / "menu" / "help"  ->  a short numbered list for that person's role.
Replying "1", "2", ... right after the menu either runs that request through the normal agent
(so answers still come only from tools) or asks one simple follow-up question.
Handled in code, so it works the same with Claude and with the offline brain.
"""
import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

from app.agent.identity import Identity

MENU_MARKER = "Reply with a number"

GREETING_WORDS = {
    "hi", "hii", "hiii", "hello", "helo", "hey", "hai", "menu", "help", "start", "options", "option",
    "namaste", "namaskar", "namaskaram", "vanakkam", "good morning", "good afternoon", "good evening",
    "gm", "hi there", "hello there", "?",
    "नमस्ते", "नमस्कार", "हेलो", "मेनू", "வணக்கம்", "மெனு", "నమస్కారం", "నమస్తే", "మెను",
}

# Questions asked after a menu choice. The offline brain recognises these exact phrases.
ASK_COPY = "Which invoice number do you need a copy of? For example: QS-2045"
ASK_TEAM = "Sure. Type your message for the team and I'll pass it on."
ASK_VENDOR = "Which vendor? Type the name, for example: Quantum Solutions"
ASK_ACTION = ("Which invoice? Type for example \"approve QS-2045\", or \"reject QS-2045 because the rate "
              "is wrong\". I'll ask you to confirm before anything changes.")
ASK_STATUS = "Which invoice number? For example: QS-2045"


@dataclass
class MenuItem:
    label: str
    request: Optional[str] = None   # run this through the agent
    ask: Optional[str] = None       # or ask this follow-up question


VENDOR_MENU: List[MenuItem] = [
    MenuItem("My invoices and their status", request="Show my invoices and their status"),
    MenuItem("Payment status", request="Which of my invoices are paid and which are not paid yet?"),
    MenuItem("Status of one invoice", ask=ASK_STATUS),
    MenuItem("Get a copy of an invoice", ask=ASK_COPY),
    MenuItem("Talk to the team", ask=ASK_TEAM),
]

REVIEWER_MENU: List[MenuItem] = [
    MenuItem("Suspicious invoices this week", request="Any suspicious invoices this week?"),
    MenuItem("Possible duplicate invoices", request="Show duplicates"),
    MenuItem("Today's summary", request="Daily summary for today"),
    MenuItem("Invoices waiting for review", request="Show pending invoices"),
    MenuItem("How much I owe a vendor", ask=ASK_VENDOR),
    MenuItem("Approve or reject an invoice", ask=ASK_ACTION),
]

STAFF_USER_MENU: List[MenuItem] = [
    MenuItem("My invoices and their status", request="Show my invoices and their status"),
    MenuItem("Status of one invoice", ask=ASK_STATUS),
    MenuItem("Talk to the team", ask=ASK_TEAM),
]


def menu_for(identity: Identity) -> List[MenuItem]:
    if identity.kind == "vendor":
        return VENDOR_MENU
    if identity.role in ("admin", "reviewer"):
        return REVIEWER_MENU
    return STAFF_USER_MENU


def _first_name(identity: Identity) -> str:
    name = identity.display_name or ""
    name = re.sub(r"\(.*?\)", "", name).strip()
    return name.split()[0] if name else ""


def build_menu(identity: Identity, business: str, multilingual: bool) -> str:
    name = _first_name(identity)
    hello = f"Hello {name}!" if name else "Hello!"
    lines = [f"{hello} I'm the invoice assistant for {business}.", f"{MENU_MARKER}:"]
    lines += [f"{i}. {item.label}" for i, item in enumerate(menu_for(identity), start=1)]
    if identity.kind == "vendor" or identity.role == "user":
        lines.append("To send a new invoice, just attach the PDF or photo here.")
    if multilingual:
        lines.append("Or simply type your question, in English, தமிழ், తెలుగు or हिंदी.")
    else:
        lines.append("Or simply type your question.")
    return "\n".join(lines)


def _norm(text: str) -> str:
    return re.sub(r"[!.,\s]+", " ", (text or "").strip().lower()).strip()


def is_greeting(text: str) -> bool:
    t = _norm(text)
    if not t:
        return False
    if t in GREETING_WORDS:
        return True
    # "hi sir", "hello madam", "hi menu"
    words = t.split()
    return len(words) <= 3 and words[0] in GREETING_WORDS and all(
        w in GREETING_WORDS or w in {"sir", "madam", "mam", "ji", "anna", "akka", "bro", "team", "there"}
        for w in words[1:])


_NUMBER_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
                 "onnu": 1, "rendu": 2, "moonu": 3, "ek": 1, "do": 2, "teen": 3, "okati": 1}


def parse_choice(text: str) -> Optional[int]:
    t = _norm(text)
    m = re.fullmatch(r"(?:option|no|number|#)?\s*(\d{1,2})", t)
    if m:
        return int(m.group(1))
    return _NUMBER_WORDS.get(t)


def resolve_choice(identity: Identity, choice: int) -> Tuple[Optional[str], Optional[str]]:
    """Returns (request_to_run, question_to_ask); both None if the number isn't on the menu."""
    items = menu_for(identity)
    if 1 <= choice <= len(items):
        item = items[choice - 1]
        return item.request, item.ask
    return None, None
