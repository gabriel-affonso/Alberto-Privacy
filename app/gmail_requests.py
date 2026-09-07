from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.gmail_delivery import GmailSender
from app.models.communication import Communication
from app.models.gdpr_request import GdprRequest
from app.models.privacy_case import CaseEvent


def send_approved_request(
    db: Session,
    request: GdprRequest,
    sender: GmailSender,
    settings: Settings,
) -> Communication:
    if request.status != "APPROVED" or request.privacy_case is None:
        raise ValueError("Only an APPROVED request with a case can be sent")
    if not request.subject or not request.body_text:
        raise ValueError("Request content is incomplete")
    if not settings.privacy_user_preferred_email:
        raise ValueError("A configured preferred email is required")

    resolution = request.controller_resolution
    method = resolution.request_method if resolution else request.company.request_method
    if method != "email":
        raise ValueError(
            "Email delivery requires a controller resolution explicitly verified as request_method=email"
        )

    recipient = (
        (resolution.dpo_contact if resolution else None)
        or request.company.dpo_contact
        or request.company.privacy_email
    )
    if not recipient or "@" not in recipient:
        raise ValueError("No verified email delivery contact is available")

    result = sender.send(recipient, request.subject, request.body_text)
    now = datetime.now(timezone.utc)
    raw = result.get("rfc822", b"")
    outgoing = _case_directory(settings, request.privacy_case.id, "outgoing")
    path = outgoing / f"{result.get('id', 'message')}.eml"
    path.write_bytes(raw)
    communication = Communication(
        gdpr_request_id=request.id,
        direction="OUTBOUND",
        channel="email",
        subject=request.subject,
        body=request.body_text,
        sender=settings.privacy_user_preferred_email,
        sent_at=now,
        gmail_message_id=str(result.get("id", "")),
        gmail_thread_id=result.get("threadId"),
        rfc822_path=str(path),
        content_hash=sha256(raw or request.body_text.encode()).hexdigest(),
    )
    db.add(communication)
    request.status = "SENT"
    request.due_date = (now + timedelta(days=settings.gdpr_default_deadline_days)).date()
    privacy_case = request.privacy_case
    privacy_case.status = "SENT"
    privacy_case.sent_at = now
    privacy_case.deadline = request.due_date
    db.add(
        CaseEvent(
            case_id=privacy_case.id,
            event_type="email_sent",
            from_status="APPROVED",
            to_status="SENT",
            note=f"Gmail message {result.get('id', '')}",
        )
    )
    db.commit()
    db.refresh(communication)
    return communication


def _case_directory(settings: Settings, case_id: int, branch: str) -> Path:
    root = Path(settings.privacy_data_root).resolve()
    directory = (root / str(case_id) / branch).resolve()
    if root not in directory.parents:
        raise ValueError("Invalid case storage path")
    directory.mkdir(parents=True, exist_ok=True)
    return directory
