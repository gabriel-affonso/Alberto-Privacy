#!/usr/bin/env python3
"""Reclassify previously stored Gmail discoveries without reading Gmail.

By default this is a dry run. Pass --apply to persist classifications and copy evidence
from alias/subdomain rows to an existing canonical Company. No privacy request is
created, approved, or sent.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sqlalchemy import select

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db.session import SessionLocal
from app.gmail_discovery.classification import IGNORE, classify_discovery
from app.gmail_discovery.constants import GMAIL_DISCOVERY_SOURCE
from app.models.account import Account
from app.models.company import Company

RANK = {"IGNORE": 0, "WEAK": 1, "PROBABLE": 2, "CONFIRMED": 3}


def _min_dt(a, b):
    values = [v for v in (a, b) if v is not None]
    return min(values) if values else None


def _max_dt(a, b):
    values = [v for v in (a, b) if v is not None]
    return max(values) if values else None


def _apply_classification(company: Company, result) -> None:
    company.discovery_raw_domain = result.raw_domain
    company.discovery_canonical_domain = result.canonical_domain
    company.discovery_classification = result.classification
    company.discovery_confidence_score = result.confidence_score
    company.discovery_relationship = result.relationship
    company.discovery_likely_controller = result.likely_controller
    company.discovery_requires_controller_review = result.requires_controller_review
    company.discovery_dsar_eligible = result.dsar_eligible
    company.discovery_classification_reason = result.reason


def _copy_to_canonical(db, source: Company, account: Account, target: Company, result) -> None:
    target.discovery_source = GMAIL_DISCOVERY_SOURCE
    target.discovery_raw_domain = result.raw_domain
    target.discovery_canonical_domain = result.canonical_domain
    target.discovery_first_seen_at = _min_dt(target.discovery_first_seen_at, source.discovery_first_seen_at)
    target.discovery_last_seen_at = _max_dt(target.discovery_last_seen_at, source.discovery_last_seen_at)
    target.discovery_message_count = (target.discovery_message_count or 0) + (source.discovery_message_count or 0)

    current_rank = RANK.get(target.discovery_classification or "", -1)
    new_rank = RANK.get(result.classification, -1)
    if new_rank > current_rank or (
        new_rank == current_rank and result.confidence_score > (target.discovery_confidence_score or 0)
    ):
        _apply_classification(target, result)

    target_account = db.scalar(
        select(Account).where(
            Account.company_id == target.id,
            Account.discovery_source == GMAIL_DISCOVERY_SOURCE,
        )
    )
    if target_account is None:
        target_account = Account(
            company_id=target.id,
            label=target.name,
            discovery_source=GMAIL_DISCOVERY_SOURCE,
        )
        db.add(target_account)

    if result.confidence_score >= (target_account.discovery_confidence_score or 0):
        target_account.account_identifier = account.account_identifier
        target_account.discovery_sender_email = account.discovery_sender_email
        target_account.discovery_subject = account.discovery_subject
        target_account.discovery_confidence_score = result.confidence_score

    source.discovery_classification = IGNORE
    source.discovery_canonical_domain = result.canonical_domain
    source.discovery_dsar_eligible = False
    source.discovery_requires_controller_review = False
    source.discovery_relationship = "canonical-alias"
    source.discovery_classification_reason = (
        f"superseded by canonical discovery target {target.domain} (company_id={target.id})"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Persist changes. Default is dry-run.")
    args = parser.parse_args()

    db = SessionLocal()
    classified = 0
    aliased = 0
    counts = {"CONFIRMED": 0, "PROBABLE": 0, "WEAK": 0, "IGNORE": 0}
    try:
        rows = db.execute(
            select(Company, Account)
            .join(Account, Account.company_id == Company.id)
            .where(Account.discovery_source == GMAIL_DISCOVERY_SOURCE)
            .order_by(Company.id)
        ).all()

        for company, account in rows:
            if not company.domain:
                continue
            result = classify_discovery(
                domain=company.domain,
                company_name=company.name,
                sender_email=account.discovery_sender_email or account.account_identifier or "",
                subject=account.discovery_subject,
                message_count=company.discovery_message_count or 0,
                base_confidence=company.discovery_confidence_score or 0.45,
            )
            counts[result.classification] += 1
            classified += 1

            target = None
            if result.canonical_domain != company.domain:
                target = db.scalar(
                    select(Company).where(Company.domain == result.canonical_domain)
                )

            action = result.classification
            if target is not None and target.id != company.id:
                action += f" -> {target.domain}"
                aliased += 1
                if args.apply:
                    _copy_to_canonical(db, company, account, target, result)
            elif args.apply:
                if result.canonical_domain != company.domain and target is None:
                    company.domain = result.canonical_domain
                _apply_classification(company, result)

            print(
                f"{company.name} | {company.domain} | {action} | "
                f"eligible={result.dsar_eligible} | {result.reason}"
            )

        if args.apply:
            db.commit()
        else:
            db.rollback()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    mode = "APPLIED" if args.apply else "DRY RUN"
    print(
        f"\n{mode}: classified={classified} aliases={aliased} "
        + " ".join(f"{key}={value}" for key, value in counts.items())
    )
    print("No Gmail messages were read and no privacy request was created or sent.")


if __name__ == "__main__":
    main()
