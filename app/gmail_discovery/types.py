from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class GmailMessageMetadata:
    message_id: str
    sender: str | None
    subject: str | None
    date: datetime | None
    matched_query: str


@dataclass
class DiscoveredService:
    domain: str
    company_name: str
    sender_email: str
    subject: str | None
    first_seen_at: datetime | None
    last_seen_at: datetime | None
    message_count: int
    confidence_score: float
    matched_queries: set[str] = field(default_factory=set)


class GmailClient(Protocol):
    def search_message_ids(self, query: str, max_results: int) -> Iterable[str]:
        ...

    def get_message_metadata(self, message_id: str, matched_query: str) -> GmailMessageMetadata:
        ...
