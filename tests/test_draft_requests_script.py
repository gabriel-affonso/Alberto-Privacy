from sqlalchemy import select
import pytest

from app.core.config import Settings
from app.gmail_discovery.constants import GMAIL_DISCOVERY_SOURCE
from app.models.account import Account
from app.models.company import Company
from app.models.gdpr_request import GdprRequest
from scripts.draft_requests import generate_missing, review, perform_action


def _confirmed_company(name: str, domain: str) -> Company:
    return Company(
        name=name,
        domain=domain,
        discovery_source=GMAIL_DISCOVERY_SOURCE,
        discovery_classification="CONFIRMED",
        discovery_dsar_eligible=True,
    )


def _gmail_account(company: Company, sender: str) -> Account:
    return Account(
        company_id=company.id,
        label=company.name,
        discovery_source=GMAIL_DISCOVERY_SOURCE,
        discovery_sender_email=sender,
    )


def test_batch_preserves_existing_and_never_approves(db_session, capsys):
    db_session.add_all([Company(name="First"), Company(name="Second")])
    db_session.commit()
    settings = Settings(
        privacy_user_full_name="Test User",
        privacy_user_preferred_email="test@example.test",
    )
    generate_missing(db_session, settings)
    requests = db_session.scalars(select(GdprRequest).order_by(GdprRequest.id)).all()
    requests[0].body_text = "User edited this draft"
    db_session.commit()
    generate_missing(db_session, settings)
    assert len(db_session.scalars(select(GdprRequest)).all()) == 2
    assert all(item.status == "DRAFT" and item.approved_at is None for item in requests)
    assert requests[0].body_text == "User edited this draft"
    review(db_session, requests[0].id)
    output = capsys.readouterr().out
    assert "User edited this draft" in output
    assert "Envio por email indisponivel" in output


def test_confirmed_only_batch_skips_probable_and_special_framework(db_session, capsys):
    confirmed = _confirmed_company("Confirmed", "example.com")
    probable = Company(
        name="Probable",
        domain="probable.example",
        discovery_source=GMAIL_DISCOVERY_SOURCE,
        discovery_classification="PROBABLE",
        discovery_dsar_eligible=False,
    )
    eu_login = _confirmed_company("Authentication Service", "nomail.ec.europa.eu")
    db_session.add_all([confirmed, probable, eu_login])
    db_session.flush()
    db_session.add_all(
        [
            _gmail_account(confirmed, "notice@example.com"),
            Account(
                company_id=probable.id,
                label="Probable",
                discovery_source=GMAIL_DISCOVERY_SOURCE,
                discovery_sender_email="notice@probable.example",
            ),
            _gmail_account(eu_login, "notice@ec.europa.eu"),
        ]
    )
    db_session.commit()

    settings = Settings(
        privacy_user_full_name="Test User",
        privacy_user_preferred_email="test@example.test",
    )
    created, preserved, skipped = generate_missing(
        db_session,
        settings,
        confirmed_only=True,
    )

    requests = db_session.scalars(select(GdprRequest)).all()
    assert created == 1
    assert preserved == 0
    assert skipped == 2
    assert len(requests) == 1
    assert requests[0].company_id == confirmed.id
    assert requests[0].account_id is not None
    output = capsys.readouterr().out
    assert "Regulation (EU) 2018/1725" in output


def test_confirmed_batch_tailors_advertising_modules(db_session):
    google = _confirmed_company("Google", "google.com")
    core = _confirmed_company("CORE", "core.ac.uk")
    db_session.add_all([google, core])
    db_session.flush()
    db_session.add_all(
        [
            _gmail_account(google, "security@google.com"),
            _gmail_account(core, "theteam@core.ac.uk"),
        ]
    )
    db_session.commit()

    settings = Settings(
        privacy_user_full_name="Test User",
        privacy_user_preferred_email="test@example.test",
    )
    created, _, _ = generate_missing(db_session, settings, confirmed_only=True)
    assert created == 2

    rows = db_session.scalars(select(GdprRequest).order_by(GdprRequest.id)).all()
    by_company = {row.company.domain: row for row in rows}
    assert "advertising identifiers" in by_company["google.com"].body_text
    assert "advertising identifiers" not in by_company["core.ac.uk"].body_text


def test_review_defaults_to_confirmed_drafts(db_session, capsys):
    confirmed = _confirmed_company("Confirmed", "example.com")
    legacy = Company(name="Legacy", domain="legacy.example")
    db_session.add_all([confirmed, legacy])
    db_session.flush()
    confirmed_account = _gmail_account(confirmed, "security@example.com")
    db_session.add(confirmed_account)
    db_session.commit()

    settings = Settings(
        privacy_user_full_name="Test User",
        privacy_user_preferred_email="test@example.test",
    )
    generate_missing(db_session, settings, confirmed_only=True)
    generate_missing(db_session, settings, confirmed_only=False)
    capsys.readouterr()

    review(db_session)
    output = capsys.readouterr().out
    assert "Confirmed" in output
    assert "Legacy" not in output


def test_send_requires_approval_and_gmail_token(db_session, tmp_path, monkeypatch):
    def no_http(*args, **kwargs):
        pytest.fail("HTTP must not run before preflight passes")

    monkeypatch.setattr("scripts.draft_requests.urlopen", no_http)
    company = Company(name="Test", request_method="email", dpo_contact="privacy@example.test")
    db_session.add(company)
    db_session.commit()
    settings = Settings(
        privacy_user_full_name="Test",
        privacy_user_preferred_email="test@example.test",
        gmail_oauth_send_token_file=str(tmp_path / "missing.json"),
    )
    generate_missing(db_session, settings)
    request = db_session.scalar(select(GdprRequest))
    with pytest.raises(ValueError, match="exige APPROVED"):
        perform_action(db_session, settings, "send", request.id)
    request.status = "APPROVED"
    db_session.commit()
    with pytest.raises(ValueError, match="Falta autorizar"):
        perform_action(db_session, settings, "send", request.id)


def test_send_rejects_unknown_delivery_method(db_session, tmp_path, monkeypatch):
    def no_http(*args, **kwargs):
        pytest.fail("HTTP must not run for an unverified delivery method")

    monkeypatch.setattr("scripts.draft_requests.urlopen", no_http)
    company = Company(name="Unknown", privacy_email="privacy@example.test", request_method="unknown")
    db_session.add(company)
    db_session.commit()
    settings = Settings(
        privacy_user_full_name="Test",
        privacy_user_preferred_email="test@example.test",
        gmail_oauth_send_token_file=str(tmp_path / "missing.json"),
    )
    generate_missing(db_session, settings)
    request = db_session.scalar(select(GdprRequest))
    request.status = "APPROVED"
    db_session.commit()

    with pytest.raises(ValueError, match="sem canal EMAIL verificado"):
        perform_action(db_session, settings, "send", request.id)
