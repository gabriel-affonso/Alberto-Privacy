from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.api.routes.companies import get_controller_resolver
from app.controller_resolver.types import ControllerResolutionResult, EvidenceItem
from app.main import app


class FakeControllerResolver:
    def resolve(self, raw_domain: str) -> ControllerResolutionResult:
        return ControllerResolutionResult(
            brand="Example",
            domain=raw_domain,
            controller_name="Example Ltd",
            controller_country="Ireland",
            privacy_policy_url="https://example.com/privacy",
            privacy_request_url="https://example.com/privacy/data-rights",
            dpo_contact="dpo@example.com",
            request_method="form",
            confidence=0.91,
            evidence=[
                EvidenceItem(
                    field="controller_name",
                    value="Example Ltd",
                    source_url="https://example.com/privacy",
                    excerpt="Example Ltd is the data controller.",
                )
            ],
            queried_at=datetime(2026, 8, 28, tzinfo=timezone.utc),
        )


def test_resolve_controller_endpoint(client: TestClient) -> None:
    app.dependency_overrides[get_controller_resolver] = lambda: FakeControllerResolver()
    company_response = client.post(
        "/companies",
        json={"name": "Example", "domain": "example.com"},
    )
    assert company_response.status_code == 201
    company_id = company_response.json()["id"]

    response = client.post(f"/companies/{company_id}/resolve-controller")

    assert response.status_code == 200
    payload = response.json()
    assert payload["brand"] == "Example"
    assert payload["domain"] == "example.com"
    assert payload["controller_name"] == "Example Ltd"
    assert payload["request_method"] == "form"
    assert payload["confidence"] == 0.91
    assert payload["evidence"][0]["source_url"] == "https://example.com/privacy"


def test_resolve_controller_requires_domain_or_website(client: TestClient) -> None:
    company_response = client.post("/companies", json={"name": "No Domain Ltd"})
    assert company_response.status_code == 201
    company_id = company_response.json()["id"]

    response = client.post(f"/companies/{company_id}/resolve-controller")

    assert response.status_code == 422
    assert "domain or website" in response.json()["detail"]


def test_get_latest_resolved_controller(client: TestClient) -> None:
    app.dependency_overrides[get_controller_resolver] = lambda: FakeControllerResolver()
    company = client.post("/companies", json={"name": "Example", "domain": "example.com"}).json()
    assert client.post(f"/companies/{company['id']}/resolve-controller").status_code == 200

    response = client.get(f"/companies/{company['id']}/controller")

    assert response.status_code == 200
    assert response.json()["controller_name"] == "Example Ltd"
