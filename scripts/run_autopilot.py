"""Run the safe, repeatable Privacy Agent maintenance pipeline.

This command only reads Gmail and creates/reconciles local records and DRAFT
requests. Approval, email delivery, portal submission, MFA, and CAPTCHA stay
outside the autopilot.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from sqlalchemy import select

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import models  # noqa: F401
from app.controller_resolver.resolver import ControllerResolver
from app.controller_resolver.service import resolve_controller_for_company
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.gdpr_request_generator.service import generate_request
from app.gmail_discovery.client import build_google_gmail_client
from app.gmail_discovery.service import discover_from_gmail
from app.gmail_delivery import build_google_gmail_sender
from app.gmail_requests import send_approved_request
from app.models.company import Company
from app.models.gdpr_request import GdprRequest
from app.telegram_approval import approval_allows_send, enabled as telegram_enabled, process_updates, queue_email_approval

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)


def main() -> None:
    settings = get_settings()
    summary = {"discovered": 0, "resolved": 0, "drafted": 0, "telegram_approved": 0, "telegram_notified": 0, "sent": 0, "errors": 0}
    with SessionLocal() as db:
        if telegram_enabled(settings):
            try:
                summary["telegram_approved"] = process_updates(db, settings)
            except Exception as exc:
                summary["errors"] += 1
                log.warning("Telegram approval polling failed: %s", exc)
        # Never launch OAuth from an unattended timer. Once a read token exists,
        # the normal refresh flow may run without user interaction.
        if Path(settings.gmail_oauth_token_file).is_file():
            try:
                gmail = build_google_gmail_client(settings)
                summary["discovered"] = len(discover_from_gmail(db, gmail, settings.gmail_discovery_max_results_per_query))
            except Exception as exc:  # The remaining local work must still run.
                summary["errors"] += 1
                log.warning("Gmail discovery skipped: %s", exc)
        else:
            log.info("Gmail discovery skipped: no authorized read token yet.")

        resolver = ControllerResolver(max_pages=settings.controller_resolver_max_pages)
        companies = db.scalars(
            select(Company).where(Company.last_resolved_at.is_(None)).order_by(Company.id)
        ).all()
        for company in companies:
            if not (company.domain or company.website):
                continue
            try:
                resolve_controller_for_company(db, company, resolver, settings)
                summary["resolved"] += 1
            except Exception as exc:
                summary["errors"] += 1
                log.warning("Controller resolution failed for %s: %s", company.name, exc)

        if settings.privacy_user_full_name and settings.privacy_user_preferred_email:
            for company in db.scalars(select(Company).order_by(Company.id)).all():
                existing = db.scalar(
                    select(GdprRequest.id).where(
                        GdprRequest.company_id == company.id,
                        GdprRequest.request_type == "article_15_access",
                    ).limit(1)
                )
                if existing is not None:
                    continue
                try:
                    generate_request(db, company, settings, "article_15_access", None, True)
                    summary["drafted"] += 1
                except Exception as exc:
                    summary["errors"] += 1
                    log.warning("Draft generation failed for %s: %s", company.name, exc)
        else:
            log.info("Draft generation skipped: privacy identity is incomplete.")

        if telegram_enabled(settings):
            for request in db.scalars(select(GdprRequest).where(GdprRequest.status == "DRAFT").order_by(GdprRequest.id)).all():
                try:
                    summary["telegram_notified"] += int(queue_email_approval(db, request, settings))
                except Exception as exc:
                    summary["errors"] += 1
                    log.warning("Telegram notification failed for request %s: %s", request.id, exc)

            try:
                sender = build_google_gmail_sender(settings)
                for request in db.scalars(select(GdprRequest).where(GdprRequest.status == "APPROVED").order_by(GdprRequest.id)).all():
                    if approval_allows_send(db, request.id):
                        send_approved_request(db, request, sender, settings)
                        summary["sent"] += 1
            except Exception as exc:
                summary["errors"] += 1
                log.warning("Approved email delivery skipped: %s", exc)
    log.info("Autopilot complete: %s", summary)


if __name__ == "__main__":
    main()
