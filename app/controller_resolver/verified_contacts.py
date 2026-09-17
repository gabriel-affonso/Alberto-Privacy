"""Load manually verified privacy/contact overrides.

The catalogs are evidence for controller resolution only. They never authorize or send a
GDPR request; the normal DRAFT -> APPROVED -> send/portal workflow remains unchanged.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.controller_resolver.parser import normalize_domain
from app.controller_resolver.types import ControllerResolutionResult, EvidenceItem

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_VERIFIED_CONTACTS_PATH = PROJECT_ROOT / "data" / "verified_privacy_contacts.json"
SUPPLEMENTAL_VERIFIED_CONTACTS_PATHS = (
    PROJECT_ROOT / "data" / "verified_privacy_contacts_confirmed.json",
)
ALLOWED_METHODS = {"email", "form", "portal"}

# A few discovered sender domains are transport/subdomain aliases of services already
# represented in the original verified catalog. Keep this deliberately small and auditable.
VERIFIED_DOMAIN_ALIASES = {
    "fs.flixbus.com": "flixbus.pt",
    "flixbus.com": "flixbus.pt",
}


def _lookup_paths(path: Path) -> tuple[Path, ...]:
    if path == DEFAULT_VERIFIED_CONTACTS_PATH:
        return (DEFAULT_VERIFIED_CONTACTS_PATH, *SUPPLEMENTAL_VERIFIED_CONTACTS_PATHS)
    return (path,)


def _record_domains(record: dict[str, Any]) -> set[str]:
    values = [record.get("domain"), *(record.get("aliases") or [])]
    return {
        normalize_domain(str(value))
        for value in values
        if value and str(value).strip()
    }


def verified_contact_for_domain(
    domain: str, path: Path = DEFAULT_VERIFIED_CONTACTS_PATH
) -> dict[str, Any] | None:
    """Return a verified contact record for *domain*, if one exists.

    The default lookup searches both the original P1 catalog and supplemental verified
    contacts gathered later from confirmed Gmail evidence. A custom path remains isolated
    for tests and maintenance tasks.
    """
    normalized = normalize_domain(domain)
    normalized = VERIFIED_DOMAIN_ALIASES.get(normalized, normalized)

    for candidate_path in _lookup_paths(path):
        if not candidate_path.exists():
            continue

        payload = json.loads(candidate_path.read_text(encoding="utf-8"))
        contacts = payload.get("contacts")
        if not isinstance(contacts, list):
            raise ValueError(f"{candidate_path} does not contain a contacts list")

        for record in contacts:
            if not isinstance(record, dict):
                continue
            if normalized in _record_domains(record):
                return record
    return None


def verified_resolution_for_domain(
    domain: str, path: Path = DEFAULT_VERIFIED_CONTACTS_PATH
) -> ControllerResolutionResult | None:
    """Convert a verified catalog entry into a controller-resolution result."""
    record = verified_contact_for_domain(domain, path)
    if record is None:
        return None

    method = str(record.get("request_method") or "").strip().lower()
    if method not in ALLOWED_METHODS:
        raise ValueError(f"Invalid verified request_method for {domain}: {method!r}")

    dpo_contact = str(record.get("dpo_contact") or "").strip()
    request_url = str(record.get("privacy_request_url") or "").strip()
    if method == "email" and (not dpo_contact or "@" not in dpo_contact):
        raise ValueError(f"Verified email method for {domain} has no valid email contact")
    if method in {"form", "portal"} and not request_url.startswith("https://"):
        raise ValueError(f"Verified {method} method for {domain} has no HTTPS request URL")

    verified_at = _parse_datetime(record.get("verified_at"))
    sources = [
        str(source).strip()
        for source in (record.get("official_sources") or [])
        if str(source).strip().startswith("https://")
    ]
    if not sources:
        raise ValueError(f"Verified contact for {domain} has no official HTTPS source")

    evidence: list[EvidenceItem] = []
    fields = {
        "controller_name": str(record.get("controller_name") or ""),
        "controller_country": str(record.get("controller_country") or ""),
        "privacy_policy_url": str(record.get("privacy_policy_url") or ""),
        "privacy_request_url": request_url,
        "dpo_contact": dpo_contact,
        "request_method": method,
    }
    for field, value in fields.items():
        if not value:
            continue
        if field == "privacy_request_url" and request_url:
            field_source = request_url
        elif field == "dpo_contact":
            # Some companies publish the rights mailbox on a secondary official
            # privacy page/PDF, which is stored last in official_sources.
            field_source = sources[-1]
        else:
            field_source = sources[0]
        evidence.append(
            EvidenceItem(
                field=field,
                value=value,
                source_url=field_source,
                excerpt=(
                    "Manually verified from official first-party privacy material; "
                    f"catalog verification timestamp {verified_at.isoformat()}."
                ),
                retrieved_at=verified_at,
            )
        )

    return ControllerResolutionResult(
        brand=str(record.get("brand") or ""),
        domain=normalize_domain(str(record.get("domain") or domain)),
        controller_name=str(record.get("controller_name") or ""),
        controller_country=str(record.get("controller_country") or ""),
        controller_address=str(record.get("controller_address") or ""),
        privacy_policy_url=str(record.get("privacy_policy_url") or ""),
        privacy_request_url=request_url,
        dpo_contact=dpo_contact,
        request_method=method,
        confidence=float(record.get("confidence", 0.0)),
        evidence=evidence,
        queried_at=datetime.now(timezone.utc),
        conflicts=[],
    )


def _parse_datetime(value: object) -> datetime:
    if not isinstance(value, str) or not value.strip():
        return datetime.now(timezone.utc)
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed
