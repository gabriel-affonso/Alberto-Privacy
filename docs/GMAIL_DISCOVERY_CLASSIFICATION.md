# Gmail discovery classification

Gmail discovery is evidence collection, not DSAR authorization.

The pipeline is:

```text
Gmail metadata evidence
  -> canonical domain
  -> semantic classification
  -> controller review/resolution
  -> confirmed DSAR target
  -> DRAFT
  -> explicit approval
  -> delivery
```

## Classifications

- `CONFIRMED`: strong account/transaction evidence. May be DSAR-eligible when the relationship is direct.
- `PROBABLE`: repeated or plausible evidence, but not enough to treat the service as a confirmed direct target.
- `WEAK`: newsletter, marketing, informational, or ambiguous evidence.
- `IGNORE`: personal correspondence or an alias row superseded by a canonical company.

`discovery_dsar_eligible` is only advisory evidence for the request generator; Gmail-derived accounts are blocked from draft generation unless they are `CONFIRMED`, eligible, and do not require controller review.

## Canonicalization

Known subdomains are collapsed into catalog services, for example:

```text
notice.aliexpress.com -> aliexpress.com
orders.temu.com       -> temu.com
email.apple.com       -> apple.com
verify.orcid.org      -> orcid.org
notify.cloudflare.com -> cloudflare.com
amazon.es             -> amazon.com
```

Catalog domains are also used as suffix matches, so new sender subdomains of known services normally canonicalize automatically.

## Processor-mediated relationships

Messages sent by recruiting/signature platforms are not assumed to make that platform the correct controller. Workday, iCIMS, Workable, DocuSign, Greenhouse and Lever are marked `processor-mediated`, `requires_controller_review=true`, and `discovery_dsar_eligible=false` until the underlying controller is resolved.

## Upgrade and reclassify stored discoveries

After pulling this change and rebuilding the API container:

```bash
docker compose exec privacy-api alembic upgrade head
```

Preview classification of stored Gmail evidence without changing the database:

```bash
docker compose exec privacy-api python scripts/reclassify_gmail_discoveries.py
```

Apply it:

```bash
docker compose exec privacy-api python scripts/reclassify_gmail_discoveries.py --apply
```

This script does not read Gmail. It only uses the sender, subject, count and confidence already stored in PostgreSQL. It does not create or send privacy requests.

## API

`GET /discovery/results` now returns the classification, raw/canonical domain, relationship type, likely controller hint, review flag, DSAR eligibility and classification reason. `IGNORE` rows are hidden by default.
