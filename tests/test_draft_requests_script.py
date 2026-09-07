from sqlalchemy import select
import pytest

from app.core.config import Settings
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
