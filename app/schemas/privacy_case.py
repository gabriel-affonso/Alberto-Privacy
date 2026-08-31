from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class CaseTransition(BaseModel):
    status: str
    note: str | None = None
    extension_deadline: date | None = None


class CaseEventRead(BaseModel):
    id: int
    event_type: str
    from_status: str | None
    to_status: str | None
    note: str | None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class CaseRead(BaseModel):
    id: int
    company_id: int
    gdpr_request_id: int
    request_type: str
    status: str
    created_at: datetime
    approved_at: datetime | None
    sent_at: datetime | None
    acknowledged_at: datetime | None
    deadline: date | None
    completed_at: datetime | None
    extension_deadline: date | None
    extension_note: str | None
    notes: str | None
    events: list[CaseEventRead] = []
    model_config = ConfigDict(from_attributes=True)

