from app.core.config import Settings
from app.gdpr_request_generator.service import generate_request
from app.models.company import Company
from app.models.telegram_approval import TelegramApproval
from app.telegram_approval import process_updates, queue_email_approval
from app.gmail_requests import send_approved_request
import pytest


class _Response:
    def __init__(self, body):
        self.body = body

    def json(self):
        return self.body


class _Telegram:
    def __init__(self):
        self.callbacks = []
        self.sent = []

    def post(self, url, json, timeout):
        if url.endswith("sendMessage"):
            self.sent.append(json)
            return _Response({"ok": True, "result": {"message_id": 42}})
        if url.endswith("getUpdates"):
            return _Response({"ok": True, "result": self.callbacks})
        return _Response({"ok": True, "result": True})


def test_telegram_callback_is_a_one_time_approval_gate(db_session, tmp_path) -> None:
    company = Company(name="Example", privacy_email="privacy@example.test")
    db_session.add(company)
    db_session.commit()
    settings = Settings(
        privacy_user_full_name="Ada Example",
        privacy_user_preferred_email="ada@example.test",
        privacy_data_root=str(tmp_path / "cases"),
        telegram_bot_token="bot-token",
        telegram_approval_chat_id="123",
    )
    request = generate_request(db_session, company, settings, "article_15_access", None, False)
    telegram = _Telegram()

    assert queue_email_approval(db_session, request, settings, telegram)
    callback_data = telegram.sent[0]["reply_markup"]["inline_keyboard"][0][0]["callback_data"]
    approval = db_session.query(TelegramApproval).one()
    assert callback_data.rsplit(":", 1)[-1] != approval.token_hash

    telegram.callbacks = [{
        "update_id": 10,
        "callback_query": {"id": "cb-1", "data": callback_data, "message": {"chat": {"id": 123}}},
    }]
    assert process_updates(db_session, settings, telegram) == 1
    db_session.refresh(request)
    db_session.refresh(approval)
    assert request.status == "APPROVED"
    assert approval.status == "APPROVED"

    # The same callback cannot approve, send, or change the request a second time.
    assert process_updates(db_session, settings, telegram) == 0


def test_telegram_enabled_blocks_send_without_its_approval(db_session, tmp_path) -> None:
    company = Company(name="Example", privacy_email="privacy@example.test")
    db_session.add(company)
    db_session.commit()
    settings = Settings(
        privacy_user_full_name="Ada Example", privacy_user_preferred_email="ada@example.test",
        privacy_data_root=str(tmp_path / "cases"), telegram_bot_token="bot-token", telegram_approval_chat_id="123",
    )
    request = generate_request(db_session, company, settings, "article_15_access", None, False)
    request.status = "APPROVED"  # Models an attempted bypass through a non-Telegram approval path.
    request.privacy_case.status = "APPROVED"
    db_session.commit()
    with pytest.raises(ValueError, match="Telegram approval"):
        send_approved_request(db_session, request, sender=None, settings=settings)
