# Candidate company catalog

`data/company_candidates.json` is a curated discovery catalog, not a list of confirmed user accounts.

The catalog exists to give the privacy agent a broad set of services to check against evidence such as Gmail discovery before controller resolution or an Article 15 request is prepared.

## Safety model

- `status: candidate` means only that the service is worth checking.
- A catalog entry is **not** evidence that the user has or had an account.
- Seeding candidates never sends a GDPR request.
- Controller resolution is opt-in with `--resolve`.
- Requests should be deduplicated by `likely_controller_group` where appropriate (for example Google services, Meta services, Inditex brands, or Expedia Group services).
- Every actual send or portal submission remains subject to the project's existing explicit-approval workflow.

## Fields

Each candidate includes:

- `brand`
- `domain`
- `category`
- `parent_company`
- `likely_controller_group`
- `priority` (`P1`, `P2`, or `P3`)
- `reason_for_candidate`
- `status`

`likely_controller_group` is a discovery/deduplication hint. It is not a verified legal-controller determination; the controller resolver must still establish the actual controller and evidence before a request is generated.

## Seed the catalog

Seed every candidate into the companies table without resolving controllers:

```bash
python scripts/seed_companies.py
```

Seed only high-priority candidates:

```bash
python scripts/seed_companies.py --priority P1
```

Seed more than one priority:

```bash
python scripts/seed_companies.py --priority P1 --priority P2
```

Seed a category:

```bash
python scripts/seed_companies.py --category travel
```

Limit a test run:

```bash
python scripts/seed_companies.py --priority P1 --limit 10
```

Resolve controllers only when explicitly requested and OpenClaw/Alberto is configured:

```bash
python scripts/seed_companies.py --priority P1 --resolve
```

The script is idempotent by domain: existing companies are retained rather than duplicated.

## Recommended workflow

1. Seed candidate companies.
2. Run Gmail discovery and other account-evidence sources.
3. Promote candidates only when there is credible evidence of an account/relationship.
4. Group related services by probable controller family.
5. Resolve the current legal controller and privacy channel from public evidence.
6. Generate an Article 15 draft.
7. Review and explicitly approve before any email send or portal submission.

The catalog is intentionally broad and should evolve as new services are discovered.
