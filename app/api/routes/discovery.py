from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.deps import get_db
from app.gmail_discovery.client import GmailDiscoveryConfigError, build_google_gmail_client
from app.gmail_discovery.constants import GMAIL_DISCOVERY_SOURCE
from app.gmail_discovery.service import discover_from_gmail, list_gmail_discovery_results
from app.gmail_discovery.types import GmailClient
from app.models.account import Account
from app.models.company import Company
from app.schemas.discovery import GmailDiscoveryResultRead, GmailDiscoveryRunRead

router = APIRouter(prefix="/discovery", tags=["discovery"])


def get_gmail_client(settings: Settings = Depends(get_settings)) -> GmailClient:
    try:
        return build_google_gmail_client(settings)
    except GmailDiscoveryConfigError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc


@router.post("/gmail", response_model=GmailDiscoveryRunRead)
def run_gmail_discovery(
    db: Session = Depends(get_db),
    gmail_client: GmailClient = Depends(get_gmail_client),
    settings: Settings = Depends(get_settings),
) -> GmailDiscoveryRunRead:
    discovered = discover_from_gmail(
        db,
        gmail_client,
        max_results_per_query=settings.gmail_discovery_max_results_per_query,
    )
    return GmailDiscoveryRunRead(discovered_count=len(discovered))


@router.get("/results", response_model=list[GmailDiscoveryResultRead])
def get_discovery_results(db: Session = Depends(get_db)) -> list[GmailDiscoveryResultRead]:
    companies = list_gmail_discovery_results(db)
    results: list[GmailDiscoveryResultRead] = []

    for company in companies:
        account = db.scalar(
            select(Account).where(
                Account.company_id == company.id,
                Account.discovery_source == GMAIL_DISCOVERY_SOURCE,
            )
        )
        results.append(_company_to_result(company, account))

    return results


def _company_to_result(company: Company, account: Account | None) -> GmailDiscoveryResultRead:
    return GmailDiscoveryResultRead(
        company_id=company.id,
        account_id=account.id if account else None,
        domain=company.domain or "",
        company_name=company.name,
        sender_email=account.discovery_sender_email if account else None,
        subject=account.discovery_subject if account else None,
        first_seen_at=company.discovery_first_seen_at,
        last_seen_at=company.discovery_last_seen_at,
        message_count=company.discovery_message_count,
        confidence_score=company.discovery_confidence_score,
        raw_domain=company.discovery_raw_domain,
        canonical_domain=company.discovery_canonical_domain,
        classification=company.discovery_classification,
        relationship=company.discovery_relationship,
        likely_controller=company.discovery_likely_controller,
        requires_controller_review=company.discovery_requires_controller_review,
        dsar_eligible=company.discovery_dsar_eligible,
        classification_reason=company.discovery_classification_reason,
    )
