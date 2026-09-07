"""Seed curated candidate companies and optionally resolve controller data.

The catalog is intentionally broader than confirmed accounts. Seeding a candidate does
not mean the user has an account with that company and never sends a privacy request.
"""

from __future__ import annotations

import json
import sys
from argparse import ArgumentParser, Namespace
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import get_settings


CATALOG_PATH = PROJECT_ROOT / "data" / "company_candidates.json"
ALLOWED_PRIORITIES = {"P1", "P2", "P3"}


def api(method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
    settings = get_settings()
    data = json.dumps(payload).encode() if payload is not None else None
    request = Request(
        # The script runs inside the privacy-api container. "localhost" would
        # point back to that container, while the Compose service name reaches
        # the API through Docker's internal network.
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


def load_catalog(path: Path = CATALOG_PATH) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    candidates = payload.get("candidates")
    if not isinstance(candidates, list):
        raise ValueError(f"{path} does not contain a candidates list")
    return candidates


def candidate_note(candidate: dict[str, Any]) -> str:
    return (
        "candidate_catalog; "
        f"priority={candidate['priority']}; "
        f"category={candidate['category']}; "
        f"parent_company={candidate['parent_company']}; "
        f"likely_controller_group={candidate['likely_controller_group']}; "
        f"reason={candidate['reason_for_candidate']}"
    )


def parse_args() -> Namespace:
    parser = ArgumentParser(
        description=(
            "Seed the curated candidate-company catalog. Controller resolution is "
            "opt-in via --resolve; no GDPR request is ever sent by this script."
        )
    )
    parser.add_argument(
        "--catalog",
        type=Path,
        default=CATALOG_PATH,
        help=f"Candidate catalog JSON (default: {CATALOG_PATH.relative_to(PROJECT_ROOT)}).",
    )
    parser.add_argument(
        "--skip-domain",
        action="append",
        default=[],
        help="Domain to skip. May be passed more than once.",
    )
    parser.add_argument(
        "--priority",
        action="append",
        choices=sorted(ALLOWED_PRIORITIES),
        default=[],
        help="Only seed this priority. May be passed more than once.",
    )
    parser.add_argument(
        "--category",
        action="append",
        default=[],
        help="Only seed this category. May be passed more than once.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of matching candidates to process.",
    )
    parser.add_argument(
        "--resolve",
        action="store_true",
        help="After seeding, resolve controller data for unresolved or unknown candidates.",
    )
    return parser.parse_args()


def selected_candidates(args: Namespace) -> list[dict[str, Any]]:
    skipped = {domain.lower() for domain in args.skip_domain}
    priorities = set(args.priority)
    categories = set(args.category)

    selected: list[dict[str, Any]] = []
    for candidate in load_catalog(args.catalog):
        domain = str(candidate["domain"]).lower()
        if domain in skipped:
            continue
        if priorities and candidate["priority"] not in priorities:
            continue
        if categories and candidate["category"] not in categories:
            continue
        selected.append(candidate)

    if args.limit is not None:
        selected = selected[: max(args.limit, 0)]
    return selected


def main() -> None:
    args = parse_args()
    settings = get_settings()

    if args.resolve and (
        not settings.openclaw_enabled or not settings.alberto_bridge_token
    ):
        raise SystemExit(
            "--resolve requires OPENCLAW_ENABLED=true and ALBERTO_BRIDGE_TOKEN."
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

    created = 0
    resolved = 0
    skipped_resolution = 0
    failed = 0

    for candidate in selected_candidates(args):
        name = candidate["brand"]
        domain = candidate["domain"].lower()

        try:
            company = existing.get(domain)
            if company is None:
                company = api(
                    "POST",
                    "/companies",
                    {
                        "name": name,
                        "domain": domain,
                        "notes": candidate_note(candidate),
                    },
                )
                existing[domain] = company
                created += 1
                print(
                    f"{name}: seeded "
                    f"({candidate['priority']}, {candidate['category']})."
                )
            else:
                print(f"{name}: already present.")

            if not args.resolve:
                continue

            # A previous low-confidence run can set last_resolved_at while still
            # leaving request_method unknown. Revisit those records so a newly
            # added verified override can replace the weak crawler result.
            existing_method = str(company.get("request_method") or "").strip().lower()
            if company.get("last_resolved_at") and existing_method not in {"", "unknown"}:
                skipped_resolution += 1
                print("  controller already resolved; keeping existing result.")
                continue

            print("  resolving controller...")
            result = api("POST", f"/companies/{company['id']}/resolve-controller")
            resolved += 1
            company.update(
                {
                    "last_resolved_at": result.get("queried_at") or company.get("last_resolved_at"),
                    "request_method": result.get("request_method"),
                }
            )
            print(f"  done. Request method: {result['request_method']}")
        except HTTPError as error:
            failed += 1
            print(f"{name}: HTTP {error.code}; continuing.")
        except Exception as error:
            failed += 1
            print(f"{name}: failed ({type(error).__name__}); continuing.")

    print(
        "Batch finished. "
        f"created={created} resolved={resolved} "
        f"resolution_skipped={skipped_resolution} failed={failed}. "
        "No privacy request was sent."
    )


if __name__ == "__main__":
    main()
