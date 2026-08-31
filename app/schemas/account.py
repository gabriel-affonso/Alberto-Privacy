from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AccountBase(BaseModel):
    company_id: int
    label: str = Field(min_length=1, max_length=255)
    account_identifier: str | None = Field(default=None, max_length=255)
    notes: str | None = None


class AccountCreate(AccountBase):
    pass


class AccountUpdate(BaseModel):
    company_id: int | None = None
    label: str | None = Field(default=None, min_length=1, max_length=255)
    account_identifier: str | None = Field(default=None, max_length=255)
    notes: str | None = None


class AccountRead(AccountBase):
    id: int
    discovery_source: str | None = None
    discovery_sender_email: str | None = None
    discovery_subject: str | None = None
    discovery_confidence_score: float | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
