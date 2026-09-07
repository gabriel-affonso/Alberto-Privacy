"""Deterministic classification for Gmail discovery evidence.

This module deliberately separates "we saw mail from this service" from "this is a
safe DSAR target". It uses sender/domain canonicalization plus conservative subject
semantics. It never sends, approves, or generates a privacy request.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CANDIDATE_CATALOG = PROJECT_ROOT / "data" / "company_candidates.json"

CONFIRMED = "CONFIRMED"
PROBABLE = "PROBABLE"
WEAK = "WEAK"
IGNORE = "IGNORE"
CLASSIFICATIONS = {CONFIRMED, PROBABLE, WEAK, IGNORE}

DOMAIN_ALIASES = {
    "amazon.es": "amazon.com",
    "amazon.co.uk": "amazon.com",
    "amazon.de": "amazon.com",
    "amazon.fr": "amazon.com",
    "amazon.it": "amazon.com",
    "amazon.nl": "amazon.com",
    "email.apple.com": "apple.com",
    "sheinnotice.com": "shein.com",
    "updates.activision.com": "activision.com",
    "mail.nintendo-europe.com": "nintendo.com",
    "nintendo-europe.com": "nintendo.com",
    "workablemail.com": "workable.com",
    "candidates.workablemail.com": "workable.com",
    "myworkday.com": "workday.com",
    "docusign.net": "docusign.com",
}

PROCESSOR_DOMAINS = {
    "workday.com": "Workday",
    "myworkday.com": "Workday",
    "icims.com": "iCIMS",
    "workable.com": "Workable",
    "workablemail.com": "Workable",
    "docusign.com": "DocuSign",
    "docusign.net": "DocuSign",
    "greenhouse.io": "Greenhouse",
    "lever.co": "Lever",
    "dryfta.net": "Dryfta",
}

PERSONAL_MAIL_DOMAINS = {
    "gmail.com",
    "googlemail.com",
    "outlook.com",
    "hotmail.com",
    "live.com",
    "yahoo.com",
    "icloud.com",
    "proton.me",
    "protonmail.com",
}

NEWSLETTER_DOMAINS = {"morningbrew.com", "substack.com", "paragraph.xyz"}

SERVICE_NAME_TERMS = {
    "support",
    "team",
    "company",
    "corporation",
    "association",
    "university",
    "institute",
    "books",
    "bank",
    "airlines",
    "store",
    "shop",
    "newsletter",
    "security",
    "accounts",
    "recruiting",
    "recruitment",
    "contact",
    "ecommerce",
}

AUTOMATED_LOCALPART_TERMS = {
    "noreply",
    "no-reply",
    "donotreply",
    "support",
    "info",
    "contact",
    "hello",
    "newsletter",
    "notify",
    "notification",
    "notice",
    "security",
    "account",
    "team",
    "orders",
    "mail",
    "service",
    "customer",
    "verify",
    "updates",
    "billing",
    "payment",
    "recruitment",
    "recruiting",
    "jobs",
}

STRONG_ACCOUNT_PATTERNS = (
    r"password reset",
    r"reset (?:your|the) password",
    r"verify your (?:email|account|legal information)",
    r"verification code",
    r"security code",
    r"confirm your (?:email|account|payment)",
    r"new device",
    r"signed in",
    r"sign-in",
    r"login",
    r"account",
    r"registration",
    r"registered",
    r"api key",
    r"payment",
    r"receipt",
    r"invoice",
    r"refund",
    r"subscription",
    r"booking",
    r"purchase",
    r"application received",
    r"online application",
    r"thanks for applying",
    r"proof of (?:payment|email)",
    r"recovery options",
    r"re-pairing",
    r"device pairing",
)

ORDER_ACCOUNT_PATTERNS = (
    r"\byour\b.*\border\b",
    r"\border\s*(?:#|no\.?|number|[-:])",
    r"\border\s+(?:confirmed|confirmation|delivered|shipped|refunded|cancelled|canceled)",
    r"\border\b.*\b(?:thank you|delivered|shipped|refunded|tracking|package)\b",
)

TRANSACTIONAL_PATTERNS = (
    r"delivered",
    r"shipment",
    r"shipping",
    r"tracking",
    r"package",
    r"carrier",
    r"renewal",
    r"membership",
)

WEAK_CONTENT_PATTERNS = (
    r"newsletter",
    r"weekly",
    r"digest",
    r"roundup",
    r"call for papers",
    r"call for proposals",
    r"call for nominations",
    r"bulletin",
    r"updates?",
    r"news",
)

PLATFORM_APPLY_RE = re.compile(r"thanks for applying to\s+(.+?)(?:[!|]|$)", re.I)
PLATFORM_PASSWORD_RE = re.compile(r"reset (?:your|the) password for\s+(.+?)(?:[!|]|$)", re.I)


@dataclass(frozen=True)
class DiscoveryClassification:
    raw_domain: str
    canonical_domain: str
    classification: str
    confidence_score: float
    relationship: str
    likely_controller: str | None
    requires_controller_review: bool
    dsar_eligible: bool
    reason: str


def normalize_domain(domain: str) -> str:
    return domain.strip().lower().removeprefix("www.").rstrip(".")


@lru_cache(maxsize=1)
def candidate_domains() -> set[str]:
    try:
        payload = json.loads(CANDIDATE_CATALOG.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    rows = payload.get("candidates", []) if isinstance(payload, dict) else []
    return {
        normalize_domain(str(row.get("domain", "")))
        for row in rows
        if isinstance(row, dict) and row.get("domain")
    }


def canonicalize_discovery_domain(domain: str) -> str:
    raw = normalize_domain(domain)
    if raw in DOMAIN_ALIASES:
        return DOMAIN_ALIASES[raw]

    matches = [d for d in candidate_domains() if raw == d or raw.endswith("." + d)]
    if matches:
        return max(matches, key=len)

    for alias, canonical in DOMAIN_ALIASES.items():
        if raw.endswith("." + alias):
            return canonical
    return raw


def _matches_any(subject: str, patterns: tuple[str, ...]) -> bool:
    return any(re.search(pattern, subject, re.I) for pattern in patterns)


def _processor_name(raw_domain: str, canonical_domain: str) -> str | None:
    raw = normalize_domain(raw_domain)
    for domain, name in PROCESSOR_DOMAINS.items():
        if raw == domain or raw.endswith("." + domain) or canonical_domain == domain:
            return name
    return None


def _likely_controller_from_platform(company_name: str, subject: str) -> str | None:
    for pattern in (PLATFORM_APPLY_RE, PLATFORM_PASSWORD_RE):
        match = pattern.search(subject)
        if match:
            value = match.group(1).strip(" .-|")
            if value:
                return value[:255]

    generic = {
        "icims",
        "workday",
        "myworkday",
        "workable",
        "docusign",
        "greenhouse",
        "lever",
        "dryfta",
    }
    cleaned = company_name.strip()
    if cleaned and cleaned.lower() not in generic and " via docusign" not in cleaned.lower():
        return cleaned[:255]
    return None


def _looks_like_person_sender(company_name: str, sender_email: str, catalog_match: bool) -> bool:
    if catalog_match:
        return False

    words = [w for w in re.split(r"\s+", company_name.strip()) if w]
    if len(words) < 2 or len(words) > 5:
        return False

    normalized_words = [re.sub(r"[^a-z]", "", word.lower()) for word in words]
    lower_words = {word for word in normalized_words if word}
    if lower_words & SERVICE_NAME_TERMS:
        return False

    localpart = sender_email.split("@", 1)[0].lower() if "@" in sender_email else ""
    if any(term in localpart for term in AUTOMATED_LOCALPART_TERMS):
        return False

    # A display name that merely has two words is not enough to call it a person:
    # business names such as "Summersta Herrgard" or "Ecommerce Contact" otherwise
    # become false IGNORE results. Require the mailbox local-part to actually resemble
    # at least one substantial token from the display name (e.g. teresacravo,
    # iliana.boycheva, p.abreu, a.failler).
    compact_localpart = re.sub(r"[^a-z0-9]", "", localpart)
    person_tokens = [word for word in normalized_words if len(word) >= 3]
    if not person_tokens:
        return False

    return any(token in compact_localpart for token in person_tokens)


def classify_discovery(
    *,
    domain: str,
    company_name: str,
    sender_email: str,
    subject: str | None,
    message_count: int,
    base_confidence: float,
) -> DiscoveryClassification:
    raw = normalize_domain(domain)
    canonical = canonicalize_discovery_domain(raw)
    text = (subject or "").strip()
    lower = text.lower()
    catalog_match = canonical in candidate_domains()

    if raw in PERSONAL_MAIL_DOMAINS:
        return DiscoveryClassification(
            raw_domain=raw,
            canonical_domain=canonical,
            classification=IGNORE,
            confidence_score=min(base_confidence, 0.25),
            relationship="personal-correspondence",
            likely_controller=None,
            requires_controller_review=False,
            dsar_eligible=False,
            reason="sender uses a personal mailbox domain",
        )

    processor = _processor_name(raw, canonical)
    strong = _matches_any(lower, STRONG_ACCOUNT_PATTERNS) or _matches_any(lower, ORDER_ACCOUNT_PATTERNS)
    if catalog_match and re.search(r"\bwelcome to\b", lower):
        strong = True
    transactional = _matches_any(lower, TRANSACTIONAL_PATTERNS)
    weak_content = _matches_any(lower, WEAK_CONTENT_PATTERNS)
    newsletter_domain = raw in NEWSLETTER_DOMAINS or any(raw.endswith("." + d) for d in NEWSLETTER_DOMAINS)

    if processor:
        likely = _likely_controller_from_platform(company_name, text)
        classification = PROBABLE if strong or transactional else WEAK
        confidence = max(base_confidence, 0.72 if classification == PROBABLE else 0.48)
        return DiscoveryClassification(
            raw_domain=raw,
            canonical_domain=canonical,
            classification=classification,
            confidence_score=round(min(confidence, 0.92), 2),
            relationship="processor-mediated",
            likely_controller=likely,
            requires_controller_review=True,
            dsar_eligible=False,
            reason=f"evidence mediated by processor/platform {processor}",
        )

    if newsletter_domain and not strong and not transactional:
        return DiscoveryClassification(
            raw_domain=raw,
            canonical_domain=canonical,
            classification=WEAK,
            confidence_score=round(min(base_confidence, 0.55), 2),
            relationship="newsletter-or-marketing",
            likely_controller=None,
            requires_controller_review=False,
            dsar_eligible=False,
            reason="newsletter/marketing sender without account evidence",
        )

    if _looks_like_person_sender(company_name, sender_email, catalog_match):
        return DiscoveryClassification(
            raw_domain=raw,
            canonical_domain=canonical,
            classification=IGNORE,
            confidence_score=min(base_confidence, 0.35),
            relationship="personal-or-institutional-correspondence",
            likely_controller=None,
            requires_controller_review=False,
            dsar_eligible=False,
            reason="sender appears to be an individual rather than an automated service",
        )

    if strong and weak_content:
        confidence = max(base_confidence, 0.72)
        classification = PROBABLE
        reason = "mixed account and newsletter/informational subject signals"
    elif strong:
        confidence = max(base_confidence, 0.88 if catalog_match else 0.82)
        classification = CONFIRMED
        reason = "strong account/transaction subject evidence"
    elif transactional:
        confidence = max(base_confidence, 0.76)
        classification = PROBABLE if not catalog_match else CONFIRMED
        reason = "transactional message evidence"
    elif weak_content:
        confidence = min(base_confidence, 0.60)
        classification = WEAK
        reason = "newsletter/informational subject evidence"
    elif catalog_match and message_count >= 2:
        confidence = max(base_confidence, 0.70)
        classification = PROBABLE
        reason = "catalog match with repeated Gmail evidence"
    elif message_count >= 3:
        confidence = max(base_confidence, 0.66)
        classification = PROBABLE
        reason = "repeated Gmail evidence without strong account semantics"
    else:
        confidence = min(max(base_confidence, 0.40), 0.62)
        classification = WEAK
        reason = "single/ambiguous Gmail evidence"

    return DiscoveryClassification(
        raw_domain=raw,
        canonical_domain=canonical,
        classification=classification,
        confidence_score=round(min(confidence, 0.95), 2),
        relationship="direct-service",
        likely_controller=None,
        requires_controller_review=False,
        dsar_eligible=classification == CONFIRMED,
        reason=reason,
    )
