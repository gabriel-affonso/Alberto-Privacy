from urllib.parse import urlparse

import httpx

from app.controller_resolver.html import parse_html
from app.controller_resolver.types import FetchedPage


class HttpxPageFetcher:
    def __init__(self, timeout_seconds: float = 10.0) -> None:
        self.timeout_seconds = timeout_seconds

    def fetch(self, url: str) -> FetchedPage | None:
        try:
            with httpx.Client(
                follow_redirects=True,
                timeout=self.timeout_seconds,
                headers={"User-Agent": "privacy-agent controller-resolver/0.1"},
            ) as client:
                response = client.get(url)
        except httpx.HTTPError:
            return None

        content_type = response.headers.get("content-type", "")
        if response.status_code >= 400 or "text/html" not in content_type:
            return None

        title, text, links = parse_html(str(response.url), response.text)
        return FetchedPage(
            url=str(response.url),
            status_code=response.status_code,
            title=title,
            text=text,
            links=_dedupe_links(links),
        )


def _dedupe_links(links: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for link in links:
        parsed = urlparse(link)
        if parsed.scheme not in {"http", "https"}:
            continue
        normalized = parsed._replace(fragment="").geturl()
        if normalized not in seen:
            seen.add(normalized)
            result.append(normalized)
    return result

