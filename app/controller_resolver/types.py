from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class EvidenceItem:
    field: str
    value: str
    source_url: str
    excerpt: str
    retrieved_at: datetime | None = None


@dataclass(frozen=True)
class FetchedPage:
    url: str
    status_code: int
    title: str
    text: str
    links: list[str] = field(default_factory=list)


@dataclass
class ControllerResolutionResult:
    brand: str
    domain: str
    controller_name: str
    controller_country: str
    privacy_policy_url: str
    privacy_request_url: str
    dpo_contact: str
    request_method: str
    confidence: float
    evidence: list[EvidenceItem]
    queried_at: datetime
    controller_address: str = ""
    conflicts: list[dict[str, str]] = field(default_factory=list)


class PageFetcher(Protocol):
    def fetch(self, url: str) -> FetchedPage | None:
        ...


class ControllerTextInterpreter(Protocol):
    def interpret(
        self, domain: str, pages: list[FetchedPage], existing: ControllerResolutionResult
    ) -> ControllerResolutionResult:
        ...
