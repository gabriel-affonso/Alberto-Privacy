"""Resolve confirmed Gmail-discovered targets using only verified contact overrides.

Default mode is a dry run. Use --apply to persist controller resolution through the
existing API endpoint. The script never creates, approves, or sends a privacy request.
"""

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

from app.controller_resolver.verified_contacts import verified_contact_for_domain
from app.core.config import get_settings


def api(method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
    settings = get_settings()
    data = json.dumps(payload).encode() if payload is not None else None
    request = Request(
        "http://privacy-api:8000" + path,
        data=data,
        method=method,
        headers={
            "Authorization": "Bearer " + settings.privacy_api_token,
            "Content-Type": "application/json",
        },
    )
    with urlopen(request, timeout=600) as response:
        return json.load(response)


def companies() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    offset = 0
    while True:
        batch = api("GET", f"/companies?skip={offset}&limit=100")
        rows.extend(batch)
        if len(batch) < 100:
            return rows
        offset += len(batch)


def main() -> None:
    parser = ArgumentParser(
        description=(
            "Resolve confirmed Gmail discoveries only when a manually verified override "
            "exists. Dry-run by default; --apply persists controller metadata."
        )
    )
    parser.add_argument("--apply", action="store_true", help="Persist verified resolutions.")
    args = parser.parse_args()

    targets = [
        row
        for row in companies()
        if row.get("discovery_dsar_eligible") is True
        and str(row.get("request_method") or "").strip().lower() in {"", "unknown"}
    ]

    ready = 0
    special = 0
    unresolved = 0
    applied = 0
    failed = 0

    for company in sorted(targets, key=lambda row: (row.get("name") or "").lower()):
        domain = str(company.get("domain") or "").strip().lower()
        record = verified_contact_for_domain(domain) if domain else None
        if record is None:
            unresolved += 1
            print(f"NO_OVERRIDE      | {company.get('name')} | {domain}")
            continue

        framework = str(record.get("legal_framework") or "GDPR").strip()
        standard_template = record.get("standard_gdpr_article_15_template", True) is not False
        status = "VERIFIED"
        if not standard_template:
            status = "SPECIAL_FRAMEWORK"
            special += 1
        else:
            ready += 1

        print(
            f"{status:17} | {company.get('name')} | {domain} -> {record.get('domain')} "
            f"| {str(record.get('request_method') or '').upper()} | {framework}"
        )

        if not args.apply:
            continue

        try:
            result = api("POST", f"/companies/{company['id']}/resolve-controller")
            applied += 1
            print(
                "  applied: "
                f"controller={result.get('controller_name') or '-'}; "
                f"method={result.get('request_method') or '-'}"
            )
        except HTTPError as error:
            failed += 1
            print(f"  HTTP {error.code}; not applied")
        except Exception as error:
            failed += 1
            print(f"  {type(error).__name__}; not applied")

    mode = "APPLY" if args.apply else "DRY RUN"
    print(
        f"{mode}: targets={len(targets)} verified_standard={ready} "
        f"special_framework={special} no_override={unresolved} "
        f"applied={applied} failed={failed}."
    )
    print("No privacy request was created, approved, or sent.")


if __name__ == "__main__":
    main()
