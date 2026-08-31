from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ControllerEvidenceRead(BaseModel):
    field: str
    value: str
    source_url: str
    excerpt: str
    retrieved_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class ControllerResolutionRead(BaseModel):
    brand: str
    domain: str
    controller_name: str
    controller_country: str
    controller_address: str = ""
    privacy_policy_url: str
    privacy_request_url: str
    dpo_contact: str
    request_method: Literal["email", "form", "web_form", "portal", "postal", "unknown"]
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: list[ControllerEvidenceRead]
    conflicts: list[dict[str, str]] = []
    queried_at: datetime

    model_config = ConfigDict(from_attributes=True)
