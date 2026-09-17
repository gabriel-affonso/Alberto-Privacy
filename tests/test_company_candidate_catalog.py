import json
from pathlib import Path


CATALOG_PATH = Path(__file__).resolve().parents[1] / "data" / "company_candidates.json"
REQUIRED_FIELDS = {
    "brand",
    "domain",
    "category",
    "parent_company",
    "likely_controller_group",
    "priority",
    "reason_for_candidate",
    "status",
}


def load_catalog() -> dict:
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def test_catalog_has_broad_coverage() -> None:
    catalog = load_catalog()
    candidates = catalog["candidates"]
    assert len(candidates) >= 120


def test_catalog_domains_are_unique_and_normalized() -> None:
    candidates = load_catalog()["candidates"]
    domains = [candidate["domain"] for candidate in candidates]
    assert len(domains) == len(set(domains))
    assert all(domain == domain.lower() for domain in domains)
    assert all("://" not in domain and "/" not in domain for domain in domains)


def test_catalog_entries_have_required_metadata() -> None:
    candidates = load_catalog()["candidates"]
    for candidate in candidates:
        assert REQUIRED_FIELDS <= candidate.keys()
        assert candidate["priority"] in {"P1", "P2", "P3"}
        assert candidate["status"] == "candidate"
        assert candidate["brand"].strip()
        assert candidate["category"].strip()
        assert candidate["parent_company"].strip()
        assert candidate["likely_controller_group"].strip()
        assert candidate["reason_for_candidate"].strip()


def test_catalog_policy_prevents_blind_sending() -> None:
    policy = load_catalog()["policy"]
    assert policy["candidate_is_not_confirmation"] is True
    assert policy["do_not_send_automatically"] is True
    assert policy["deduplicate_by_controller_group_before_request"] is True
