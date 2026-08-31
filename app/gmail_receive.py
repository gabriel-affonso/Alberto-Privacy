"""Thread-scoped inbound Gmail handling; unrelated company mail is ignored."""

import base64
import hashlib
from datetime import datetime, timezone
from email.utils import parseaddr
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.case_manager.service import transition_case
from app.core.config import Settings
from app.models.communication import Communication
from app.models.gdpr_request import GdprRequest


def classify_message(subject: str, body: str, attachments: list[dict[str, Any]]) -> str:
    text = f"{subject}\n{body}".lower()
    if any(word in text for word in ("verify your identity", "identity verification", "proof of identity")):
        return "identity_verification"
    if any(word in text for word in ("we acknowledge", "acknowledgement", "we received your request")):
        return "acknowledgement"
    if any(word in text for word in ("extension", "additional two months", "extend the response")):
        return "extension_notice"
    if any(word in text for word in ("cannot process", "we refuse", "request rejected")):
        return "rejection"
    if attachments or any(word in text for word in ("attached", "copy of your data", "data export")):
        return "response"
    return "unrelated"


def sync_thread_responses(db: Session, request: GdprRequest, gmail_service: Any, settings: Settings) -> int:
    outbound = db.scalars(
        select(Communication).where(Communication.gdpr_request_id == request.id, Communication.direction == "OUTBOUND").order_by(Communication.sent_at.desc())
    ).first()
    if outbound is None or not outbound.gmail_thread_id:
        raise ValueError("No sent Gmail thread is available for this request")
    thread = gmail_service.users().threads().get(userId="me", id=outbound.gmail_thread_id, format="full").execute()
    stored = 0
    for message in thread.get("messages", []):
        if message.get("id") == outbound.gmail_message_id:
            continue
        if db.scalar(select(Communication).where(Communication.gmail_message_id == message.get("id"))):
            continue
        headers = {item.get("name", "").lower(): item.get("value", "") for item in message.get("payload", {}).get("headers", [])}
        sender = parseaddr(headers.get("from", ""))[1].lower()
        verified = {(request.company.dpo_contact or "").lower(), (request.company.privacy_email or "").lower()}
        if not sender or sender not in verified:
            continue
        subject = headers.get("subject", "")
        body, attachments = _payload_content(gmail_service, message.get("id", ""), message.get("payload", {}))
        if request.subject and request.subject.lower() not in subject.lower() and not headers.get("in-reply-to"):
            continue
        classification = classify_message(subject, body, attachments)
        if classification == "unrelated":
            continue
        _store_inbound(db, request, message, sender, subject, body, attachments, classification, settings)
        stored += 1
    return stored


def _payload_content(service: Any, message_id: str, payload: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    texts: list[str] = []
    attachments: list[dict[str, Any]] = []
    def walk(part: dict[str, Any]) -> None:
        body = part.get("body", {})
        mime = part.get("mimeType", "")
        if body.get("data") and mime.startswith("text/"):
            texts.append(base64.urlsafe_b64decode(body["data"] + "==").decode("utf-8", errors="replace"))
        if body.get("attachmentId"):
            attachment = service.users().messages().attachments().get(userId="me", messageId=message_id, id=body["attachmentId"]).execute()
            attachments.append({"filename": part.get("filename") or "attachment.bin", "data": base64.urlsafe_b64decode(attachment.get("data", "") + "==")})
        for child in part.get("parts", []): walk(child)
    walk(payload)
    return "\n".join(texts), attachments


def _store_inbound(db: Session, request: GdprRequest, message: dict[str, Any], sender: str, subject: str, body: str, attachments: list[dict[str, Any]], classification: str, settings: Settings) -> None:
    now = datetime.now(timezone.utc)
    path = _incoming_dir(settings, request.privacy_case.id)
    for attachment in attachments:
        data = attachment["data"]
        name = Path(attachment["filename"]).name
        (path / f"{hashlib.sha256(data).hexdigest()[:12]}-{name}").write_bytes(data)
    raw_hash = hashlib.sha256((subject + "\n" + body).encode()).hexdigest()
    db.add(Communication(gdpr_request_id=request.id, direction="INBOUND", channel="email", subject=subject, body=body, sender=sender, received_at=now, gmail_message_id=message.get("id"), gmail_thread_id=message.get("threadId"), content_hash=raw_hash))
    targets = {"acknowledgement": "ACKNOWLEDGED", "identity_verification": "NEEDS_IDENTITY_VERIFICATION", "response": "RESPONSE_RECEIVED", "rejection": "REJECTED", "extension_notice": "WAITING"}
    target = targets.get(classification)
    if target and target in {"ACKNOWLEDGED", "NEEDS_IDENTITY_VERIFICATION", "RESPONSE_RECEIVED", "REJECTED", "WAITING"}:
        try: transition_case(db, request.privacy_case, target, f"Inbound Gmail classification: {classification}")
        except ValueError: db.commit()
    else:
        db.commit()


def _incoming_dir(settings: Settings, case_id: int) -> Path:
    root = Path(settings.privacy_data_root).resolve()
    directory = (root / str(case_id) / "attachments").resolve()
    if root not in directory.parents: raise ValueError("Invalid attachment storage path")
    directory.mkdir(parents=True, exist_ok=True)
    return directory
