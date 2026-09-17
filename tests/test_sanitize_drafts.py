from sqlalchemy import select

from app.core.config import Settings
from app.gmail_discovery.constants import GMAIL_DISCOVERY_SOURCE
from app.gdpr_request_generator.service import generate_request
from app.models.account import Account
from app.models.company import Company
from app.models.gdpr_request import GdprRequest
from scripts.sanitize_drafts import sanitize


def _settings(tmp_path) -> Settings:
    return Settings(
        privacy_user_full_name="Ada Example",
        privacy_user_preferred_email="ada@example.test",
        privacy_data_root=str(tmp_path / "cases"),
    )


def test_sanitizer_clears_sender_identifier_refreshes_safe_and_quarantines_legacy(
    db_session,
    tmp_path,
):
    safe = Company(
        name="CORE",
        domain="core.ac.uk",
        discovery_source=GMAIL_DISCOVERY_SOURCE,
        discovery_classification="CONFIRMED",
        discovery_dsar_eligible=True,
        request_method="email",
        dpo_contact="data-protection@open.ac.uk",
    )
    legacy = Company(name="Legacy", domain="legacy.example")
    db_session.add_all([safe, legacy])
    db_session.flush()

    account = Account(
        company_id=safe.id,
        label="CORE",
        discovery_source=GMAIL_DISCOVERY_SOURCE,
        discovery_sender_email="theteam@core.ac.uk",
        account_identifier="theteam@core.ac.uk",
    )
    db_session.add(account)
    db_session.commit()

    safe_request = generate_request(
        db_session,
        safe,
        _settings(tmp_path),
        "article_15_access",
        account.id,
        True,
    )
    legacy_request = generate_request(
        db_session,
        legacy,
        _settings(tmp_path),
        "article_15_access",
        None,
        False,
    )
    assert "advertising identifiers" in safe_request.body_text

    dry = sanitize(db_session, _settings(tmp_path), apply=False)
    assert dry["false_identifiers"] == 1
    assert dry["quarantine"] == 1
    assert dry["refresh"] == 1
    assert safe_request.status == "DRAFT"
    assert legacy_request.status == "DRAFT"
    assert account.account_identifier == "theteam@core.ac.uk"

    applied = sanitize(db_session, _settings(tmp_path), apply=True)
    assert applied["failed"] == 0
    db_session.refresh(safe_request)
    db_session.refresh(legacy_request)
    db_session.refresh(account)

    assert safe_request.status == "DRAFT"
    assert legacy_request.status == "QUARANTINED"
    assert legacy_request.privacy_case.status == "QUARANTINED"
    assert account.account_identifier is None
    assert safe_request.account_id == account.id
    assert "Known account identifiers" not in safe_request.body_text
    assert "advertising identifiers" not in safe_request.body_text

    drafts = db_session.scalars(
        select(GdprRequest).where(GdprRequest.status == "DRAFT")
    ).all()
    assert [item.id for item in drafts] == [safe_request.id]
