from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.alberto_bridge.service import claim_next_job, complete_job
from app.core.config import Settings, get_settings
from app.controller_resolver.openclaw import controller_interpretation_payload
from app.controller_resolver.types import ControllerResolutionResult, FetchedPage
from app.models.alberto_job import AlbertoJob
from app.models.company import Company
from app.models.controller_resolution import ControllerResolution
from app.main import app


def test_alberto_bridge_claims_and_validates_evidenced_result(db_session) -> None:
    company = Company(name="Example")
    db_session.add(company)
    db_session.flush()
    resolution = ControllerResolution(
        company_id=company.id, brand="Example", domain="example.test", controller_name="",
        controller_country="", controller_address="", privacy_policy_url="", privacy_request_url="",
        dpo_contact="", request_method="unknown", confidence=0.1, evidence=[], conflicts=[],
        queried_at=datetime.now(timezone.utc),
    )
    db_session.add(resolution)
    db_session.flush()
    result = ControllerResolutionResult(
        brand="Example", domain="example.test", controller_name="", controller_country="", controller_address="",
        privacy_policy_url="", privacy_request_url="", dpo_contact="", request_method="unknown", confidence=0.1,
        evidence=[], conflicts=[], queried_at=resolution.queried_at,
    )
    pages = [FetchedPage(url="https://example.test/privacy", status_code=200, title="Privacy", text="Example Europe Ltd is the data controller.")]
    payload = controller_interpretation_payload(result, pages, 12000, "")
    assert payload is not None
    db_session.add(AlbertoJob(job_type="controller_resolution_interpretation", controller_resolution_id=resolution.id, payload=payload))
    db_session.commit()

    job = claim_next_job(db_session, "alberto")
    assert job is not None and job.status == "CLAIMED"
    completed = complete_job(db_session, job, {"evidence": [{"field": "controller_name", "value": "Example Europe Ltd", "source_url": "https://example.test/privacy", "excerpt": "Example Europe Ltd is the data controller."}]})

    assert completed.status == "COMPLETED"
    db_session.refresh(resolution)
    assert resolution.controller_name == "Example Europe Ltd"
    assert resolution.evidence[-1]["source_url"] == "https://example.test/privacy"


def test_alberto_result_without_matching_excerpt_is_ignored(db_session) -> None:
    company = Company(name="Example")
    db_session.add(company)
    db_session.flush()
    resolution = ControllerResolution(company_id=company.id, brand="", domain="example.test", controller_name="", controller_country="", controller_address="", privacy_policy_url="", privacy_request_url="", dpo_contact="", request_method="unknown", confidence=0.0, evidence=[], conflicts=[], queried_at=datetime.now(timezone.utc))
    db_session.add(resolution)
    db_session.flush()
    db_session.add(AlbertoJob(job_type="controller_resolution_interpretation", controller_resolution_id=resolution.id, payload={"pages": [{"url": "https://example.test/privacy", "title": "", "text": "No controller statement."}]}))
    db_session.commit()

    job = claim_next_job(db_session, "alberto")
    assert job is not None
    complete_job(db_session, job, {"evidence": [{"field": "controller_name", "value": "Invented Ltd", "source_url": "https://example.test/privacy", "excerpt": "not present"}]})
    db_session.refresh(resolution)
    assert resolution.controller_name == ""


def test_alberto_bridge_has_its_own_token(client: TestClient, db_session) -> None:
    db_session.add(AlbertoJob(job_type="controller_resolution_interpretation", payload={"pages": []}))
    db_session.commit()
    app.dependency_overrides[get_settings] = lambda: Settings(alberto_bridge_token="bridge-secret")
    try:
        assert client.post("/alberto/jobs/next").status_code == 401
        response = client.post("/alberto/jobs/next", headers={"Authorization": "Bearer bridge-secret"})
        assert response.status_code == 200
        assert response.json()["status"] == "CLAIMED"
        assert response.json()["job_type"] == "controller_resolution_interpretation"
    finally:
        app.dependency_overrides.pop(get_settings, None)
