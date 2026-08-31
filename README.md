# privacy-agent

Self-hosted personal GDPR/RGPD data-access request manager.

This first stage intentionally includes only the project foundation:

- FastAPI application with `/health`
- PostgreSQL through Docker Compose
- SQLAlchemy models and session setup
- Alembic configuration and initial migration
- Basic CRUD endpoints for companies and accounts
- Gmail read-only discovery for likely services/accounts
- Public controller resolution for company domains
- Pytest smoke tests

It never sends a request automatically: each email send and portal submission requires explicit approval.

## Stack

- Python 3.12
- FastAPI
- PostgreSQL
- SQLAlchemy
- Alembic
- Docker Compose
- Pytest

## Directory Layout

```text
privacy-agent/
  alembic/
    env.py
    versions/
  app/
    api/
      routes/
    core/
    crud/
    db/
    gmail_discovery/
    controller_resolver/
    gdpr_request_generator/
    case_manager/
    privacy_portals/
    response_analyzer/
    models/
    schemas/
    main.py
  tests/
  Dockerfile
  docker-compose.yml
  requirements.txt
```

## Configuration

Create a local `.env` file from the example:

```bash
cp .env.example .env
```

Default values:

```env
APP_NAME=privacy-agent
APP_ENV=local
DATABASE_URL=postgresql+psycopg://privacy:privacy@postgres:5432/privacy_agent
GMAIL_OAUTH_CLIENT_SECRETS_FILE=secrets/google_oauth_client.json
GMAIL_OAUTH_TOKEN_FILE=secrets/gmail_token.json
GMAIL_DISCOVERY_MAX_RESULTS_PER_QUERY=50
CONTROLLER_RESOLVER_MAX_PAGES=20
OPENCLAW_ENABLED=false
OPENCLAW_BASE_URL=
OPENCLAW_TOKEN=
OPENCLAW_MODEL=
OPENCLAW_INVOKE_COMMAND=openclaw.invoke
OPENCLAW_TIMEOUT_SECONDS=30
OPENCLAW_MAX_INPUT_CHARS=12000
GMAIL_OAUTH_SEND_TOKEN_FILE=secrets/gmail_send_token.json
PRIVACY_USER_FULL_NAME=
PRIVACY_USER_PREFERRED_EMAIL=
PRIVACY_USER_OPTIONAL_PHONE=
PRIVACY_USER_COUNTRY=
PRIVACY_USER_PREFERRED_LANGUAGE=en
GDPR_DEFAULT_DEADLINE_DAYS=30
PRIVACY_DATA_ROOT=data/cases
PRIVACY_API_TOKEN=
```

When running commands directly on the host instead of inside Docker, use `localhost` for the database host:

```env
DATABASE_URL=postgresql+psycopg://privacy:privacy@localhost:5432/privacy_agent
```

## Start With Docker Compose

Build and start the services:

```bash
docker compose up --build
```

In another terminal, run the database migration:

```bash
docker compose exec privacy-api alembic upgrade head
```

Check the API:

```bash
curl http://localhost:8000/health
```

Expected response:

```json
{"status":"ok","service":"privacy-agent"}
```

## API Endpoints

Health:

- `GET /health`

Companies:

- `POST /companies`
- `GET /companies`
- `GET /companies/{company_id}`
- `PATCH /companies/{company_id}`
- `DELETE /companies/{company_id}`
- `POST /companies/{company_id}/resolve-controller`
- `GET /companies/{company_id}/controller`
- `POST /companies/resolve-pending`

Accounts:

- `POST /accounts`
- `GET /accounts`
- `GET /accounts/{account_id}`
- `PATCH /accounts/{account_id}`
- `DELETE /accounts/{account_id}`

Discovery:

- `POST /discovery/gmail`
- `GET /discovery/results`

Requests and cases:

- `POST /companies/{company_id}/requests/generate`
- `GET/PATCH /requests/{request_id}`
- `POST /requests/{request_id}/approve`
- `POST /requests/{request_id}/send-email`
- `POST /requests/{request_id}/sync-gmail`
- `GET /cases`, `GET /cases/{id}`, `GET /cases/overdue`, `GET /cases/pending-action`
- `POST /cases/{id}/transition`
- `POST /cases/{id}/portal/prepare`

Responses and provenance:

- `POST /cases/{id}/responses` (multipart upload)
- `GET /cases/{id}/report`
- `GET /provenance/entities`, `GET /provenance/relations`
- `GET /provenance/company/{id}`
- `GET /provenance/identifier/{type}/{value_hash}`

## Gmail Discovery

