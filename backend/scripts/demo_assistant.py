"""
InvoShield Assistant terminal demo (mock WhatsApp, no Meta account needed).

    cd backend
    python -m scripts.demo_assistant            # offline demo brain (English only, no API key)
    ANTHROPIC_API_KEY=sk-... python -m scripts.demo_assistant --claude   # real Claude

Uses a throw-away database, so it never touches your real data.
"""
import argparse
import os
import sys
import tempfile
import textwrap

_tmp = tempfile.mkdtemp(prefix="invoshield-demo-")
os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_tmp, 'demo.db')}"
os.environ["LOCAL_STORAGE_DIR"] = os.path.join(_tmp, "storage")
os.environ["S3_ENDPOINT_URL"] = "http://127.0.0.1:1"
os.environ["AGENT_CHANNEL_MODE"] = "mock"
os.environ.setdefault("AGENT_BUSINESS_NAME", "Sri Lakshmi Traders")
os.environ["AGENT_DEFAULT_ORGANIZATION"] = "Apex FinTech Audits"

parser = argparse.ArgumentParser()
parser.add_argument("--claude", action="store_true", help="use the Claude API (needs ANTHROPIC_API_KEY)")
args = parser.parse_args()
if args.claude:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("Set ANTHROPIC_API_KEY to use --claude.")
    os.environ["AGENT_LLM_PROVIDER"] = "anthropic"
else:
    os.environ["AGENT_LLM_PROVIDER"] = "offline"
    os.environ["ANTHROPIC_API_KEY"] = ""

import logging  # noqa: E402
logging.disable(logging.WARNING)

from app.agent.core import handle_inbound  # noqa: E402
from app.agent.llm import provider_status  # noqa: E402
from app.channels import InboundMessage, MediaRef  # noqa: E402
from app.channels.mock import MOCK_OUTBOX  # noqa: E402
from app.database.session import SessionLocal, init_db  # noqa: E402
from app.models.agent_entities import AgentContact  # noqa: E402
from app.models.entities import User  # noqa: E402

VENDOR = "+919800000001"
OWNER = "+919800000003"
INVOICE = b"""TAX INVOICE
Invoice Number: QS-2045
Date: 2026-10-20
Due Date: 2026-11-19
Vendor: Quantum Solutions LLC
Customer: Sri Lakshmi Traders
GST Number: 33AABCT1332L1Z1
Subtotal: Rs. 2,40,000.00
Tax Amount: Rs. 43,200.00
Total Amount: Rs. 2,83,500.00
"""

BLUE, GREEN, GREY, BOLD, END = "\033[94m", "\033[92m", "\033[90m", "\033[1m", "\033[0m"


def bubble(who, text, colour):
    print(f"{colour}{BOLD}{who}{END}")
    for line in text.splitlines() or [""]:
        print(textwrap.indent(textwrap.fill(line, 76) if line else "", "   "))
    print()


def send(db, sender, label, text="", attachment=None):
    msg = InboundMessage(channel="whatsapp", sender=sender, text=text)
    shown = text
    if attachment:
        msg.media.append(MediaRef(id="demo", mime_type="text/plain", filename="QS-2045.txt", data=attachment))
        shown = (text + "  " if text else "") + "[attachment QS-2045.txt]"
    bubble(f"{label}  ({sender})", shown, BLUE)
    before = len(MOCK_OUTBOX)
    result = handle_inbound(db, msg)
    if result.tool_calls:
        print(f"{GREY}   tools: " + ", ".join(f"{c['name']}({c['outcome']})" for c in result.tool_calls) + END)
    for out in MOCK_OUTBOX[before:]:
        to = "Vendor" if out["to"] == VENDOR else "Owner" if out["to"] == OWNER else out["to"]
        text = out["text"]
        if out["template"]:
            text = f"[template {out['template']}] " + ", ".join(out["template_params"])
        if out["buttons"]:
            text += "\n" + "  ".join(f"[{t}]" for _, t in out["buttons"])
        bubble(f"Assistant -> {to}", text, GREEN)


def main():
    init_db()
    db = SessionLocal()
    reviewer = db.query(User).filter(User.email == "reviewer@invoshield.ai").first()
    db.add_all([
        AgentContact(organization=reviewer.organization, display_name="Ravi (Quantum Solutions)", kind="vendor",
                     vendor_name="Quantum Solutions LLC", phone_e164=VENDOR, verified=True),
        AgentContact(organization=reviewer.organization, display_name="Owner", kind="staff",
                     user_id=reviewer.id, phone_e164=OWNER, verified=True),
    ])
    db.commit()

    print(f"\n{BOLD}InvoShield Assistant demo{END}  (brain: {provider_status()['provider']}, channel: mock WhatsApp)\n")
    send(db, VENDOR, "Vendor", "Hi")
    send(db, VENDOR, "Vendor", "sending this month's bill", INVOICE)
    send(db, VENDOR, "Vendor", "payment kab milega?")
    send(db, OWNER, "Owner", "vanakkam")
    send(db, OWNER, "Owner", "1")
    send(db, OWNER, "Owner", "Quantum Solutions ko kitna dena hai?")
    send(db, OWNER, "Owner", "Approve QS-2045")
    send(db, OWNER, "Owner", "YES")
    send(db, VENDOR, "Vendor", "bill aaya kya? status?")
    send(db, "+919812345678", "Unknown number", "What's my payment status?")
    db.close()


if __name__ == "__main__":
    main()
