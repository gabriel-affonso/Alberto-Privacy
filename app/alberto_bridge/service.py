from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.controller_resolver.openclaw import merge_controller_interpretation
from app.controller_resolver.types import ControllerResolutionResult, EvidenceItem, FetchedPage
from app.models.alberto_job import AlbertoJob
from app.models.company import Company
from app.models.controller_evidence import ControllerEvidence
from app.models.controller_resolution import ControllerResolution


def claim_next_job(db: Session, worker_name: str) -> AlbertoJob | None:
    job = db.scalars(
        select(AlbertoJob).where(AlbertoJob.status == "PENDING").order_by(AlbertoJob.created_at).limit(1)
    ).first()
    if job is None:
        return None
    job.status, job.claimed_by, job.claimed_at = "CLAIMED", worker_name, datetime.now(timezone.utc)
    db.commit()
    db.refresh(job)
    return job


def complete_job(db: Session, job: AlbertoJob, result: dict[str, Any]) -> AlbertoJob:
    if job.status != "CLAIMED":
        raise ValueError("Only a claimed job can be completed")
    if job.job_type != "controller_resolution_interpretation" or not job.controller_resolution_id:
        raise ValueError("Unsupported Alberto job type")
    resolution = db.get(ControllerResolution, job.controller_resolution_id)
    if resolution is None:
        raise ValueError("The related controller resolution no longer exists")
    pages = _pages_from_payload(job.payload)
    existing = _result_from_resolution(resolution)
    merged = merge_controller_interpretation(existing, result, pages)
    _apply_resolution_result(db, resolution, merged)
    job.status, job.result, job.completed_at = "COMPLETED", result, datetime.now(timezone.utc)
    db.commit()
    db.refresh(job)
    return job


def reject_job(db: Session, job: AlbertoJob, error: str) -> AlbertoJob:
    if job.status != "CLAIMED":
        raise ValueError("Only a claimed job can be rejected")
    job.status, job.error, job.completed_at = "REJECTED", error[:1000], datetime.now(timezone.utc)
    db.commit()
    db.refresh(job)
    return job


def _pages_from_payload(payload: dict[str, Any]) -> list[FetchedPage]:
    pages: list[FetchedPage] = []
    for item in payload.get("pages", []):
        if not isinstance(item, dict):
            continue
        url = str(item.get("url", ""))
        if url:
            pages.append(FetchedPage(url=url, status_code=200, title=str(item.get("title", "")), text=str(item.get("text", ""))))
    return pages


def _result_from_resolution(resolution: ControllerResolution) -> ControllerResolutionResult:
    timestamp = resolution.queried_at
    evidence = [
        EvidenceItem(str(item.get("field", "")), str(item.get("value", "")), str(item.get("source_url", "")), str(item.get("excerpt", "")), timestamp)
        for item in resolution.evidence if isinstance(item, dict)
    ]
    return ControllerResolutionResult(
        brand=resolution.brand, domain=resolution.domain, controller_name=resolution.controller_name,
        controller_country=resolution.controller_country, controller_address=resolution.controller_address,
        privacy_policy_url=resolution.privacy_policy_url, privacy_request_url=resolution.privacy_request_url,
        dpo_contact=resolution.dpo_contact, request_method=resolution.request_method,
        confidence=resolution.confidence, evidence=evidence, conflicts=resolution.conflicts, queried_at=timestamp,
    )


def _apply_resolution_result(db: Session, resolution: ControllerResolution, result: ControllerResolutionResult) -> None:
    previous_count = len(resolution.evidence)
    for field in ("controller_name", "controller_country", "controller_address", "privacy_request_url", "dpo_contact", "confidence"):
        setattr(resolution, field, getattr(result, field))
    resolution.evidence = [{"field": item.field, "value": item.value, "source_url": item.source_url, "excerpt": item.excerpt} for item in result.evidence]
    for item in result.evidence[previous_count:]:
        db.add(ControllerEvidence(controller_resolution_id=resolution.id, field=item.field, value=item.value, source_url=item.source_url, excerpt=item.excerpt, retrieved_at=item.retrieved_at or result.queried_at))
    company = db.get(Company, resolution.company_id)
    if company:
        company.controller_name = result.controller_name or None
        company.controller_country = result.controller_country or None
        company.controller_address = result.controller_address or None
        company.privacy_request_url = result.privacy_request_url or None
        company.dpo_contact = result.dpo_contact or None
        company.resolver_confidence = result.confidence
