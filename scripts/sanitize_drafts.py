"""Sanitize existing GDPR drafts after Gmail discovery/controller resolution.

Dry-run by default. With ``--apply`` this script:
- clears Gmail sender addresses that were incorrectly stored as account identifiers;
- quarantines legacy DRAFTs outside the confirmed Gmail/DSAR scope;
- refreshes confirmed DRAFTs against the latest controller resolution;
- links preserved drafts to their Gmail evidence account when needed; and
- applies advertising-specific request modules only to appropriate service domains.

It never approves or sends a privacy request.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app import models  # noqa: F401
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.gmail_discovery.constants import GMAIL_DISCOVERY_SOURCE
from app.gdpr_request_generator.service import refresh_draft, should_include_advertising_modules
from app.models.account import Account
from app.models.gdpr_request import GdprRequest
from app.models.privacy_case import CaseEvent
from scripts.draft_requests import _confirmed_draft_skip_reason

QUARANTINE_STATUS = "QUARANTINED"


def _same_email(left: str | None, right: str | None) -> bool:
    return bool(left and right and left.strip().casefold() == right.strip().casefold())


def _gmail_account(db, company_id: int) -> Account | None:
    return db.scalars(
        select(Account)
        .where(
            Account.company_id == company_id,
            Account.discovery_source == GMAIL_DISCOVERY_SOURCE,
        )
        .order_by(Account.id)
    ).first()


def _append_note(existing: str | None, note: str) -> str:
    if not existing:
        return note
    if note in existing:
        return existing
    return existing.rstrip() + "\n" + note


def _quarantine(db, request: GdprRequest, reason: str) -> None:
    note = f"Quarantined by sanitize_drafts.py: {reason}"
    request.status = QUARANTINE_STATUS
    request.notes = _append_note(request.notes, note)

    privacy_case = request.privacy_case
    if privacy_case is not None:
        previous = privacy_case.status
        privacy_case.status = QUARANTINE_STATUS
        db.add(
            CaseEvent(
                case_id=privacy_case.id,
                event_type="status_changed",
                from_status=previous,
                to_status=QUARANTINE_STATUS,
                note=note,
            )
        )
    db.commit()


def sanitize(db, settings, apply: bool = False) -> dict[str, int]:
    counters = {
        "false_identifiers": 0,
        "quarantine": 0,
        "refresh": 0,
        "failed": 0,
    }

    accounts = db.scalars(
        select(Account)
        .where(Account.discovery_source == GMAIL_DISCOVERY_SOURCE)
        .order_by(Account.id)
    ).all()
    for account in accounts:
        if _same_email(account.account_identifier, account.discovery_sender_email):
            counters["false_identifiers"] += 1
            print(
                f"CLEAR_IDENTIFIER | account#{account.id} | company#{account.company_id} | "
                f"{account.account_identifier}"
            )
            if apply:
                account.account_identifier = None
    if apply:
        db.commit()

    drafts = db.scalars(
        select(GdprRequest)
        .where(GdprRequest.status == "DRAFT")
        .order_by(GdprRequest.id)
    ).all()

    for request in drafts:
        company = request.company
        reason = _confirmed_draft_skip_reason(company)
        if reason:
            counters["quarantine"] += 1
            print(
                f"QUARANTINE      | #{request.id} | {company.name} | {company.domain or '-'} | {reason}"
            )
            if apply:
                _quarantine(db, request, reason)
            continue

        account = request.account
        if account is None or account.discovery_source != GMAIL_DISCOVERY_SOURCE:
            account = _gmail_account(db, company.id)
        if account is None:
            counters["failed"] += 1
            print(
                f"FAILED          | #{request.id} | {company.name} | sem conta/evidencia Gmail vinculada"
            )
            continue

        include_ads = should_include_advertising_modules(company)
        counters["refresh"] += 1
        print(
            f"REFRESH         | #{request.id} | {company.name} | "
            f"ads={'yes' if include_ads else 'no'} | account#{account.id}"
        )
        if apply:
            # Defensive cleanup in case an old false sender identifier survived the
            # account sweep above or was changed concurrently.
            if _same_email(account.account_identifier, account.discovery_sender_email):
                account.account_identifier = None
                db.flush()
            request.account_id = account.id
            db.flush()
            refresh_draft(
                db,
                request,
                settings,
                account,
                include_advertising_modules=include_ads,
            )

    mode = "APPLY" if apply else "DRY RUN"
    print(
        f"\n{mode}: false_identifiers={counters['false_identifiers']} "
        f"quarantine={counters['quarantine']} refresh={counters['refresh']} "
        f"failed={counters['failed']}."
    )
    print("No privacy request was approved or sent.")
    return counters


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply the cleanup. Without this flag the script is read-only.",
    )
    args = parser.parse_args()
    with SessionLocal() as db:
        sanitize(db, get_settings(), apply=args.apply)


if __name__ == "__main__":
    main()
