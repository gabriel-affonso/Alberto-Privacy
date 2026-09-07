"""Evidence-led GDPR request drafts. Generation never sends a message."""

from datetime import datetime, timezone
from hashlib import sha256

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.controller_resolver.verified_contacts import verified_contact_for_domain
from app.core.config import Settings
from app.gmail_discovery.classification import CONFIRMED
from app.gmail_discovery.constants import GMAIL_DISCOVERY_SOURCE
from app.models.account import Account
from app.models.company import Company
from app.models.controller_resolution import ControllerResolution
from app.models.gdpr_request import GdprRequest
from app.models.privacy_case import CaseEvent, PrivacyCase

TEMPLATE_VERSION = "article-15-v1"
ARTICLE_15_ITEMS = [
    "confirmation whether personal data concerning me is being processed",
    "a copy of my personal data",
    "the categories of personal data concerned and the purposes of processing",
    "the legal basis where applicable, the source of data not collected directly from me, and recipients or categories of recipients",
    "the envisaged retention period or criteria used to determine it",
    "information about profiling, automated decision-making, and international transfers",
    "the rights available to me in relation to this processing",
]
ADVERTISING_ITEMS = [
    "advertising identifiers, inferred interests, custom audiences, uploaded customer lists, and off-platform activity",
    "third-party data sources, data partners, recipients, and lead-generation information",
]

# Advertising-specific Article 15 questions are useful for services that operate
# large advertising, profiling, marketplace or recommendation ecosystems. They are
# intentionally not included for every confirmed controller (for example CORE,
# Porkbun, ORCID or a university).
ADVERTISING_MODULE_DOMAINS = {
    "aliexpress.com",
    "amazon.com",
    "facebook.com",
    "google.com",
    "instagram.com",
    "shein.com",
    "spotify.com",
    "temu.com",
    "uber.com",
}


def generate_request(
    db: Session,
    company: Company,
    settings: Settings,
    request_type: str,
    account_id: int | None,
    include_advertising_modules: bool,
) -> GdprRequest:
    if not settings.privacy_user_full_name or not settings.privacy_user_preferred_email:
        raise ValueError("Set PRIVACY_USER_FULL_NAME and PRIVACY_USER_PREFERRED_EMAIL before generating a request")
    _assert_standard_article_15_framework(company, request_type)
    account = db.get(Account, account_id) if account_id else None
    if account_id and (account is None or account.company_id != company.id):
        raise ValueError("Account does not belong to this company")
    _assert_gmail_target(company, account)

    resolution = _latest_resolution(db, company.id)
    identifiers = _identifiers(account, settings)
    recipient = (resolution.controller_name if resolution else None) or company.name
    subject, body = _draft_text(recipient, settings, request_type, identifiers, include_advertising_modules)
    now = datetime.now(timezone.utc)
    request = GdprRequest(
        company_id=company.id,
        account_id=account.id if account else None,
        controller_resolution_id=resolution.id if resolution else None,
        request_type=request_type,
        status="DRAFT",
        subject=subject,
        body_text=body,
        legal_basis="GDPR Article 15",
        identifiers_used=identifiers,
        template_version=TEMPLATE_VERSION,
        generated_at=now,
    )
    db.add(request)
    db.flush()
    privacy_case = PrivacyCase(
        company_id=company.id,
        gdpr_request_id=request.id,
        request_type=request_type,
        status="DRAFT",
    )
    db.add(privacy_case)
    db.flush()
    db.add(
        CaseEvent(
            case_id=privacy_case.id,
            event_type="request_generated",
            to_status="DRAFT",
            note=f"Template {TEMPLATE_VERSION}",
        )
    )
    db.commit()
    db.refresh(request)
    return request


def refresh_draft(
    db: Session,
    request: GdprRequest,
    settings: Settings,
    account: Account | None,
    include_advertising_modules: bool,
) -> GdprRequest:
    """Rebuild a DRAFT from current controller evidence without creating a new case.

    This is deliberately unavailable for APPROVED/SENT requests. It is used by the
    maintenance workflow after controller resolution or discovery cleanup.
    """
    if request.status != "DRAFT":
        raise ValueError("Only DRAFT requests can be refreshed")
    if not settings.privacy_user_full_name or not settings.privacy_user_preferred_email:
        raise ValueError("Set PRIVACY_USER_FULL_NAME and PRIVACY_USER_PREFERRED_EMAIL before refreshing a request")

    company = request.company
    _assert_standard_article_15_framework(company, request.request_type)
    if account is not None and account.company_id != company.id:
        raise ValueError("Account does not belong to this company")
    _assert_gmail_target(company, account)

    resolution = _latest_resolution(db, company.id)
    identifiers = _identifiers(account, settings)
    recipient = (resolution.controller_name if resolution else None) or company.name
    subject, body = _draft_text(
        recipient,
        settings,
        request.request_type,
        identifiers,
        include_advertising_modules,
    )
    request.account_id = account.id if account else None
    request.controller_resolution_id = resolution.id if resolution else None
    request.subject = subject
    request.body_text = body
    request.legal_basis = "GDPR Article 15"
    request.identifiers_used = identifiers
    request.template_version = TEMPLATE_VERSION
    request.generated_at = datetime.now(timezone.utc)
    request.approved_at = None
    request.content_hash = None
    db.commit()
    db.refresh(request)
    return request


