from sqlalchemy import select
import pytest

from app.core.config import Settings
from app.gmail_discovery.constants import GMAIL_DISCOVERY_SOURCE
from app.models.account import Account
from app.models.company import Company
from app.models.gdpr_request import GdprRequest
from scripts.draft_requests import generate_missing, review, perform_action


def test_batch_preserves_existing_and_never_approves(db_session, capsys):
    db_session.add_all([Company(name="First"), Company(name="Second")])
    db_session.commit()
    settings = Settings(privacy_user_full_name="Test User", privacy_user_preferred_email="test@example.test")
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
    assert "falta destinatario" in output


def test_confirmed_only_batch_skips_probable_and_special_framework(db_session, capsys):
    confirmed = Company(
        name="Confirmed",
        domain="example.com",
        discovery_source=GMAIL_DISCOVERY_SOURCE,
        discovery_classification="CONFIRMED",
        discovery_dsar_eligible=True,
    )
    probable = Company(
        name="Probable",
        domain="probable.example",
        discovery_source=GMAIL_DISCOVERY_SOURCE,
        discovery_classification="PROBABLE",
        discovery_dsar_eligible=False,
    )
    eu_login = Company(
        name="Authentication Service",
        domain="nomail.ec.europa.eu",
        discovery_source=GMAIL_DISCOVERY_SOURCE,
        discovery_classification="CONFIRMED",
        discovery_dsar_eligible=True,
    )
    db_session.add_all([confirmed, probable, eu_login])
    db_session.flush()
    db_session.add_all([
        Account(
            company_id=confirmed.id,
            label="Confirmed",
            discovery_source=GMAIL_DISCOVERY_SOURCE,
            account_identifier="account@example.com",
        ),
        Account(
            company_id=probable.id,
            label="Probable",
            discovery_source=GMAIL_DISCOVERY_SOURCE,
            account_identifier="account@probable.example",
        ),
        Account(
            company_id=eu_login.id,
            label="EU Login",
            discovery_source=GMAIL_DISCOVERY_SOURCE,
            account_identifier="notice@ec.europa.eu",
        ),
    ])
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


def test_send_requires_approval_and_gmail_token(db_session, tmp_path, monkeypatch):
    def no_http(*args, **kwargs):
        pytest.fail("HTTP must not run before preflight passes")
    monkeypatch.setattr("scripts.draft_requests.urlopen", no_http)
    db_session.add(Company(name="Test"))
    db_session.commit()
    settings = Settings(privacy_user_full_name="Test", privacy_user_preferred_email="test@example.test",
                        gmail_oauth_send_token_file=str(tmp_path / "missing.json"))
    generate_missing(db_session, settings)
    request = db_session.scalar(select(GdprRequest))
    with pytest.raises(ValueError, match="exige APPROVED"):
        perform_action(db_session, settings, "send", request.id)
    request.status = "APPROVED"
    db_session.commit()
    with pytest.raises(ValueError, match="Falta autorizar"):
        perform_action(db_session, settings, "send", request.id)
