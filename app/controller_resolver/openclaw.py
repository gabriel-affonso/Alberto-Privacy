"""Validation shared by the restricted Alberto bridge.

This module deliberately has no OpenClaw client, subprocess call, Gateway URL, or Gateway token.
Alberto owns its own Gateway; this application only accepts a validated result from the bridge.
"""

from dataclasses import replace
from typing import Any

from app.controller_resolver.types import ControllerResolutionResult, EvidenceItem, FetchedPage

CONTROLLER_INTERPRETATION_FIELDS = (
    "controller_name",
    "controller_country",
    "dpo_contact",
    "privacy_request_url",
)


def missing_interpretation_fields(result: ControllerResolutionResult) -> list[str]:
    return [field for field in CONTROLLER_INTERPRETATION_FIELDS if not getattr(result, field)]


def controller_interpretation_payload(
    result: ControllerResolutionResult,
    pages: list[FetchedPage],
    max_input_chars: int,
    model: str,
) -> dict[str, Any] | None:
    missing_fields = missing_interpretation_fields(result)
    if not missing_fields or not pages:
        return None
    return {
        "domain": result.domain,
        "missing_fields": missing_fields,
        "model_hint": model,
        "instruction": (
            "Extract only values explicitly supported by the supplied public page text. "
            "Do not browse and do not infer missing facts. For every populated value, return evidence "
            "with its source_url and an exact excerpt from that source."
        ),
        "pages": [
            {"url": page.url, "title": page.title, "text": page.text[:max_input_chars]}
            for page in pages
        ],
        "output_schema": {
            "controller_name": "string", "controller_country": "string", "dpo_contact": "string",
            "privacy_request_url": "string",
            "evidence": [{"field": "string", "value": "string", "source_url": "string", "excerpt": "string"}],
        },
    }


def merge_controller_interpretation(
    existing: ControllerResolutionResult,
    interpreted: dict[str, object],
    pages: list[FetchedPage],
) -> ControllerResolutionResult:
    fields = {field: getattr(existing, field) for field in CONTROLLER_INTERPRETATION_FIELDS}
    evidence = list(existing.evidence)
    pages_by_url = {page.url: page for page in pages}

    for item in interpreted.get("evidence", []):
        if not isinstance(item, dict):
            continue
        field, value = str(item.get("field", "")), str(item.get("value", ""))
        source_url, excerpt = str(item.get("source_url", "")), str(item.get("excerpt", ""))
        source_page = pages_by_url.get(source_url)
        if field not in fields or fields[field] or not value or source_page is None or not excerpt:
            continue
        if excerpt.lower() not in source_page.text.lower():
            continue
        fields[field] = value
        evidence.append(EvidenceItem(field, value, source_url, excerpt, existing.queried_at))

    confidence = min(0.85, existing.confidence + 0.08 * (len(evidence) - len(existing.evidence)))
    return replace(
        existing,
        controller_name=fields["controller_name"], controller_country=fields["controller_country"],
        dpo_contact=fields["dpo_contact"], privacy_request_url=fields["privacy_request_url"],
        confidence=round(confidence, 2), evidence=evidence,
    )