def should_include_advertising_modules(company: Company) -> bool:
    domain = (company.discovery_canonical_domain or company.domain or "").lower().strip(".")
    return any(domain == root or domain.endswith("." + root) for root in ADVERTISING_MODULE_DOMAINS)


def _assert_gmail_target(company: Company, account: Account | None) -> None:
    gmail_derived = company.discovery_source == GMAIL_DISCOVERY_SOURCE or (
        account is not None and account.discovery_source == GMAIL_DISCOVERY_SOURCE
    )
    if not gmail_derived:
        return
    if company.discovery_classification != CONFIRMED or not company.discovery_dsar_eligible:
        raise ValueError(
            "Gmail-discovered evidence is not a confirmed DSAR target; review the discovery classification/controller first"
        )
    if company.discovery_requires_controller_review:
        raise ValueError(
            "Gmail discovery indicates a processor-mediated relationship; resolve the likely controller before drafting a request"
        )


def _latest_resolution(db: Session, company_id: int) -> ControllerResolution | None:
    return db.scalars(
        select(ControllerResolution)
        .where(ControllerResolution.company_id == company_id)
        .order_by(ControllerResolution.queried_at.desc(), ControllerResolution.id.desc())
    ).first()


def _assert_standard_article_15_framework(company: Company, request_type: str) -> None:
    if request_type != "article_15_access" or not company.domain:
        return
    record = verified_contact_for_domain(company.domain)
    if record is None or record.get("standard_gdpr_article_15_template", True) is not False:
        return
    framework = str(record.get("legal_framework") or "a controller-specific legal framework")
    raise ValueError(
        f"{company.name} is not a standard GDPR Article 15 template target; use {framework} instead"
    )


def update_draft(db: Session, request: GdprRequest, values: dict[str, object]) -> GdprRequest:
    if request.status != "DRAFT":
        raise ValueError("Only DRAFT requests can be edited")
    for field, value in values.items():
        setattr(request, field, value)
    db.commit()
    db.refresh(request)
    return request


def approve_request(db: Session, request: GdprRequest) -> GdprRequest:
    if request.status != "DRAFT":
        raise ValueError("Only DRAFT requests can be approved")
    if not request.subject or not request.body_text:
        raise ValueError("A request needs a subject and body before approval")
    _assert_standard_article_15_framework(request.company, request.request_type)
    _assert_gmail_target(request.company, request.account)
    now = datetime.now(timezone.utc)
    request.status = "APPROVED"
    request.approved_at = now
    request.content_hash = _content_hash(request.subject, request.body_text)
    privacy_case = request.privacy_case
    if privacy_case is None:
        raise ValueError("Request has no case")
    privacy_case.status = "APPROVED"
    privacy_case.approved_at = now
    db.add(
        CaseEvent(
            case_id=privacy_case.id,
            event_type="status_changed",
            from_status="DRAFT",
            to_status="APPROVED",
            note="Request approved",
        )
    )
    db.commit()
    db.refresh(request)
    return request


def _draft_text(
    recipient: str,
    settings: Settings,
    request_type: str,
    identifiers: list[dict[str, str]],
    include_advertising: bool,
) -> tuple[str, str]:
    if request_type != "article_15_access":
        raise ValueError("Only article_15_access generation is available in this release")
    subject = "GDPR Article 15 access request"
    identity_lines = [
        f"Name: {settings.privacy_user_full_name}",
        f"Email: {settings.privacy_user_preferred_email}",
    ]
    if settings.privacy_user_optional_phone:
        identity_lines.append(f"Phone: {settings.privacy_user_optional_phone}")
    if settings.privacy_user_country:
        identity_lines.append(f"Country: {settings.privacy_user_country}")
    known = "; ".join(
        f"{item['type']}: {item['value']}" for item in identifiers if item["type"] != "email"
    )
    requested = ARTICLE_15_ITEMS + (ADVERTISING_ITEMS if include_advertising else [])
    body = (
        f"Dear {recipient},\n\n"
        "I am exercising my right of access under Article 15 of the GDPR. Please provide the following information:\n\n"
        + "".join(f"- {item};\n" for item in requested)
        + "\nMy details for locating relevant records are:\n"
        + "\n".join(identity_lines)
        + (f"\nKnown account identifiers: {known}" if known else "")
        + "\n\nPlease respond to this email.\n\nKind regards,\n"
        + settings.privacy_user_full_name
    )
    return subject, body


def _identifiers(account: Account | None, settings: Settings) -> list[dict[str, str]]:
    values = [{"type": "email", "value": settings.privacy_user_preferred_email}]
    if not account or not account.account_identifier:
        return values

    identifier = account.account_identifier.strip()
    sender = (account.discovery_sender_email or "").strip()
    preferred = settings.privacy_user_preferred_email.strip()

    # A discovery sender such as noreply@company.com is evidence of a relationship,
    # not the user's account identifier. Also avoid duplicating the preferred email.
    if sender and identifier.casefold() == sender.casefold():
        return values
    if identifier.casefold() == preferred.casefold():
        return values

    values.append({"type": "account", "value": identifier})
    return values


def _content_hash(subject: str, body: str) -> str:
    return sha256(f"{subject}\n{body}".encode()).hexdigest()
