"""Local polling and one-time confirmation gates for Telegram email approvals."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.gdpr_request_generator.service import approve_request
from app.models.gdpr_request import GdprRequest
from app.models.telegram_approval import TelegramApproval, TelegramBotState


def enabled(settings: Settings) -> bool:
    return bool(settings.telegram_bot_token and settings.telegram_approval_chat_id)


def queue_email_approval(db: Session, request: GdprRequest, settings: Settings, client: httpx.Client | None = None) -> bool:
    """Send one approval message. The raw capability token is never persisted."""
    if not enabled(settings) or request.status != "DRAFT" or not _email_recipient(request):
        return False
    if db.scalar(select(TelegramApproval).where(TelegramApproval.gdpr_request_id == request.id)):
        return False
    token = secrets.token_urlsafe(18)
    approval = TelegramApproval(gdpr_request_id=request.id, token_hash=_hash(token))
    db.add(approval)
    db.flush()
    text = _approval_text(request)
    payload = {
        "chat_id": settings.telegram_approval_chat_id,
        "text": text,
        "reply_markup": {"inline_keyboard": [[
            {"text": "✅ Aprovar e enviar", "callback_data": f"pa:a:{request.id}:{token}"},
            {"text": "❌ Recusar", "callback_data": f"pa:r:{request.id}:{token}"},
        ]]},
    }
    response = _post(settings, "sendMessage", payload, client)
    if not response.get("ok"):
        db.rollback()
        raise RuntimeError("Telegram did not accept the approval message")
    approval.notified_at = datetime.now(timezone.utc)
    approval.telegram_message_id = str(response.get("result", {}).get("message_id", ""))
    db.commit()
    return True


def process_updates(db: Session, settings: Settings, client: httpx.Client | None = None) -> int:
    """Poll only the configured chat; valid approvals immediately change to APPROVED."""
    if not enabled(settings):
        return 0
    state = db.get(TelegramBotState, 1)
    if state is None:
        state = TelegramBotState(id=1)
        db.add(state)
        db.commit()
    response = _post(settings, "getUpdates", {"offset": state.update_offset, "timeout": 0}, client)
    if not response.get("ok"):
        raise RuntimeError("Telegram updates could not be read")
    processed = 0
    for update in response.get("result", []):
        update_id = int(update.get("update_id", -1))
        state.update_offset = max(state.update_offset, update_id + 1)
        callback = update.get("callback_query") or {}
        if str((callback.get("message") or {}).get("chat", {}).get("id", "")) != settings.telegram_approval_chat_id:
            continue
        if _apply_callback(db, str(callback.get("data", ""))):
            processed += 1
        callback_id = callback.get("id")
        if callback_id:
            _post(settings, "answerCallbackQuery", {"callback_query_id": callback_id}, client)
    db.commit()
    return processed


def approval_allows_send(db: Session, request_id: int) -> bool:
    approval = db.scalar(select(TelegramApproval).where(TelegramApproval.gdpr_request_id == request_id))
    return approval is not None and approval.status == "APPROVED"


def _apply_callback(db: Session, data: str) -> bool:
    parts = data.split(":")
    if len(parts) != 4 or parts[:2] != ["pa", "a"] and parts[:2] != ["pa", "r"]:
        return False
    action, raw_id, token = parts[1:]
    if not raw_id.isdigit():
        return False
    approval = db.scalar(select(TelegramApproval).where(TelegramApproval.gdpr_request_id == int(raw_id)))
    if approval is None or approval.status != "PENDING" or not hmac.compare_digest(approval.token_hash, _hash(token)):
        return False
    now = datetime.now(timezone.utc)
    if action == "r":
        approval.status, approval.rejected_at = "REJECTED", now
        return True
    request = db.get(GdprRequest, approval.gdpr_request_id)
    if request is None:
        return False
    approval.status, approval.approved_at = "APPROVED", now
    # approve_request commits the case transition; set the gate first so the
    # request and Telegram decision are persisted in the same transaction.
    approve_request(db, request)
    return True


def _email_recipient(request: GdprRequest) -> str:
    resolution = request.controller_resolution
    method = resolution.request_method if resolution else request.company.request_method
    recipient = (resolution.dpo_contact if resolution else None) or request.company.dpo_contact or request.company.privacy_email
    return recipient if method in {"email", "unknown", None} and recipient and "@" in recipient else ""


def _approval_text(request: GdprRequest) -> str:
    return (
        "Pedido RGPD pronto para envio\n\n"
        f"Empresa: {request.company.name}\nPara: {_email_recipient(request)}\n"
        f"Assunto: {request.subject or '(sem assunto)'}\n\n"
        "Toque em ‘Aprovar e enviar’ para autorizar este email."
    )


def _post(settings: Settings, method: str, payload: dict[str, Any], client: httpx.Client | None) -> dict[str, Any]:
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/{method}"
    if client is not None:
        return client.post(url, json=payload, timeout=15).json()
    with httpx.Client() as owned_client:
        return owned_client.post(url, json=payload, timeout=15).json()


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()
