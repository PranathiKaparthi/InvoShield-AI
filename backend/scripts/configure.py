"""
InvoShield setup wizard: turns the assistant from demo mode into the real thing.

    cd backend
    .\\venv\\Scripts\\Activate.ps1        (Windows)   |   source venv/bin/activate   (Mac/Linux)
    python -m scripts.configure

It asks for your keys (passwords are hidden while you type), TESTS each one, generates every
secret token itself, switches the assistant to Gemini or Claude + live WhatsApp/email, creates your own
owner login, disables the public demo logins, and writes backend/.env (and a copy in the project
root for Docker). Run it again any time to change something: press Enter to keep a value.
"""
import base64
import getpass
import imaplib
import os
import re
import secrets
import smtplib
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import httpx

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
ENV_FILES = [BACKEND / ".env", ROOT / ".env"]
EXAMPLE = ROOT / ".env.example"

DEFAULT_SECRETS = {
    "JWT_SECRET_KEY": {"", "dev_secret_key_invoshield_super_secure_jwt_token_2026_production_grade",
                       "change_this_to_a_secure_random_64_character_hex_secret_key_in_production"},
    "AES_ENCRYPTION_KEY": {"", "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY="},
    "S3_ACCESS_KEY_ID": {"", "minioadmin"},
    "S3_SECRET_ACCESS_KEY": {"", "minioadmin"},
}
DEFAULT_MODEL = "claude-sonnet-5-5"

if os.name == "nt":  # make ✓ / ₹ print correctly in PowerShell
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

GREEN, RED, YELLOW, BOLD, END = ("\033[92m", "\033[91m", "\033[93m", "\033[1m", "\033[0m") \
    if sys.stdout.isatty() else ("", "", "", "", "")


# ============================================================ .env file helpers
def parse_env(lines: List[str]) -> Dict[str, str]:
    values: Dict[str, str] = {}
    for line in lines:
        m = re.match(r"^\s*([A-Z0-9_]+)\s*=\s*(.*)$", line)
        if m:
            values[m.group(1)] = m.group(2).strip().strip('"').strip("'")
    return values


def merge_env(lines: List[str], updates: Dict[str, str]) -> List[str]:
    """Replace KEY=... lines in place (keeping comments and order); append keys that are missing."""
    out, seen = [], set()
    for line in lines:
        m = re.match(r"^\s*([A-Z0-9_]+)\s*=", line)
        if m and m.group(1) in updates:
            key = m.group(1)
            if key in seen:
                continue  # drop duplicates
            out.append(f"{key}={updates[key]}")
            seen.add(key)
        else:
            out.append(line.rstrip("\n"))
    missing = [k for k in updates if k not in seen]
    if missing:
        out += ["", "# ---- set by scripts/configure.py ----"] + [f"{k}={updates[k]}" for k in missing]
    return out


def load_template() -> List[str]:
    for path in (BACKEND / ".env", ROOT / ".env", EXAMPLE):
        if path.exists():
            return path.read_text(encoding="utf-8").splitlines()
    return []


def write_env(lines: List[str]) -> None:
    text = "\n".join(lines).rstrip() + "\n"
    for path in ENV_FILES:
        path.write_text(text, encoding="utf-8")


def new_jwt_secret() -> str:
    return secrets.token_hex(32)


def new_aes_key() -> str:
    return base64.b64encode(secrets.token_bytes(32)).decode()


def new_token(n: int = 24) -> str:
    return secrets.token_urlsafe(n)


def mask(value: str) -> str:
    return (value[:4] + "…" + value[-4:]) if value and len(value) > 12 else ("set" if value else "not set")


# ============================================================ prompts
def ask(prompt: str, default: Optional[str] = None, secret: bool = False, required: bool = False) -> str:
    shown = f" [{mask(default) if secret else default}]" if default else ""
    while True:
        raw = getpass.getpass(f"{prompt}{shown}: ") if secret else input(f"{prompt}{shown}: ")
        value = raw.strip()
        if not value and default is not None:
            return default
        if value or not required:
            return value
        print(f"{YELLOW}  This one is needed.{END}")


def yes(prompt: str, default: bool = True) -> bool:
    raw = input(f"{prompt} [{'Y/n' if default else 'y/N'}]: ").strip().lower()
    return default if not raw else raw.startswith("y")


def ok(msg: str) -> None:
    print(f"{GREEN}  ✓ {msg}{END}")


def bad(msg: str) -> None:
    print(f"{RED}  ✗ {msg}{END}")


