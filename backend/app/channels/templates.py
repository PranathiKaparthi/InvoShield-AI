"""
WhatsApp message templates.

Outside WhatsApp's 24-hour customer-service window a business may only send pre-approved
templates. Submit these in Meta Business Manager (WhatsApp Manager -> Message templates) with
exactly these names, category UTILITY, and the same numbered variables. `render()` produces the
same text for the mock channel, the email channel and the conversation log.
"""
from typing import Dict, List

TEMPLATES: Dict[str, Dict] = {
    "invoice_received": {
        "category": "UTILITY",
        "body": "Hello {{1}}, we have received your invoice {{2}} for {{3}}. "
                "We will update you once it has been reviewed.",
        "params": ["vendor_name", "invoice_number", "amount"],
    },
    "invoice_approved": {
        "category": "UTILITY",
        "body": "Hello {{1}}, your invoice {{2}} for {{3}} has been approved by {{4}}.",
        "params": ["vendor_name", "invoice_number", "amount", "business_name"],
    },
    "invoice_needs_correction": {
        "category": "UTILITY",
        "body": "Hello {{1}}, your invoice {{2}} needs a correction: {{3}}. "
                "Please send a corrected copy by replying to this message.",
        "params": ["vendor_name", "invoice_number", "issue"],
    },
    "payment_reminder": {
        "category": "UTILITY",
        "body": "Hello {{1}}, this is a reminder that invoice {{2}} for {{3}} is due on {{4}}.",
        "params": ["name", "invoice_number", "amount", "due_date"],
    },
    "payment_processed": {
        "category": "UTILITY",
        "body": "Hello {{1}}, payment for your invoice {{2}} ({{3}}) has been processed by {{4}}.",
        "params": ["vendor_name", "invoice_number", "amount", "business_name"],
    },
    "team_follow_up": {
        "category": "UTILITY",
        "body": "Hello {{1}}, {{2}} has an update for you. Reply to this message to see it.",
        "params": ["name", "business_name"],
    },
}


def render(name: str, params: List[str]) -> str:
    body = TEMPLATES[name]["body"]
    for i, value in enumerate(params, start=1):
        body = body.replace("{{" + str(i) + "}}", str(value))
    return body
