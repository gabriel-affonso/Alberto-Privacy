from datetime import datetime, timezone

from app.controller_resolver.resolver import ControllerResolver
from app.controller_resolver.types import FetchedPage


class FakePageFetcher:
    def __init__(self) -> None:
        self.pages = {
            "https://example.com": FetchedPage(
                url="https://example.com",
                status_code=200,
                title="Example - Home",
                text="Example home",
                links=[
                    "https://example.com/privacy-policy",
                    "https://example.com/privacy/data-rights",
                ],
            ),
            "https://example.com/privacy": FetchedPage(
                url="https://example.com/privacy",
                status_code=200,
                title="Example Privacy Policy",
                text=(
                    "Example privacy policy. Example Ltd is the data controller. "
                    "Example Ltd is located in Ireland. Contact our Data Protection "
                    "Officer at dpo@example.com."
                ),
            ),
            "https://example.com/privacy-policy": FetchedPage(
                url="https://example.com/privacy-policy",
                status_code=200,
                title="Example Privacy Policy",
                text=(
                    "Example privacy policy. Example Ltd is the data controller. "
                    "Example Ltd is located in Ireland. Contact our Data Protection "
                    "Officer at dpo@example.com."
                ),
            ),
            "https://example.com/privacy/data-rights": FetchedPage(
                url="https://example.com/privacy/data-rights",
                status_code=200,
                title="Example Data Rights",
                text="Use this privacy rights form to submit a data subject access request.",
            ),
        }

    def fetch(self, url: str) -> FetchedPage | None:
        return self.pages.get(url)


def test_controller_resolver_extracts_evidenced_fields() -> None:
    resolver = ControllerResolver(fetcher=FakePageFetcher(), max_pages=6)

    result = resolver.resolve("example.com")

    assert result.brand == "Example"
    assert result.domain == "example.com"
    assert result.controller_name == "Example Ltd"
    assert result.controller_country == "Ireland"
    assert result.privacy_policy_url == "https://example.com/privacy"
    assert result.privacy_request_url == "https://example.com/privacy/data-rights"
    assert result.dpo_contact == "dpo@example.com"
    assert result.request_method == "form"
    assert result.confidence >= 0.8
    assert isinstance(result.queried_at, datetime)
    assert result.queried_at.tzinfo == timezone.utc
    assert {item.field for item in result.evidence} >= {
        "domain",
        "brand",
        "controller_name",
        "controller_country",
        "privacy_policy_url",
        "privacy_request_url",
        "dpo_contact",
        "request_method",
    }
    assert all(item.source_url for item in result.evidence)


def test_controller_resolver_keeps_low_confidence_when_evidence_is_sparse() -> None:
    class SparseFetcher:
        def fetch(self, url: str) -> FetchedPage | None:
            if url == "https://unknown.test":
                return FetchedPage(
                    url=url,
                    status_code=200,
                    title="Unknown",
                    text="A simple page without privacy details.",
                )
            return None

    result = ControllerResolver(fetcher=SparseFetcher(), max_pages=3).resolve("unknown.test")

    assert result.controller_name == ""
    assert result.controller_country == ""
    assert result.request_method == "unknown"
    assert result.confidence < 0.3


def test_controller_resolver_surfaces_conflicting_controller_statements() -> None:
    class ConflictingFetcher:
        def fetch(self, url: str) -> FetchedPage | None:
            if url == "https://example.test":
                return FetchedPage(url=url, status_code=200, title="Example", text="Example EU Ltd is the data controller. Example US Inc is the data controller.")
            return None

    result = ControllerResolver(fetcher=ConflictingFetcher(), max_pages=1).resolve("example.test")

    assert result.conflicts
    assert result.conflicts[0]["field"] == "controller_name"