def section(title: str) -> None:
    print(f"\n{BOLD}── {title} ──{END}")


# ============================================================ live checks
def check_anthropic(api_key: str, model: str) -> Tuple[bool, str]:
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(model=model, max_tokens=5,
                                      messages=[{"role": "user", "content": "Reply with: ok"}])
        return True, f"Claude answered using {resp.model}"
    except Exception as exc:  # show the API's own message (bad key, no credit, unknown model...)
        return False, str(exc)[:300]


GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"
_SKIP_MODEL_WORDS = ("lite", "image", "tts", "audio", "live", "embedding", "exp", "vision", "learnlm", "gemma", "robotics")


def gemini_models(api_key: str, client: Optional[httpx.Client] = None) -> Tuple[bool, List[str], str]:
    """Models this key can chat with, best default first (newest stable 'flash')."""
    client = client or httpx.Client(timeout=20)
    try:
        r = client.get(f"{GEMINI_BASE}/models", params={"pageSize": 200}, headers={"x-goog-api-key": api_key})
    except httpx.HTTPError as exc:
        return False, [], f"Could not reach Google: {exc}"
    if r.status_code != 200:
        try:
            return False, [], r.json().get("error", {}).get("message", r.text)[:300]
        except ValueError:
            return False, [], r.text[:300]
    names = [m["name"].replace("models/", "") for m in r.json().get("models", [])
             if "generateContent" in (m.get("supportedGenerationMethods") or [])
             and m.get("name", "").startswith("models/gemini")]

    def score(name: str):
        version = [float(x) for x in re.findall(r"gemini-(\d+(?:\.\d+)?)", name)] or [0.0]
        return ("flash" in name, "preview" not in name, version[0], -len(name))

    chat = [n for n in names if not any(w in n for w in _SKIP_MODEL_WORDS)]
    chat.sort(key=score, reverse=True)
    return True, chat, f"{len(chat)} chat models available"


def check_gemini(api_key: str, model: str, client: Optional[httpx.Client] = None) -> Tuple[bool, str]:
    client = client or httpx.Client(timeout=30)
    try:
        r = client.post(f"{GEMINI_BASE}/models/{model}:generateContent", headers={"x-goog-api-key": api_key},
                        json={"contents": [{"role": "user", "parts": [{"text": "Reply with: ok"}]}],
                              "generationConfig": {"maxOutputTokens": 256}})
    except httpx.HTTPError as exc:
        return False, f"Could not reach Google: {exc}"
    if r.status_code != 200:
        try:
            return False, r.json().get("error", {}).get("message", r.text)[:300]
        except ValueError:
            return False, r.text[:300]
    return True, f"Gemini answered using {model}"


def check_whatsapp(phone_number_id: str, token: str, version: str,
                   client: Optional[httpx.Client] = None) -> Tuple[bool, str]:
    client = client or httpx.Client(timeout=20)
    try:
        r = client.get(f"https://graph.facebook.com/{version}/{phone_number_id}",
                       params={"fields": "display_phone_number,verified_name"},
                       headers={"Authorization": f"Bearer {token}"})
    except httpx.HTTPError as exc:
        return False, f"Could not reach Meta: {exc}"
    if r.status_code != 200:
        try:
            return False, r.json().get("error", {}).get("message", r.text)[:300]
        except ValueError:
            return False, r.text[:300]
    data = r.json()
    return True, f"Connected to {data.get('verified_name', 'your number')} ({data.get('display_phone_number', '?')})"


def check_smtp(host: str, port: int, user: str, password: str) -> Tuple[bool, str]:
    try:
        with smtplib.SMTP(host, port, timeout=20) as smtp:
            smtp.starttls()
            smtp.login(user, password)
        return True, "Email sending works"
    except Exception as exc:
        return False, str(exc)[:300]


def check_imap(host: str, user: str, password: str) -> Tuple[bool, str]:
    try:
        with imaplib.IMAP4_SSL(host) as imap:
            imap.login(user, password)
        return True, "Inbox reading works"
    except Exception as exc:
        return False, str(exc)[:300]


