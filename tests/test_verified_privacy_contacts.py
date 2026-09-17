import json
from pathlib import Path

from app.controller_resolver.verified_contacts import (
    DEFAULT_VERIFIED_CONTACTS_PATH,
    SUPPLEMENTAL_VERIFIED_CONTACTS_PATHS,
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


def test_supplemental_catalog_is_structurally_safe() -> None:
    for path in SUPPLEMENTAL_VERIFIED_CONTACTS_PATHS:
        contacts = _payload(path)["contacts"]
        assert contacts
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


def test_discovered_flixbus_sender_alias_uses_existing_verified_record() -> None:
    result = verified_resolution_for_domain("fs.flixbus.com")
    assert result is not None
    assert result.domain == "flixbus.pt"
    assert result.dpo_contact == "data.protection@flixbus.com"


def test_supplemental_aliases_resolve_to_canonical_verified_contacts() -> None:
    surfshark = verified_resolution_for_domain("info.surfshark.com")
    xiaomi = verified_resolution_for_domain("notice.xiaomi.com")
    eu_login = verified_resolution_for_domain("nomail.ec.europa.eu")

    assert surfshark is not None and surfshark.domain == "surfshark.com"
    assert surfshark.dpo_contact == "support@surfshark.com"
    assert xiaomi is not None and xiaomi.domain == "mi.com"
    assert xiaomi.request_method == "form"
    assert eu_login is not None and eu_login.domain == "ec.europa.eu"
    assert eu_login.dpo_contact.lower() == "data-protection-officer@ec.europa.eu"


def test_form_override_does_not_become_email_method() -> None:
    result = verified_resolution_for_domain("samsung.com")
    assert result is not None
    assert result.request_method == "form"
    assert result.privacy_request_url.startswith("https://")


def test_new_confirmed_targets_have_verified_resolution() -> None:
    expected = {
        "apple.com": "portal",
        "core.ac.uk": "email",
        "activision.com": "email",
        "cloudflare.com": "email",
        "uc.pt": "email",
        "infineon.com": "email",
        "mckinsey.com": "email",
        "n26.com": "form",
        "porkbun.com": "email",
        "shein.com": "email",
    }
    for domain, method in expected.items():
        result = verified_resolution_for_domain(domain)
        assert result is not None, domain
        assert result.request_method == method, domain


def test_unlisted_domain_has_no_override() -> None:
    assert verified_resolution_for_domain("example.invalid") is None
