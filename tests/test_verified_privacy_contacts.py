import json
from pathlib import Path

from app.controller_resolver.verified_contacts import (
    DEFAULT_VERIFIED_CONTACTS_PATH,
    verified_resolution_for_domain,
)


EXPECTED_DOMAINS = {
    "aliexpress.com",
    "amazon.com",
    "bolt.eu",
    "bulk.com",
    "cardmarket.com",
    "continente.pt",
    "fnac.pt",
    "flixbus.pt",
    "glovoapp.com",
    "google.com",
    "colab.research.google.com",
    "kaggle.com",
    "lidl.pt",
    "mcdonalds.pt",
    "microsoft.com",
    "myprotein.com",
    "openai.com",
    "overleaf.com",
    "rede-expressos.pt",
    "researchgate.net",
    "samsung.com",
    "flytap.com",
    "uber.com",
    "ubereats.com",
    "whatsapp.com",
    "worten.pt",
    "zotero.org",
}


def _payload(path: Path = DEFAULT_VERIFIED_CONTACTS_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_verified_catalog_has_expected_unknown_p1_domains() -> None:
    payload = _payload()
    contacts = payload["contacts"]
    domains = {item["domain"] for item in contacts}
    assert domains == EXPECTED_DOMAINS
    assert len(domains) == len(contacts) == 27


def test_verified_catalog_has_safe_delivery_metadata_and_sources() -> None:
    contacts = _payload()["contacts"]
    for contact in contacts:
        assert contact["request_method"] in {"email", "form", "portal"}
        assert float(contact["confidence"]) >= 0.9
        assert contact["official_sources"]
        assert all(url.startswith("https://") for url in contact["official_sources"])
        if contact["request_method"] == "email":
            assert "@" in contact["dpo_contact"]
        else:
            assert contact["privacy_request_url"].startswith("https://")


def test_verified_resolution_normalizes_domain_and_builds_evidence() -> None:
    result = verified_resolution_for_domain("https://www.flixbus.pt/foo")
    assert result is not None
    assert result.domain == "flixbus.pt"
    assert result.request_method == "email"
    assert result.dpo_contact == "data.protection@flixbus.com"
    assert result.evidence
    assert all(item.source_url.startswith("https://") for item in result.evidence)


def test_form_override_does_not_become_email_method() -> None:
    result = verified_resolution_for_domain("samsung.com")
    assert result is not None
    assert result.request_method == "form"
    assert result.privacy_request_url.startswith("https://")


def test_unlisted_domain_has_no_override() -> None:
    assert verified_resolution_for_domain("example.invalid") is None
