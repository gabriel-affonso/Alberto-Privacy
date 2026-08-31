from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

RequestType = Literal["article_15_access", "source_and_recipients", "advertising_profile", "deletion", "correction"]


class RequestGenerate(BaseModel):
    request_type: RequestType = "article_15_access"
    account_id: int | None = None
    include_advertising_modules: bool = False


class GdprRequestUpdate(BaseModel):
    subject: str | None = Field(default=None, max_length=500)
    body_text: str | None = None
    body_html: str | None = None
    notes: str | None = None


class GdprRequestRead(BaseModel):
    id: int
    company_id: int
    controller_resolution_id: int | None
    account_id: int | None
    request_type: str
    status: str
    subject: str | None
    body_text: str | None
    body_html: str | None
    legal_basis: str | None
    identifiers_used: list[dict[str, str]]
    template_version: str | None
    ai_model: str | None
    content_hash: str | None
    generated_at: datetime | None
    approved_at: datetime | None
    due_date: date | None = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class SendEmailResult(BaseModel):
    request_id: int
    communication_id: int
    gmail_message_id: str
    gmail_thread_id: str | None
    status: str
