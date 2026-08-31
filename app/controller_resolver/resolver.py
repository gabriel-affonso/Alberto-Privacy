from dataclasses import replace
from datetime import datetime, timezone

from app.controller_resolver.fetcher import HttpxPageFetcher
from app.controller_resolver.parser import (
    candidate_urls,
    find_brand,
    find_controller_country,
    find_controller_address,
    find_controller_name,
    find_controller_names,
    find_dpo_contact,
    find_privacy_policy_url,
    find_privacy_request_url,
    infer_request_method,
    normalize_domain,
    page_for_url,
    relevant_links,
)
from app.controller_resolver.types import (
    ControllerResolutionResult,
    EvidenceItem,
    FetchedPage,
    PageFetcher,
)


class ControllerResolver:
    def __init__(
        self,
        fetcher: PageFetcher | None = None,
        max_pages: int = 20,
    ) -> None:
        self.fetcher = fetcher or HttpxPageFetcher()
        self.max_pages = max_pages

    def resolve(self, raw_domain: str) -> ControllerResolutionResult:
        result, _ = self.resolve_with_pages(raw_domain)
        return result

    def resolve_with_pages(self, raw_domain: str) -> tuple[ControllerResolutionResult, list[FetchedPage]]:
        domain = normalize_domain(raw_domain)
        pages = self._fetch_pages(domain)
        result = self._extract(domain, pages)
        return result, pages

    def _fetch_pages(self, domain: str) -> list[FetchedPage]:
        urls = candidate_urls(domain)
        pages: list[FetchedPage] = []
        seen_urls: set[str] = set()

        for url in urls:
            if len(pages) >= self.max_pages or url in seen_urls:
                continue
            seen_urls.add(url)
            page = self.fetcher.fetch(url)
            if page is None:
                continue
            pages.append(page)
            if len(pages) == 1:
                for link in relevant_links(page, domain):
                    if link not in seen_urls:
                        urls.append(link)

        return pages

    def _extract(self, domain: str, pages: list[FetchedPage]) -> ControllerResolutionResult:
        evidence: list[EvidenceItem] = []
        if pages:
            evidence.append(EvidenceItem("domain", domain, pages[0].url, pages[0].url))

        brand = ""
        brand_evidence = find_brand(pages, domain)
        if brand_evidence:
            brand = brand_evidence.value
            evidence.append(brand_evidence)

        privacy_policy_url = ""
        policy_evidence = find_privacy_policy_url(pages)
        if policy_evidence:
            privacy_policy_url = policy_evidence.value
            evidence.append(policy_evidence)

        privacy_request_url = ""
        request_evidence = find_privacy_request_url(pages)
        if request_evidence:
            privacy_request_url = request_evidence.value
            evidence.append(request_evidence)

        dpo_contact = ""
        dpo_evidence = find_dpo_contact(pages)
        if dpo_evidence:
            dpo_contact = dpo_evidence.value
            evidence.append(dpo_evidence)

        controller_name = ""
        controller_evidence = find_controller_name(pages)
        if controller_evidence:
            controller_name = controller_evidence.value
            evidence.append(controller_evidence)

        controller_country = ""
        country_evidence = find_controller_country(pages, controller_name)
        if country_evidence:
            controller_country = country_evidence.value
            evidence.append(country_evidence)

        controller_address = ""
        address_evidence = find_controller_address(pages, controller_name)
        if address_evidence:
            controller_address = address_evidence.value
            evidence.append(address_evidence)

        conflicts: list[dict[str, str]] = []
        controller_candidates = find_controller_names(pages)
        names = {item.value for item in controller_candidates}
        if len(names) > 1:
            conflicts.append({"field": "controller_name", "values": " | ".join(sorted(names)), "reason": "Conflicting controller statements"})

        request_method = "unknown"
        method_evidence = infer_request_method(
            privacy_request_url,
            dpo_contact,
            page_for_url(pages, privacy_request_url) if privacy_request_url else None,
            dpo_evidence,
        )
        if method_evidence:
            request_method = method_evidence.value
            evidence.append(method_evidence)

        result = ControllerResolutionResult(
            brand=brand,
            domain=domain,
            controller_name=controller_name,
            controller_country=controller_country,
            controller_address=controller_address,
            privacy_policy_url=privacy_policy_url,
            privacy_request_url=privacy_request_url,
            dpo_contact=dpo_contact,
            request_method=request_method,
            confidence=0.0,
            evidence=evidence,
            conflicts=conflicts,
            queried_at=datetime.now(timezone.utc),
        )
        return replace(result, confidence=_confidence(result, pages))


def _confidence(result: ControllerResolutionResult, pages: list[FetchedPage]) -> float:
    score = 0.05 if pages else 0.0
    evidenced_fields = {item.field for item in result.evidence}
    field_weights = {
        "brand": 0.08,
        "privacy_policy_url": 0.18,
        "privacy_request_url": 0.18,
        "dpo_contact": 0.14,
        "controller_name": 0.2,
        "controller_country": 0.12,
        "request_method": 0.1,
    }
    for field, weight in field_weights.items():
        if field in evidenced_fields:
            score += weight
    return round(min(score, 0.95), 2)