The Gmail discovery module uses the Gmail API with OAuth2 and the read-only scope:

```text
https://www.googleapis.com/auth/gmail.readonly
```

It searches for likely account-related messages using these queries:

- `welcome`
- `verify your email`
- `confirm your account`
- `password reset`
- `your account`
- `registration`

For each candidate service, it extracts only metadata:

- sender domain
- apparent company name
- sender email address
- subject
- first seen date
- last seen date
- matching message count
- confidence score

It deduplicates services by sender domain, then saves candidates into `companies` and `accounts`.

It does not send full email contents to an LLM.

### Gmail OAuth Setup

Create an OAuth client in Google Cloud for the Gmail API and download the OAuth client secrets JSON file.

Place it at:

```text
secrets/google_oauth_client.json
```

The first call to Gmail discovery starts an OAuth2 browser flow:

```bash
curl -X POST http://localhost:8000/discovery/gmail
```

The app stores the OAuth token at:

```text
secrets/gmail_token.json
```

This token is used for future Gmail API calls. The Google account password is never requested or stored by this project. Files under `secrets/*.json` are ignored by Git.

With Docker Compose, `./secrets` is mounted into the API container at `/app/secrets`, so OAuth files can be updated without rebuilding the image.

After discovery, inspect saved results:

```bash
curl http://localhost:8000/discovery/results
```

## Controller Resolver

The controller resolver takes a company domain or website and searches public pages on that domain for:

- privacy policy
- privacy center
- GDPR/data rights page
- DPO contact
- data controller

Run it for a company:

```bash
curl -X POST http://localhost:8000/companies/1/resolve-controller
```

The company must have either `domain` or `website` set. The response shape is:

```json
{
  "brand": "",
  "domain": "",
  "controller_name": "",
  "controller_country": "",
  "privacy_policy_url": "",
  "privacy_request_url": "",
  "dpo_contact": "",
  "request_method": "unknown",
  "confidence": 0.0,
  "evidence": [],
  "queried_at": "2026-08-28T00:00:00Z"
}
```

Every populated field is backed by an evidence item with `source_url` and `excerpt`. If evidence is weak or missing, the resolver leaves fields empty and returns lower confidence instead of guessing.

Each run is stored in `controller_resolutions` with the query timestamp and evidence payload. The latest verified values are mirrored on the company record. Conflicting controller names are returned as conflicts rather than silently selected.

### Optional OpenClaw Interpretation

By default, `OPENCLAW_ENABLED=false`. When enabled, the resolver may call OpenClaw only after public pages have been fetched, and only to interpret the fetched text for missing ambiguous fields. It does not let OpenClaw browse or invent values.

Expected command shape:

```bash
openclaw.invoke --tool llm-task --action json --args-json '{...}'
```

The OpenClaw result is accepted only when it includes evidence pointing back to a fetched source URL and an excerpt present in the fetched page text.

## GDPR request workflow

Configure the identity through environment variables; it is never hard-coded and no identity document is stored by default. Generate an Article 15 draft, review or edit it, then approve it:

```bash
curl -X POST http://localhost:8000/companies/1/requests/generate \
  -H 'content-type: application/json' \
  -d '{"request_type":"article_15_access"}'
curl -X POST http://localhost:8000/requests/1/approve
```

`send-email` only accepts an approved request with a verified email contact. It uses a separate Gmail OAuth token with the `gmail.send` scope and records Gmail IDs, a local EML copy, a hash, deadline, and case event. Portal preparation creates a preview only; it stops for explicit approval and never bypasses CAPTCHA, MFA, login, or identity checks.

For a browser-backed portal preview, install Playwright's Chromium runtime after installing Python dependencies:

```bash
playwright install chromium
```

## Response ingestion and privacy

Incoming ZIP, JSON, CSV, HTML, TXT, and PDF files are saved under `data/cases/{case_id}/incoming/` and hashed. ZIP extraction rejects path traversal, nested archives, excessive member counts, and excessive decompressed sizes. Parsed identifiers are redacted in database findings and retained as hashes for lookup. The report states that information was “not identified in the supplied response”; it makes no legal conclusion.

If the service is exposed beyond localhost, set `PRIVACY_API_TOKEN` and send `Authorization: Bearer …`. Docker binds PostgreSQL and the API to localhost by default.

## Run Tests Locally

Create and activate a virtual environment:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Run tests:

```bash
pytest
```

The tests use SQLite in memory and do not require Docker or PostgreSQL.

## Database Migrations

Apply migrations:

```bash
alembic upgrade head
```

Create a new migration after changing models:

```bash
alembic revision --autogenerate -m "describe change"
```
