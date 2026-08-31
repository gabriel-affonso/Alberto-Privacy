from collections.abc import Iterable
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.api.routes.discovery import get_gmail_client
from app.gmail_discovery.types import GmailMessageMetadata
from app.main import app


class FakeGmailClient:
    def __init__(self) -> None:
        self.ids_by_query = {
            "welcome": ["m1", "m2"],
            "verify your email": ["m1"],
            "confirm your account": [],
            "password reset": ["m3"],
            "your account": [],
            "registration": [],
        }
        self.messages = {
            "m1": GmailMessageMetadata(
                message_id="m1",
                sender="Example <welcome@example.com>",
                subject="Welcome to Example",
                date=datetime(2024, 1, 1, tzinfo=timezone.utc),
                matched_query="welcome",
            ),
            "m2": GmailMessageMetadata(
                message_id="m2",
                sender="Example <security@example.com>",
                subject="Verify your email",
                date=datetime(2024, 1, 5, tzinfo=timezone.utc),
                matched_query="welcome",
            ),
            "m3": GmailMessageMetadata(
                message_id="m3",
                sender="Other Service <no-reply@other.test>",
                subject="Password reset",
                date=datetime(2024, 2, 1, tzinfo=timezone.utc),
                matched_query="password reset",
            ),
        }

    def search_message_ids(self, query: str, max_results: int) -> Iterable[str]:
        return self.ids_by_query[query][:max_results]

    def get_message_metadata(self, message_id: str, matched_query: str) -> GmailMessageMetadata:
        message = self.messages[message_id]
        return GmailMessageMetadata(
            message_id=message.message_id,
            sender=message.sender,
            subject=message.subject,
            date=message.date,
            matched_query=matched_query,
        )


def test_gmail_discovery_endpoint_saves_companies_and_accounts(client: TestClient) -> None:
    app.dependency_overrides[get_gmail_client] = lambda: FakeGmailClient()

    response = client.post("/discovery/gmail")
    assert response.status_code == 200
    assert response.json() == {"discovered_count": 2}

    results_response = client.get("/discovery/results")
    assert results_response.status_code == 200
    results = results_response.json()

    assert {result["domain"] for result in results} == {"example.com", "other.test"}
    example = next(result for result in results if result["domain"] == "example.com")
    assert example["company_name"] == "Example"
    assert example["sender_email"] == "welcome@example.com"
    assert example["subject"] == "Welcome to Example"
    assert example["message_count"] == 2
    assert example["confidence_score"] > 0.45

    companies_response = client.get("/companies")
    assert companies_response.status_code == 200
    assert {company["domain"] for company in companies_response.json()} == {
        "example.com",
        "other.test",
    }

    accounts_response = client.get("/accounts")
    assert accounts_response.status_code == 200
    assert len(accounts_response.json()) == 2

