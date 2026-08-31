from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.privacy_case import CaseEvent, PrivacyCase

CASE_STATUSES = {
    "DRAFT", "APPROVED", "SENT", "ACKNOWLEDGED", "WAITING", "RESPONSE_RECEIVED",
    "NEEDS_IDENTITY_VERIFICATION", "NEEDS_USER_ACTION", "PARTIALLY_COMPLETED", "COMPLETED",
    "OVERDUE", "REJECTED", "CANCELLED", "WAITING_FOR_APPROVAL",
}
TRANSITIONS = {
    "DRAFT": {"APPROVED", "CANCELLED"}, "APPROVED": {"SENT", "CANCELLED", "WAITING_FOR_APPROVAL"},
    "WAITING_FOR_APPROVAL": {"APPROVED", "CANCELLED"},
    "SENT": {"ACKNOWLEDGED", "WAITING", "RESPONSE_RECEIVED", "NEEDS_IDENTITY_VERIFICATION", "NEEDS_USER_ACTION", "OVERDUE", "REJECTED", "CANCELLED"},
    "ACKNOWLEDGED": {"WAITING", "RESPONSE_RECEIVED", "NEEDS_IDENTITY_VERIFICATION", "OVERDUE", "REJECTED", "CANCELLED"},
    "WAITING": {"RESPONSE_RECEIVED", "NEEDS_IDENTITY_VERIFICATION", "NEEDS_USER_ACTION", "OVERDUE", "REJECTED", "CANCELLED"},
    "NEEDS_IDENTITY_VERIFICATION": {"WAITING", "SENT", "CANCELLED", "OVERDUE"},
    "NEEDS_USER_ACTION": {"WAITING", "CANCELLED"}, "RESPONSE_RECEIVED": {"PARTIALLY_COMPLETED", "COMPLETED", "NEEDS_USER_ACTION", "REJECTED"},
    "PARTIALLY_COMPLETED": {"COMPLETED", "NEEDS_USER_ACTION", "CANCELLED"}, "OVERDUE": {"WAITING", "RESPONSE_RECEIVED", "COMPLETED", "REJECTED", "CANCELLED"},
    "REJECTED": {"NEEDS_USER_ACTION", "CANCELLED"}, "CANCELLED": set(), "COMPLETED": set(),
}


def transition_case(db: Session, privacy_case: PrivacyCase, target: str, note: str | None = None, extension_deadline=None) -> PrivacyCase:
    target = target.upper()
    if target not in CASE_STATUSES:
        raise ValueError("Unknown case status")
    if target not in TRANSITIONS.get(privacy_case.status, set()):
        raise ValueError(f"Cannot transition case from {privacy_case.status} to {target}")
    previous, now = privacy_case.status, datetime.now(timezone.utc)
    privacy_case.status, privacy_case.gdpr_request.status = target, target
    if target == "ACKNOWLEDGED": privacy_case.acknowledged_at = now
    if target == "COMPLETED": privacy_case.completed_at = now
    if extension_deadline:
        privacy_case.extension_deadline, privacy_case.extension_note = extension_deadline, note
    db.add(CaseEvent(case_id=privacy_case.id, event_type="status_changed", from_status=previous, to_status=target, note=note))
    db.commit(); db.refresh(privacy_case)
    return privacy_case
