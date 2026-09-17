import pytest

from app.core.config import Settings
from app.gdpr_request_generator.service import approve_request, generate_request
from app.gmail_requests import send_approved_request
from app.models.company import Company


class NeverSend:
    def send(self, recipient: str, subject: str, body: str):
        pytest.fail("sender.send must not run for an unverified request method")


def test_unknown_request_method_cannot_send_email(db_session, tmp_path):
    company = Company(
        name="Example",
        domain="example.com",
        request_method="unknown",
        privacy_email="privacy@example.com",
    )
    db_session.add(company)
    db_session.commit()

    settings = Settings(
        privacy_user_full_name="Ada Example",
        privacy_user_preferred_email="ada@example.test",
        privacy_data_root=str(tmp_path / "cases"),
    )
    request = generate_request(
        db_session,
        company,
        settings,
        "article_15_access",
        None,
        False,
    )
    approve_request(db_session, request)

    with pytest.raises(ValueError, match="request_method=email"):
        send_approved_request(db_session, request, NeverSend(), settings)
