import io
import zipfile

import pytest

from app.case_manager.service import transition_case
from app.core.config import Settings
from app.gdpr_request_generator.service import approve_request, generate_request
from app.models.company import Company
from app.response_analyzer.service import ingest_response


def _settings(tmp_path) -> Settings:
    return Settings(
        privacy_user_full_name="Ada Example",
        privacy_user_preferred_email="ada@example.test",
        privacy_data_root=str(tmp_path / "cases"),
    )


def test_request_generation_approval_and_guarded_case_transitions(db_session, tmp_path) -> None:
    company = Company(name="Example", privacy_email="privacy@example.test")
    db_session.add(company)
    db_session.commit()

    request = generate_request(db_session, company, _settings(tmp_path), "article_15_access", None, True)

    assert request.status == "DRAFT"
    assert "Article 15" in request.body_text
    assert request.privacy_case.status == "DRAFT"
    approved = approve_request(db_session, request)
    assert approved.status == "APPROVED"
    assert approved.content_hash
    with pytest.raises(ValueError, match="Cannot transition"):
        transition_case(db_session, approved.privacy_case, "COMPLETED")


def test_response_ingestion_redacts_identifier_and_rejects_zip_slip(db_session, tmp_path) -> None:
    company = Company(name="Example")
    db_session.add(company)
    db_session.commit()
    request = generate_request(db_session, company, _settings(tmp_path), "article_15_access", None, False)
    case = request.privacy_case
    files = ingest_response(
        db_session, case.id, "response.txt", b"Your contact email is customer@example.test. Data sources: signup.", "text/plain", _settings(tmp_path)
    )
    assert files[0].sha256
    assert files[0].storage_path.endswith("response.txt")

    malicious = io.BytesIO()
    with zipfile.ZipFile(malicious, "w") as archive:
        archive.writestr("../outside.txt", "no")
    with pytest.raises(ValueError, match="Unsafe ZIP"):
        ingest_response(db_session, case.id, "response.zip", malicious.getvalue(), "application/zip", _settings(tmp_path))
