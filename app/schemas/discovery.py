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

    model_config = ConfigDict(from_attributes=True)

