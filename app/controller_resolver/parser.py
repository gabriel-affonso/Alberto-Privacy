import re
from urllib.parse import urlparse

from app.controller_resolver.types import EvidenceItem, FetchedPage

COUNTRIES = [
    "Austria",
    "Belgium",
    "Brazil",
    "Bulgaria",
    "Canada",
    "Croatia",
    "Cyprus",
    "Czech Republic",
    "Denmark",
    "Estonia",
    "Finland",
    "France",
    "Germany",
    "Greece",
    "Hungary",
    "Iceland",
    "Ireland",
    "Italy",
    "Latvia",
    "Liechtenstein",
    "Lithuania",
    "Luxembourg",
    "Malta",
    "Netherlands",
    "Norway",
    "Poland",
    "Portugal",
    "Romania",
    "Slovakia",
    "Slovenia",
    "Spain",
    "Sweden",
    "Switzerland",
    "United Kingdom",
    "United States",
]

EMAIL_PATTERN = re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")
CONTROLLER_PATTERNS = [
    re.compile(
        r"(?:data controller|controller)\s+(?:is|for this processing is|of your personal data is)\s+([^.\n]{3,160})",
        re.IGNORECASE,
    ),
    re.compile(r"([^.\n]{3,160})\s+is\s+the\s+data\s+controller", re.IGNORECASE),
]
ADDRESS_PATTERNS = [
    re.compile(r"(?:registered office|address|located at)(?:\s+is)?\s*:?\s*([^\n.]{8,240})", re.IGNORECASE),
]

PRIVACY_POLICY_KEYWORDS = ["privacy policy", "privacy notice"]
PRIVACY_REQUEST_KEYWORDS = [
    "privacy center",
    "data rights",
    "privacy rights",
    "gdpr",
    "access request",
    "data subject",
    "subject access",
    "delete your data",
    "request your data",
]
DPO_KEYWORDS = ["data protection officer", " dpo", "privacy@"]


def link_belongs_to_domain(link: str, domain: str) -> bool:
    host = urlparse(link).netloc.lower().split("@")[-1].split(":")[0]
    return host == domain or host.endswith(f".{domain}")


def normalize_domain(raw_domain: str) -> str:
    candidate = raw_domain.strip().lower()
    if "://" not in candidate:
        candidate = f"https://{candidate}"
    parsed = urlparse(candidate)
    domain = parsed.netloc or parsed.path
    return domain.split("@")[-1].split(":")[0].removeprefix("www.")


def candidate_urls(domain: str) -> list[str]:
    base = f"https://{domain}"
    www_base = f"https://www.{domain}"
    paths = [
        "",
        "/privacy",
        "/privacy-policy",
        "/privacy-center",
        "/privacy/privacy-policy",
        "/legal/privacy",
        "/legal/privacy-policy",
        "/privacy/data-rights",
        "/privacy/rights",
        "/gdpr",
        "/data-rights",
    ]
    urls = [f"{base}{path}" for path in paths]
    urls.extend([www_base, f"{www_base}/privacy", f"{www_base}/privacy-policy"])
    return urls


def relevant_links(home_page: FetchedPage, domain: str, limit: int = 12) -> list[str]:
    matches: list[str] = []
    keywords = PRIVACY_POLICY_KEYWORDS + PRIVACY_REQUEST_KEYWORDS + DPO_KEYWORDS
    for link in home_page.links:
        if not link_belongs_to_domain(link, domain):
            continue
        searchable = link.lower().replace("-", " ").replace("_", " ")
        if any(keyword in searchable for keyword in keywords):
            matches.append(link)
    return _dedupe(matches)[:limit]


def find_privacy_policy_url(pages: list[FetchedPage]) -> EvidenceItem | None:
    return _find_url_evidence(pages, "privacy_policy_url", PRIVACY_POLICY_KEYWORDS)


def find_privacy_request_url(pages: list[FetchedPage]) -> EvidenceItem | None:
    return _find_url_evidence(pages, "privacy_request_url", PRIVACY_REQUEST_KEYWORDS)


def find_brand(pages: list[FetchedPage], domain: str) -> EvidenceItem | None:
    for page in pages:
        if page.title:
            brand = _clean_title(page.title, domain)
            if brand:
                return EvidenceItem("brand", brand[:255], page.url, page.title[:500])
    return None


def find_dpo_contact(pages: list[FetchedPage]) -> EvidenceItem | None:
    for page in pages:
        for email in EMAIL_PATTERN.findall(page.text):
            excerpt = excerpt_around(page.text, email)
            if _contains_any(excerpt.lower(), DPO_KEYWORDS):
                return EvidenceItem("dpo_contact", email, page.url, excerpt)
    return None


