from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.gmail_discovery.classification import IGNORE
from app.gmail_discovery.constants import DEFAULT_DISCOVERY_QUERIES, GMAIL_DISCOVERY_SOURCE
from app.gmail_discovery.parser import aggregate_discovered_services
from app.gmail_discovery.types import DiscoveredService, GmailClient, GmailMessageMetadata
from app.models.account import Account
from app.models.company import Company


def discover_from_gmail(
    db: Session,
    gmail_client: GmailClient,
    queries: list[str] | None = None,
    max_results_per_query: int = 50,
) -> list[DiscoveredService]:
    search_queries = queries or DEFAULT_DISCOVERY_QUERIES
    messages: list[GmailMessageMetadata] = []
    messages_by_id: dict[str, GmailMessageMetadata] = {}

    for query in search_queries:
        for message_id in gmail_client.search_message_ids(query, max_results_per_query):
            if message_id in messages_by_id:
                message = messages_by_id[message_id]
                messages.append(
                    GmailMessageMetadata(
                        message_id=message.message_id,
                        sender=message.sender,
                        subject=message.subject,
                        date=message.date,
                        matched_query=query,
                    )
                )
                continue
            message = gmail_client.get_message_metadata(message_id, query)
            messages_by_id[message_id] = message
            messages.append(message)

    services = aggregate_discovered_services(messages)
    for service in services:
        save_discovered_service(db, service)

    db.commit()
    return services


def save_discovered_service(db: Session, service: DiscoveredService) -> tuple[Company, Account] | None:
    company = db.scalar(select(Company).where(Company.domain == service.domain))

    # Personal correspondence should not pollute the controller/company table. Existing
    # rows can still be classified IGNORE by the reclassification maintenance script.
    if company is None and service.classification == IGNORE:
        return None

    if company is None:
        company = Company(
            name=service.company_name,
            domain=service.domain,
            discovery_source=GMAIL_DISCOVERY_SOURCE,
        )
        db.add(company)
        db.flush()

    company.discovery_source = GMAIL_DISCOVERY_SOURCE
    company.discovery_confidence_score = service.confidence_score
    company.discovery_first_seen_at = service.first_seen_at
    company.discovery_last_seen_at = service.last_seen_at
    company.discovery_message_count = service.message_count
    company.discovery_raw_domain = service.raw_domain or service.domain
    company.discovery_canonical_domain = service.domain
    company.discovery_classification = service.classification
    company.discovery_relationship = service.relationship
    company.discovery_likely_controller = service.likely_controller
    company.discovery_requires_controller_review = service.requires_controller_review
    company.discovery_dsar_eligible = service.dsar_eligible
    company.discovery_classification_reason = service.classification_reason

    account = db.scalar(
        select(Account).where(
            Account.company_id == company.id,
            Account.discovery_source == GMAIL_DISCOVERY_SOURCE,
        )
    )
    if account is None:
        account = Account(
            company_id=company.id,
            label=service.company_name,
            discovery_source=GMAIL_DISCOVERY_SOURCE,
        )
        db.add(account)

    # The sender address is evidence about the service, not an identifier of the
    # user's account. Keep it in the dedicated discovery field and never copy it
    # into account_identifier. If a user supplied a real identifier manually, it
    # remains untouched.
    account.discovery_sender_email = service.sender_email
    account.discovery_subject = service.subject
    account.discovery_confidence_score = service.confidence_score

    return company, account


def list_gmail_discovery_results(db: Session, include_ignored: bool = False) -> list[Company]:
    query = select(Company).where(Company.discovery_source == GMAIL_DISCOVERY_SOURCE)
    if not include_ignored:
        query = query.where(
            or_(Company.discovery_classification.is_(None), Company.discovery_classification != IGNORE)
        )
    return list(
        db.scalars(
            query.order_by(
                Company.discovery_dsar_eligible.desc(),
                Company.discovery_confidence_score.desc(),
                Company.domain,
            )
        ).all()
    )
