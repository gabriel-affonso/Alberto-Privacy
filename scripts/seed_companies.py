"""Seed obvious privacy-target companies and resolve their controller data."""

from __future__ import annotations

import json
import sys
from argparse import ArgumentParser
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import get_settings


DEFAULT_COMPANIES = [
    ("Temu", "temu.com"),
    ("AliExpress", "aliexpress.com"),
    ("Myprotein", "myprotein.com"),
    ("Bulk", "bulk.com"),
    ("Facebook", "facebook.com"),
    ("Google / Gmail", "google.com"),
    ("Instagram", "instagram.com"),
    ("Amazon", "amazon.com"),
    ("PayPal", "paypal.com"),
    ("Spotify", "spotify.com"),
]


def api(method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
    settings = get_settings()
    data = json.dumps(payload).encode() if payload is not None else None
    request = Request(
        "http://127.0.0.1:8000" + path,
        data=data,
        method=method,
        headers={
            "Authorization": "Bearer " + settings.privacy_api_token,
            "Content-Type": "application/json",
        },
    )
    with urlopen(request, timeout=600) as response:
        return json.load(response)


def parse_args() -> set[str]:
    parser = ArgumentParser(
        description="Seed obvious privacy-target companies and resolve controller data."
    )
    parser.add_argument(
        "--skip-domain",
        action="append",
        default=[],
        help="Domain to skip. May be passed more than once.",
    )
    args = parser.parse_args()
    return {domain.lower() for domain in args.skip_domain}


def main() -> None:
    skipped_domains = parse_args()
    settings = get_settings()
    if not settings.openclaw_enabled or not settings.alberto_bridge_token:
        raise SystemExit(
            "Enable OPENCLAW_ENABLED=true and configure ALBERTO_BRIDGE_TOKEN first."
        )

    existing: dict[str, dict[str, Any]] = {}
    offset = 0
    while True:
        batch = api("GET", f"/companies?skip={offset}&limit=100")
        for company in batch:
            domain = (company.get("domain") or "").lower()
            if domain:
                existing[domain] = company
        if len(batch) < 100:
            break
        offset += len(batch)

    for name, domain in DEFAULT_COMPANIES:
        if domain in skipped_domains:
            print(f"{name}: skipped.")
            continue

        try:
            company = existing.get(domain)
            if company is None:
                company = api("POST", "/companies", {"name": name, "domain": domain})
                existing[domain] = company

            if company.get("last_resolved_at"):
                print(f"{name}: already resolved; keeping existing result.")
                continue

            print(f"{name}: resolving, please wait...")
            result = api("POST", f"/companies/{company['id']}/resolve-controller")
            print(f"  done. Request method: {result['request_method']}")
        except HTTPError as error:
            print(f"{name}: HTTP {error.code}; continuing.")
        except Exception as error:
            print(f"{name}: failed ({type(error).__name__}); continuing.")

    print("Batch finished. No privacy request was sent.")


if __name__ == "__main__":
    main()