# ============================================================ owner login + demo accounts
def setup_accounts(env: Dict[str, str], owner_email: str, owner_password: str, owner_name: str,
                   disable_demo: bool) -> List[str]:
    """Create/update the owner's admin login and lock the public demo accounts."""
    for k, v in env.items():
        os.environ[k] = v
    sys.path.insert(0, str(BACKEND))
    from app.core.security import get_password_hash
    from app.database.session import SessionLocal, init_db
    from app.models.entities import User

    notes = []
    init_db()
    db = SessionLocal()
    try:
        org = env["AGENT_DEFAULT_ORGANIZATION"]
        owner = db.query(User).filter(User.email == owner_email.lower()).first()
        if owner is None:
            owner = User(name=owner_name or "Owner", email=owner_email.lower(), role="admin", organization=org,
                         password_hash=get_password_hash(owner_password), must_change_password=False)
            db.add(owner)
            notes.append(f"Created owner login {owner_email} (admin, {org})")
        else:
            owner.password_hash = get_password_hash(owner_password)
            owner.role, owner.organization, owner.must_change_password = "admin", org, False
            notes.append(f"Updated owner login {owner_email} (admin, {org})")
        if disable_demo:
            for demo in db.query(User).filter(User.email.in_(
                    ["admin@invoshield.ai", "reviewer@invoshield.ai", "user@invoshield.ai"])).all():
                demo.password_hash = get_password_hash(secrets.token_urlsafe(32))
                notes.append(f"Disabled demo login {demo.email}")
        db.commit()
    finally:
        db.close()
    return notes


