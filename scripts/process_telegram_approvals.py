"""Poll Telegram confirmations and immediately deliver only approved requests."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from sqlalchemy import select

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import models  # noqa: F401
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.gmail_delivery import build_google_gmail_sender
from app.gmail_requests import send_approved_request
from app.models.gdpr_request import GdprRequest
from app.telegram_approval import approval_allows_send, enabled, process_updates

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)


def main() -> None:
    settings = get_settings()
    if not enabled(settings):
        log.info("Telegram approval is disabled.")
        return
    with SessionLocal() as db:
        approved = process_updates(db, settings)
        sent = 0
        if approved:
            sender = build_google_gmail_sender(settings)
            for request in db.scalars(select(GdprRequest).where(GdprRequest.status == "APPROVED")).all():
                if approval_allows_send(db, request.id):
                    send_approved_request(db, request, sender, settings)
                    sent += 1
    log.info("Telegram approvals processed=%s emails_sent=%s", approved, sent)


if __name__ == "__main__":
    main()
