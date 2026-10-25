"""
Poll the configured IMAP inbox and hand unread emails to the InvoShield Assistant.

    cd backend
    python -m scripts.email_poller            # once
    python -m scripts.email_poller --every 60 # keep polling every 60 seconds

Needs EMAIL_IMAP_HOST / EMAIL_IMAP_USER / EMAIL_IMAP_PASSWORD (and EMAIL_SMTP_* for replies).
"""
import argparse
import logging
import time

from app.agent.core import handle_inbound
from app.channels.email import fetch_unseen_imap
from app.database.session import SessionLocal, init_db

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("email_poller")


def poll_once() -> int:
    messages = fetch_unseen_imap()
    for inbound in messages:
        db = SessionLocal()
        try:
            handle_inbound(db, inbound)
        except Exception:
            log.exception(f"Failed to handle email from {inbound.sender}")
        finally:
            db.close()
    return len(messages)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--every", type=int, default=0, help="seconds between polls (0 = run once)")
    args = parser.parse_args()
    init_db()
    while True:
        log.info(f"Processed {poll_once()} new email(s).")
        if not args.every:
            break
        time.sleep(args.every)


if __name__ == "__main__":
    main()
