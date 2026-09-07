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
    assert canonicalize_discovery_domain("updates.activision.com") == "activision.com"


def test_password_reset_or_order_is_strong_account_evidence() -> None:
    reset = classify("zotero.org", "Password Reset")
    order = classify("orders.temu.com", "Your Temu order has been refunded")

    assert reset.classification == CONFIRMED
    assert reset.dsar_eligible is True
    assert order.classification == CONFIRMED
    assert order.canonical_domain == "temu.com"


def test_discount_mention_does_not_prove_an_order() -> None:
    result = classify(
        "fdcm.eu",
        "Re: First order discount for 20 kg Soy Protein Isolate",
        company_name="Ecommerce Contact",
        messages=3,
    )

    assert result.classification == PROBABLE
    assert result.dsar_eligible is False


def test_catalog_welcome_is_strong_but_generic_welcome_is_not() -> None:
    amazon = classify("amazon.es", "Welcome to Prime", company_name="Amazon Prime")
    generic = classify("summerstaherrgard.se", "Welcome to Summersta Herrgard!", company_name="Summersta Herrgard")

    assert amazon.classification == CONFIRMED
    assert amazon.dsar_eligible is True
    assert generic.classification == WEAK
    assert generic.dsar_eligible is False


def test_device_repairing_is_strong_account_evidence() -> None:
    result = classify("n26.com", "Please confirm your re-pairing", company_name="N26", messages=3)

    assert result.classification == CONFIRMED
    assert result.dsar_eligible is True


def test_personal_mailbox_is_ignored() -> None:
    result = classify("gmail.com", "Re: project notes", company_name="A Person", messages=10)

    assert result.classification == IGNORE
    assert result.dsar_eligible is False


def test_person_like_sender_on_unknown_institution_is_not_a_dsar_target() -> None:
    result = classify_discovery(
        domain="department.example.edu",
        company_name="Ada Example",
        sender_email="ada.example@department.example.edu",
        subject="Reset Password",
        message_count=2,
        base_confidence=0.61,
    )

    assert result.classification == IGNORE
    assert result.dsar_eligible is False


def test_newsletter_without_account_signal_is_weak_even_with_many_messages() -> None:
    result = classify("morningbrew.com", "Unstable outlook", messages=9)

    assert result.classification == WEAK
    assert result.dsar_eligible is False


def test_mixed_registration_and_call_for_proposals_is_probable_not_confirmed() -> None:
    result = classify(
        "methodsnet.org",
        "Weekly Digest: Summer School Registration & Conference Call for Proposals",
        company_name="MethodsNET",
        messages=9,
    )

    assert result.classification == PROBABLE
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


def test_dryfta_event_account_is_processor_mediated() -> None:
    result = classify(
        "dryfta.net",
        "Reset your password for MSA Prague 2025",
        company_name="MSAPrague2025",
    )

    assert result.classification == PROBABLE
    assert result.relationship == "processor-mediated"
    assert result.likely_controller == "MSA Prague 2025"
    assert result.requires_controller_review is True
    assert result.dsar_eligible is False
