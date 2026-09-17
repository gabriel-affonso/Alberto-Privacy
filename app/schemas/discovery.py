from datetime import datetime

from pydantic import BaseModel, ConfigDict


class GmailDiscoveryRunRead(BaseModel):
    discovered_count: int


class GmailDiscoveryResultRead(BaseModel):
    company_id: int
    account_id: int | None
    domain: str
    company_name: str
    sender_email: str | None
    subject: str | None
    first_seen_at: datetime | None
    last_seen_at: datetime | None
    message_count: int
    confidence_score: float | None
    raw_domain: str | None = None
    canonical_domain: str | None = None
    classification: str | None = None
    relationship: str | None = None
    likely_controller: str | None = None
    requires_controller_review: bool = False
    dsar_eligible: bool = False
    classification_reason: str | None = None

    model_config = ConfigDict(from_attributes=True)