def find_controller_name(pages: list[FetchedPage]) -> EvidenceItem | None:
    matches = find_controller_names(pages)
    return matches[0] if matches else None


def find_controller_names(pages: list[FetchedPage]) -> list[EvidenceItem]:
    results: list[EvidenceItem] = []
    seen: set[str] = set()
    for page in pages:
        for pattern in CONTROLLER_PATTERNS:
            for match in pattern.finditer(page.text):
                value = _clean_controller(match.group(1))
                if value and value.lower() not in seen:
                    seen.add(value.lower())
                    results.append(EvidenceItem("controller_name", value[:500], page.url, excerpt_around(page.text, value)))
    return results


def find_controller_address(pages: list[FetchedPage], controller_name: str) -> EvidenceItem | None:
    if not controller_name:
        return None
    for page in pages:
        window = excerpt_around(page.text, controller_name, radius=700)
        for pattern in ADDRESS_PATTERNS:
            match = pattern.search(window)
            if match:
                value = " ".join(match.group(1).split()).strip(" :,;")
                if value:
                    return EvidenceItem("controller_address", value, page.url, excerpt_around(page.text, value))
    return None


def find_controller_country(pages: list[FetchedPage], controller_name: str) -> EvidenceItem | None:
    if not controller_name:
        return None

    for page in pages:
        windows = [excerpt_around(page.text, controller_name, radius=500)]
        for window in windows:
            for country in COUNTRIES:
                if re.search(rf"\b{re.escape(country)}\b", window, flags=re.IGNORECASE):
                    return EvidenceItem(
                        "controller_country",
                        country,
                        page.url,
                        excerpt_around(page.text, country),
                    )
    return None


def infer_request_method(
    privacy_request_url: str,
    dpo_contact: str,
    request_page: FetchedPage | None,
    dpo_evidence: EvidenceItem | None = None,
) -> EvidenceItem | None:
    if privacy_request_url:
        searchable = f"{privacy_request_url} {request_page.text if request_page else ''}".lower()
        if any(keyword in searchable for keyword in ["portal", "dashboard", "account settings"]):
            return EvidenceItem("request_method", "portal", privacy_request_url, privacy_request_url)
        if "privacy center" in searchable:
            return EvidenceItem("request_method", "portal", privacy_request_url, privacy_request_url)
        if any(keyword in searchable for keyword in ["form", "request form", "submit a request"]):
            excerpt = excerpt_around(searchable, "form") if "form" in searchable else privacy_request_url
            return EvidenceItem("request_method", "form", privacy_request_url, excerpt)
        return EvidenceItem("request_method", "form", privacy_request_url, privacy_request_url)
    if dpo_contact:
        return EvidenceItem(
            "request_method",
            "email",
            dpo_evidence.source_url if dpo_evidence else "",
            dpo_evidence.excerpt if dpo_evidence else dpo_contact,
        )
    return None


def page_for_url(pages: list[FetchedPage], url: str) -> FetchedPage | None:
    for page in pages:
        if page.url == url:
            return page
    return None


def excerpt_around(text: str, needle: str, radius: int = 180) -> str:
    if not needle:
        return ""
    lower_text = text.lower()
    lower_needle = needle.lower()
    index = lower_text.find(lower_needle)
    if index == -1:
        return text[: radius * 2].strip()
    start = max(0, index - radius)
    end = min(len(text), index + len(needle) + radius)
    return " ".join(text[start:end].split())


def _find_url_evidence(
    pages: list[FetchedPage], field: str, keywords: list[str]
) -> EvidenceItem | None:
    for page in pages:
        searchable_url = page.url.lower().replace("-", " ").replace("_", " ")
        searchable_text = f"{page.title}\n{page.text[:4000]}".lower()
        if any(keyword in searchable_url or keyword in searchable_text for keyword in keywords):
            matched = next(
                (
                    keyword
                    for keyword in keywords
                    if keyword in searchable_url or keyword in searchable_text
                ),
                keywords[0],
            )
            return EvidenceItem(field, page.url, page.url, excerpt_around(page.text, matched))
    return None


def _clean_title(title: str, domain: str) -> str:
    brand = re.split(r"\s[-|]\s", title, maxsplit=1)[0].strip()
    if not brand or domain.replace(".", "") in brand.lower().replace(" ", ""):
        return brand or domain
    return brand


def _clean_controller(value: str) -> str:
    cleaned = " ".join(value.split()).strip(" :,;")
    cleaned = re.split(
        r"\s+(?:and|for|with|when|where|if|unless|because)\s+",
        cleaned,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]
    return cleaned.strip(" :,;")


def _contains_any(value: str, keywords: list[str]) -> bool:
    return any(keyword.strip() in value for keyword in keywords)


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result
