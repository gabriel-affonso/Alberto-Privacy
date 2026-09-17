from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CompanyBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    domain: str | None = Field(default=None, max_length=255)
    website: str | None = Field(default=None, max_length=500)
    privacy_email: str | None = Field(default=None, max_length=255)
    notes: str | None = None


class CompanyCreate(CompanyBase):
    pass


class CompanyUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    domain: str | None = Field(default=None, max_length=255)
    website: str | None = Field(default=None, max_length=500)
    privacy_email: str | None = Field(default=None, max_length=255)
    notes: str | None = None


class CompanyRead(CompanyBase):
    id: int
    discovery_source: str | None = None
    discovery_confidence_score: float | None = None
    discovery_first_seen_at: datetime | None = None
    discovery_last_seen_at: datetime | None = None
    discovery_message_count: int
    discovery_raw_domain: str | None = None
    discovery_canonical_domain: str | None = None
    discovery_classification: str | None = None
    discovery_relationship: str | None = None
    discovery_likely_controller: str | None = None
    discovery_requires_controller_review: bool = False
    discovery_dsar_eligible: bool = False
    discovery_classification_reason: str | None = None
    controller_name: str | None = None
    controller_country: str | None = None
    controller_address: str | None = None
    privacy_policy_url: str | None = None
    privacy_request_url: str | None = None
    dpo_contact: str | None = None
    request_method: str | None = None
    resolver_confidence: float | None = None
    last_resolved_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
