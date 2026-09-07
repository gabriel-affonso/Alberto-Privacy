import pytest

from app.core.config import Settings
from app.gmail_discovery.constants import GMAIL_DISCOVERY_SOURCE
from app.gdpr_request_generator.service import generate_request
from app.models.account import Account
from app.models.company import Company


def _settings(tmp_path) -> Settings:
    return Settings(
        privacy_user_full_name="Ada Example",
        privacy_user_preferred_email="ada@example.test",
        privacy_data_root=str(tmp_path / "cases"),
    )


def test_probable_gmail_discovery_cannot_generate_request(db_session, tmp_path) -> None:
    company = Company(
        name="Recruiting Platform",
        domain="workable.com",
        discovery_source=GMAIL_DISCOVERY_SOURCE,
        discovery_classification="PROBABLE",
        discovery_dsar_eligible=False,
        discovery_requires_controller_review=True,
    )
    db_session.add(company)
    db_session.flush()
    account = Account(
        company_id=company.id,
        label="Recruiting Platform",
        discovery_source=GMAIL_DISCOVERY_SOURCE,
        account_identifier="notice@workable.com",
    )
    db_session.add(account)
    db_session.commit()

    with pytest.raises(ValueError, match="not a confirmed DSAR target"):
        generate_request(
            db_session,
            company,
            _settings(tmp_path),
            "article_15_access",
            account.id,
            False,
        )


def test_confirmed_direct_gmail_discovery_can_generate_draft(db_session, tmp_path) -> None:
    company = Company(
        name="Example",
        domain="example.com",
        discovery_source=GMAIL_DISCOVERY_SOURCE,
        discovery_classification="CONFIRMED",
        discovery_dsar_eligible=True,
        discovery_requires_controller_review=False,
    )
    db_session.add(company)
    db_session.flush()
    account = Account(
        company_id=company.id,
        label="Example",
        discovery_source=GMAIL_DISCOVERY_SOURCE,
        account_identifier="notice@example.com",
    )
    db_session.add(account)
    db_session.commit()

    request = generate_request(
        db_session,
        company,
        _settings(tmp_path),
        "article_15_access",
        account.id,
        False,
    )

    assert request.status == "DRAFT"
