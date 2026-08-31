from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parseaddr, parsedate_to_datetime

from app.gmail_discovery.types import DiscoveredService, GmailMessageMetadata


@dataclass
class _CandidateAccumulator:
    domain: str
    company_name: str
    sender_email: str
    subject: str | None
    dates: list[datetime] = field(default_factory=list)
    message_ids: set[str] = field(default_factory=set)
    matched_queries: set[str] = field(default_factory=set)


def extract_header(headers: list[dict[str, str]], name: str) -> str | None:
    for header in headers:
        if header.get("name", "").lower() == name.lower():
            return header.get("value")
    return None


def parse_message_date(date_header: str | None, internal_date_ms: str | None) -> datetime | None:
    if date_header:
        try:
            return parsedate_to_datetime(date_header)
        except (TypeError, ValueError, IndexError, OverflowError):
            pass

    if internal_date_ms:
        try:
            return datetime.fromtimestamp(int(internal_date_ms) / 1000, tz=timezone.utc)
        except (TypeError, ValueError, OverflowError):
            return None

    return None


def parse_sender(sender: str | None) -> tuple[str | None, str | None]:
    if not sender:
        return None, None

    display_name, sender_email = parseaddr(sender)
    if not sender_email or "@" not in sender_email:
        return None, None

    return display_name or None, sender_email.lower()


def sender_domain(sender_email: str | None) -> str | None:
    if not sender_email or "@" not in sender_email:
        return None

    domain = sender_email.rsplit("@", 1)[1].lower().strip()
    if not domain or "." not in domain:
        return None
    return domain.removeprefix("www.")


def company_name_from_sender(display_name: str | None, domain: str) -> str:
    if display_name:
        cleaned = display_name.strip().strip('"')
        if cleaned:
            return cleaned[:255]

    root = domain.split(".")[0].replace("-", " ").replace("_", " ")
    return root.title()[:255]


def confidence_score(message_count: int, matched_query_count: int) -> float:
    score = 0.45
    score += min(message_count, 10) * 0.04
    score += min(matched_query_count, 6) * 0.04
    return round(min(score, 0.95), 2)


def aggregate_discovered_services(
    messages: Iterable[GmailMessageMetadata],
) -> list[DiscoveredService]:
    candidates: dict[str, _CandidateAccumulator] = {}

    for message in messages:
        display_name, sender_email = parse_sender(message.sender)
        domain = sender_domain(sender_email)
        if domain is None or sender_email is None:
            continue

        candidate = candidates.get(domain)
        if candidate is None:
            candidate = _CandidateAccumulator(
                domain=domain,
                company_name=company_name_from_sender(display_name, domain),
                sender_email=sender_email,
                subject=message.subject,
            )
            candidates[domain] = candidate

        candidate.message_ids.add(message.message_id)
        candidate.matched_queries.add(message.matched_query)
        if message.date is not None:
            candidate.dates.append(message.date)

    services: list[DiscoveredService] = []
    for candidate in candidates.values():
        first_seen_at = min(candidate.dates) if candidate.dates else None
        last_seen_at = max(candidate.dates) if candidate.dates else None
        message_count = len(candidate.message_ids)
        services.append(
            DiscoveredService(
                domain=candidate.domain,
                company_name=candidate.company_name,
                sender_email=candidate.sender_email,
                subject=candidate.subject,
                first_seen_at=first_seen_at,
                last_seen_at=last_seen_at,
                message_count=message_count,
                confidence_score=confidence_score(message_count, len(candidate.matched_queries)),
                matched_queries=candidate.matched_queries,
            )
        )

    return sorted(services, key=lambda service: (-service.confidence_score, service.domain))