# ============================================================ the wizard
def main() -> None:
    lines = load_template()
    cur = parse_env(lines)
    up: Dict[str, str] = {}

    print(f"\n{BOLD}InvoShield Assistant setup{END}")
    print("Press Enter to keep the value shown in [brackets]. Secret values are hidden as you type.")

    # ---------------------------------------------------------------- business
    section("1. Your business")
    business = ask("Business name (shown to vendors)", cur.get("AGENT_BUSINESS_NAME") or None, required=True)
    org_default = cur.get("AGENT_DEFAULT_ORGANIZATION")
    if not org_default or org_default == "General":
        org_default = business
    org = ask("Organization name in the app (your owner login belongs to this)", org_default, required=True)
    up.update({"AGENT_BUSINESS_NAME": business, "AGENT_DEFAULT_ORGANIZATION": org,
               "AGENT_TIMEZONE": cur.get("AGENT_TIMEZONE") or "Asia/Kolkata"})
    if not cur.get("DATABASE_URL") or "@postgres:" in cur.get("DATABASE_URL", "") and not yes(
            "Are you running with Docker (PostgreSQL)?", default=False):
        up["DATABASE_URL"] = "sqlite:///./invoshield.db"

    # ---------------------------------------------------------------- Claude
    section("2. The assistant's brain (AI)")
    print("  1. Google Gemini  (key from https://aistudio.google.com/app/apikey)")
    print("  2. Claude by Anthropic  (key from https://console.anthropic.com -> API Keys)")
    current = "2" if (cur.get("AGENT_LLM_PROVIDER") == "anthropic" and cur.get("ANTHROPIC_API_KEY")) else "1"
    choice = ask("Which one? 1 or 2", current)
    if choice.strip() == "2":
        model = cur.get("AGENT_MODEL") or DEFAULT_MODEL
        key = cur.get("ANTHROPIC_API_KEY", "")
        while True:
            key = ask("Anthropic API key (starts with sk-ant-)", key or None, secret=True, required=True)
            model = ask("Model", model)
            good, msg = check_anthropic(key, model)
            if good:
                ok(msg)
                break
            bad(msg)
            if not yes("Try again?"):
                print(f"{YELLOW}  Saved anyway; the assistant will hand chats to your team until the key works.{END}")
                break
        up.update({"ANTHROPIC_API_KEY": key, "AGENT_MODEL": model, "AGENT_LLM_PROVIDER": "anthropic"})
    else:
        print("Note: on Google's free tier, Google may use what is sent to Gemini (your vendors' messages and\n"
              "invoice details) to improve its products. Turn on billing for the key's project to avoid that.")
        key = cur.get("GOOGLE_API_KEY", "")
        model = cur.get("GEMINI_MODEL", "")
        listed, models = False, []
        while True:
            key = ask("Google API key (starts with AIza)", key or None, secret=True, required=True)
            listed, models, msg = gemini_models(key)
            if not listed:
                bad(msg)
                if "API has not been used" in msg or "disabled" in msg:
                    print("  Enable the 'Generative Language API' for this key's project, or create the key\n"
                          "  at https://aistudio.google.com/app/apikey (it is enabled there automatically).")
                if yes("Try again?"):
                    continue
                break
            if models:
                print("  Available: " + ", ".join(models[:6]) + (" ..." if len(models) > 6 else ""))
            suggested = model if model in models else (models[0] if models else "gemini-2.5-flash")
            model = ask("Model (press Enter to use the one in brackets)", suggested)
            if model.lower() in ("y", "yes", "n", "no", "ok") or (models and model not in models and len(model) < 6):
                print(f"  Using {suggested}.")
                model = suggested
            good, msg = check_gemini(key, model)
            if good:
                ok(msg)
                break
            bad(msg)
            if "demand" in msg.lower() or "overloaded" in msg.lower() or "unavailable" in msg.lower():
                for alt in [m for m in models if m != model][:4]:
                    print(f"  That model is busy at Google right now; trying {alt} ...")
                    good, msg = check_gemini(key, alt)
                    if good:
                        model = alt
                        ok(msg)
                        break
                if good:
                    break
            if not yes("Try again?"):
                print(f"{YELLOW}  Saved anyway; the assistant will hand chats to your team until the key works.{END}")
                break
        backups = [m for m in models if m != model][:3] if listed else []
        if "gemini-flash-latest" in models and model != "gemini-flash-latest" and "gemini-flash-latest" not in backups:
            backups = (backups[:2] + ["gemini-flash-latest"])
        up.update({"GOOGLE_API_KEY": key, "GEMINI_MODEL": model, "AGENT_LLM_PROVIDER": "gemini",
                   "GEMINI_FALLBACK_MODELS": ",".join(backups)})
        if backups:
            print(f"  Backups if {model} is busy: {', '.join(backups)}")

    # ---------------------------------------------------------------- WhatsApp
    section("3. WhatsApp (Meta WhatsApp Business Cloud API)")
    print("At https://developers.facebook.com -> your app -> WhatsApp -> API Setup you'll find the\n"
          "Phone number ID and an access token. The App secret is under App settings -> Basic.")
    wa_live = False
    if yes("Connect WhatsApp now?", default=bool(cur.get("WHATSAPP_PHONE_NUMBER_ID"))):
        version = cur.get("WHATSAPP_API_VERSION") or "v21.0"
        pid, token = cur.get("WHATSAPP_PHONE_NUMBER_ID", ""), cur.get("WHATSAPP_ACCESS_TOKEN", "")
        while True:
            pid = ask("Phone number ID (digits)", pid or None, required=True)
            token = ask("Access token", token or None, secret=True, required=True)
            good, msg = check_whatsapp(pid, token, version)
            if good:
                ok(msg)
                wa_live = True
                break
            bad(msg)
            if not yes("Try again?"):
                break
        app_secret = ask("App secret", cur.get("WHATSAPP_APP_SECRET") or None, secret=True, required=True)
        verify = cur.get("WHATSAPP_VERIFY_TOKEN") or new_token()
        up.update({"WHATSAPP_PHONE_NUMBER_ID": pid, "WHATSAPP_ACCESS_TOKEN": token,
                   "WHATSAPP_APP_SECRET": app_secret, "WHATSAPP_VERIFY_TOKEN": verify,
                   "WHATSAPP_API_VERSION": version,
                   "WHATSAPP_TEMPLATE_LANGUAGE": cur.get("WHATSAPP_TEMPLATE_LANGUAGE") or "en"})

    # ---------------------------------------------------------------- Email
    section("4. Email (optional)")
    email_live = False
    if yes("Connect an email inbox too?", default=bool(cur.get("EMAIL_SMTP_HOST"))):
        print("For Gmail: turn on 2-Step Verification, then create an App Password at\n"
              "https://myaccount.google.com/apppasswords and use it below (not your normal password).")
        address = ask("Email address", cur.get("EMAIL_FROM_ADDRESS") or None, required=True)
        gmail = address.lower().endswith("@gmail.com")
        smtp_host = ask("SMTP server", cur.get("EMAIL_SMTP_HOST") or ("smtp.gmail.com" if gmail else None), required=True)
        smtp_port = int(ask("SMTP port", cur.get("EMAIL_SMTP_PORT") or "587"))
        password = ask("Email (app) password", cur.get("EMAIL_SMTP_PASSWORD") or None, secret=True, required=True)
        good, msg = check_smtp(smtp_host, smtp_port, address, password)
        (ok if good else bad)(msg)
        imap_host = ask("IMAP server (to read incoming invoices)",
                        cur.get("EMAIL_IMAP_HOST") or ("imap.gmail.com" if gmail else ""))
        if imap_host:
            good_i, msg_i = check_imap(imap_host, address, password)
            (ok if good_i else bad)(msg_i)
        email_live = good
        up.update({"EMAIL_FROM_ADDRESS": address, "EMAIL_SMTP_HOST": smtp_host, "EMAIL_SMTP_PORT": str(smtp_port),
                   "EMAIL_SMTP_USER": address, "EMAIL_SMTP_PASSWORD": password,
                   "EMAIL_IMAP_HOST": imap_host, "EMAIL_IMAP_USER": address if imap_host else "",
                   "EMAIL_IMAP_PASSWORD": password if imap_host else "",
                   "EMAIL_WEBHOOK_SECRET": cur.get("EMAIL_WEBHOOK_SECRET") or new_token()})

    # ---------------------------------------------------------------- security
    section("5. Security")
    for name, maker in (("JWT_SECRET_KEY", new_jwt_secret), ("AES_ENCRYPTION_KEY", new_aes_key),
                        ("S3_ACCESS_KEY_ID", lambda: "invoshield-" + secrets.token_hex(4)),
                        ("S3_SECRET_ACCESS_KEY", lambda: new_token(24))):
        if cur.get(name, "") in DEFAULT_SECRETS[name]:
            up[name] = maker()
    if "AES_ENCRYPTION_KEY" in up:
        print("  New encryption key generated. (GST/bank fields of earlier TEST invoices won't display any more.)")
    ok("Secret keys generated")

    going_live = wa_live or email_live
    print("\nWhen WhatsApp is live your server is reachable from the internet, so the public demo\n"
          "passwords (Admin@12345 ...) must not work any more. Create your own owner login:")
    owner_email = ask("Your login email", cur.get("BOOTSTRAP_ADMIN_EMAIL") or None, required=True)
    owner_name = ask("Your name", "Owner")
    while True:
        pw = getpass.getpass("Choose a password (10+ characters): ")
        if len(pw) >= 10 and pw == getpass.getpass("Type it again: "):
            break
        print(f"{YELLOW}  Passwords must match and be at least 10 characters.{END}")
    disable_demo = yes("Disable the demo logins (recommended)?", default=True)

    up.update({
        "AGENT_CHANNEL_MODE": "live" if going_live else "mock",
        "SEED_DEMO_USERS": "False" if disable_demo else "True",
        "APP_ENV": "production" if disable_demo else "development",
        "EXTRACTION_DEMO_FALLBACKS": "False",
        "BOOTSTRAP_ADMIN_EMAIL": "", "BOOTSTRAP_ADMIN_PASSWORD": "",
        "BOOTSTRAP_ADMIN_ORGANIZATION": org,
        "DEBUG": "False" if disable_demo else cur.get("DEBUG", "True"),
    })

    # ---------------------------------------------------------------- save
    lines = merge_env(lines, up)
    write_env(lines)
    ok("Saved backend/.env (and a copy in the project folder)")
    try:
        os.chdir(BACKEND)
        for note in setup_accounts(parse_env(lines), owner_email, pw, owner_name, disable_demo):
            ok(note)
    except Exception as exc:
        bad(f"Could not update logins: {exc}")

    # ---------------------------------------------------------------- next steps
    final = parse_env(lines)
    section("Done! Next steps")
    print("1. Restart the backend:  uvicorn app.main:app --reload --port 8000")
    print(f"2. Log in at http://localhost:5173 with {owner_email}")
    print("3. Assistant Inbox -> Contacts: add your own WhatsApp number as Staff (linked to that email)")
    if "WHATSAPP_VERIFY_TOKEN" in final and final.get("WHATSAPP_PHONE_NUMBER_ID"):
        print("4. Make the backend reachable for Meta (keep this window open):")
        print("     winget install --id Cloudflare.cloudflared      (one time, Windows)")
        print("     cloudflared tunnel --url http://localhost:8000")
        print("   It prints an https://....trycloudflare.com address. In Meta -> WhatsApp -> Configuration:")
        print("     Callback URL : https://<that address>/api/agent/webhooks/whatsapp")
        print(f"     Verify token : {final['WHATSAPP_VERIFY_TOKEN']}")
        print("     then click Verify and save, and subscribe to the 'messages' field.")
        print("5. Send 'hi' to your WhatsApp Business number from your phone.")
        print("   (Test numbers only reply to phone numbers you added under API Setup -> 'To'.)")
    if final.get("EMAIL_IMAP_HOST"):
        print("•  To read incoming invoice emails, also run:  python -m scripts.email_poller --every 60")
    if not going_live:
        print(f"{YELLOW}No channel is connected yet, so the assistant stays in test mode (Test console).{END}")


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("\nStopped.")
