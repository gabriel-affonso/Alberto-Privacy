from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AlbertoJobRead(BaseModel):
    id: int
    job_type: str
    status: str
    payload: dict[str, Any]
    claimed_at: datetime | None
    attempts: int


class AlbertoJobSummary(BaseModel):
    pending: int
    claimed: int
    completed: int
    rejected: int
    failed: int


class AlbertoJobCompletion(BaseModel):
    result: dict[str, Any] | None = None
    error: str | None = Field(default=None, max_length=1000)
