from sqlalchemy.orm import Session

from app.controller_resolver.openclaw import controller_interpretation_payload
from app.controller_resolver.resolver import ControllerResolver
from app.controller_resolver.types import ControllerResolutionResult
from app.core.config import Settings
from app.models.alberto_job import AlbertoJob
from app.models.company import Company
from app.models.controller_resolution import ControllerResolution
from app.models.controller_evidence import ControllerEvidence


def resolve_controller_for_company(
    db: Session,
    company: Company,
    resolver: ControllerResolver,
    settings: Settings | None = None,
) -> ControllerResolutionResult:
    domain = company.domain or _domain_from_website(company.website)
    if not domain:
        raise ValueError("Company must have a domain or website before controller resolution")

    if hasattr(resolver, "resolve_with_pages"):
        result, pages = resolver.resolve_with_pages(domain)
    else:  # Backwards-compatible test/dummy resolver support.
        result, pages = resolver.resolve(domain), []
    resolution = ControllerResolution(
            company_id=company.id,
            brand=result.brand,
            domain=result.domain,
            controller_name=result.controller_name,
            controller_country=result.controller_country,
            controller_address=result.controller_address,
            privacy_policy_url=result.privacy_policy_url,
            privacy_request_url=result.privacy_request_url,
            dpo_contact=result.dpo_contact,
            request_method=result.request_method,
            confidence=result.confidence,
            evidence=[
                {
                    "field": item.field,
                    "value": item.value,
                    "source_url": item.source_url,
                    "excerpt": item.excerpt,
                }
                for item in result.evidence
            ],
            conflicts=result.conflicts,
            queried_at=result.queried_at,
        )
    db.add(resolution)
    db.flush()
    for item in result.evidence:
        db.add(ControllerEvidence(
            controller_resolution_id=resolution.id, field=item.field, value=item.value,
            source_url=item.source_url, excerpt=item.excerpt, retrieved_at=item.retrieved_at or result.queried_at,
        ))
    if settings and settings.openclaw_enabled:
        payload = controller_interpretation_payload(
            result, pages, settings.openclaw_max_input_chars, settings.openclaw_model
        )
        if payload:
            db.add(AlbertoJob(
                job_type="controller_resolution_interpretation",
                controller_resolution_id=resolution.id,
                payload=payload,
            ))
    company.controller_name = result.controller_name or None
    company.controller_country = result.controller_country or None
    company.controller_address = result.controller_address or None
    company.privacy_policy_url = result.privacy_policy_url or None
    company.privacy_request_url = result.privacy_request_url or None
    company.dpo_contact = result.dpo_contact or None
    company.request_method = result.request_method
    company.resolver_confidence = result.confidence
    company.last_resolved_at = result.queried_at
    db.commit()
    db.refresh(resolution)
    return result


def _domain_from_website(website: str | None) -> str:
    if not website:
        return ""
    from app.controller_resolver.parser import normalize_domain

    return normalize_domain(website)
