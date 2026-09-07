# Verified privacy contacts

`data/verified_privacy_contacts.json` is the reviewed override layer for controller resolution.

It contains privacy/DPO email addresses and official form/portal routes verified from first-party privacy material. A record in this file is stronger evidence than a crawler guess, so `resolve_controller_for_company()` checks this catalog before fetching or interpreting public pages.

## Safety boundary

A verified contact does **not** mean that the user has an account with that company and it does **not** authorize a GDPR request.

The workflow remains:

```text
candidate catalog
  -> evidence of an account/relationship
  -> controller resolution
  -> controller-group deduplication
  -> Article 15 DRAFT
  -> explicit APPROVAL
  -> email send or portal/form preparation
```

Email delivery still requires an approved request. Records whose verified method is `form` or `portal` are not valid email-delivery targets even if a DPO mailbox is also stored for reference.

## Resolution precedence

1. A matching domain in `data/verified_privacy_contacts.json` is converted directly into a `ControllerResolutionResult` with provenance.
2. If there is no verified override, the normal public-page crawler/resolver runs.
3. OpenClaw interpretation is not queued for verified overrides, because those records have already been manually reviewed.

The verified catalog currently covers the 27 P1 services that remained `unknown` after the first automated resolution pass on 2026-09-07.

## Refreshing existing `unknown` records

After pulling and rebuilding the NUC container, run:

```bash
docker compose exec privacy-api python scripts/seed_companies.py --priority P1 --resolve
```

The seed script preserves already resolved non-`unknown` records, but revisits `unknown` records so a newly added verified override can replace the weak crawler result.

This command resolves metadata only. It never sends a privacy request.

## Maintaining the catalog

For every new or changed record:

- prefer official company privacy/DPO pages;
- record one or more HTTPS URLs in `official_sources`;
- use `email` only when the company explicitly provides the mailbox for privacy/data-subject rights;
- use `form` or `portal` when the company directs users to that route;
- keep a verification timestamp;
- do not use guessed addresses;
- review controller-group membership before deduplicating requests.

Run the tests after changes:

```bash
pytest tests/test_verified_privacy_contacts.py tests/test_company_candidate_catalog.py
```
