from app.gmail_discovery.classification import (
    CONFIRMED,
    IGNORE,
    PROBABLE,
    WEAK,
    canonicalize_discovery_domain,
    classify_discovery,
)


def classify(domain: str, subject: str, *, company_name: str = "Example", messages: int = 1):
    return classify_discovery(
        domain=domain,
        company_name=company_name,
        sender_email=f"notice@{domain}",
        subject=subject,
        message_count=messages,
        base_confidence=0.53,
    )


def test_known_subdomains_and_country_domains_are_canonicalized() -> None:
    assert canonicalize_discovery_domain("notice.aliexpress.com") == "aliexpress.com"
    assert canonicalize_discovery_domain("orders.temu.com") == "temu.com"
    assert canonicalize_discovery_domain("email.apple.com") == "apple.com"
    assert canonicalize_discovery_domain("verify.orcid.org") == "orcid.org"
    assert canonicalize_discovery_domain("amazon.es") == "amazon.com"


def test_password_reset_or_order_is_strong_account_evidence() -> None:
    reset = classify("zotero.org", "Password Reset")
    order = classify("orders.temu.com", "Your Temu order has been refunded")

    assert reset.classification == CONFIRMED
    assert reset.dsar_eligible is True
    assert order.classification == CONFIRMED
    assert order.canonical_domain == "temu.com"


def test_personal_mailbox_is_ignored() -> None:
    result = classify("gmail.com", "Re: project notes", company_name="A Person", messages=10)

    assert result.classification == IGNORE
    assert result.dsar_eligible is False


def test_newsletter_without_account_signal_is_weak_even_with_many_messages() -> None:
    result = classify("morningbrew.com", "Unstable outlook", messages=9)

    assert result.classification == WEAK
    assert result.dsar_eligible is False


def test_processor_mediated_recruiting_needs_controller_review() -> None:
    result = classify(
        "candidates.workablemail.com",
        "Thanks for applying to Q ENERGY",
        company_name="Workable",
    )

    assert result.classification == PROBABLE
    assert result.canonical_domain == "workable.com"
    assert result.relationship == "processor-mediated"
    assert result.likely_controller == "Q ENERGY"
    assert result.requires_controller_review is True
    assert result.dsar_eligible is False
