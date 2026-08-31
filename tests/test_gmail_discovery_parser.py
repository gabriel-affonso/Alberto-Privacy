from datetime import datetime, timezone

from app.gmail_discovery.parser import aggregate_discovered_services, parse_sender, sender_domain
from app.gmail_discovery.types import GmailMessageMetadata


def test_parse_sender_and_domain() -> None:
    display_name, sender_email = parse_sender("Example Support <support@mail.example.com>")

    assert display_name == "Example Support"
    assert sender_email == "support@mail.example.com"
    assert sender_domain(sender_email) == "mail.example.com"


def test_aggregate_discovered_services_deduplicates_by_domain() -> None:
    messages = [
        GmailMessageMetadata(
            message_id="1",
            sender="Example <welcome@example.com>",
            subject="Welcome",
            date=datetime(2025, 1, 1, tzinfo=timezone.utc),
            matched_query="welcome",
        ),
        GmailMessageMetadata(
            message_id="2",
            sender="Example Security <security@example.com>",
            subject="Password reset",
            date=datetime(2025, 2, 1, tzinfo=timezone.utc),
            matched_query="password reset",
        ),
    ]

    services = aggregate_discovered_services(messages)

    assert len(services) == 1
    service = services[0]
    assert service.domain == "example.com"
    assert service.message_count == 2
    assert service.first_seen_at == datetime(2025, 1, 1, tzinfo=timezone.utc)
    assert service.last_seen_at == datetime(2025, 2, 1, tzinfo=timezone.utc)
    assert service.confidence_score > 0.45

