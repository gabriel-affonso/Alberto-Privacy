# Headless Gmail OAuth on the NUC

The privacy agent normally uses `InstalledAppFlow.run_local_server()`, which assumes the browser and Python process are on the same machine. On a headless NUC accessed from a phone, Google's loopback callback (`http://localhost:...`) points at the phone instead of the NUC.

Use `scripts/gmail_oauth_headless.py` once to create the read-only Gmail token.

## Prerequisite

Place the Google Desktop OAuth client JSON at:

```text
/app/secrets/google_oauth_client.json
```

With the default Docker Compose mount this corresponds to:

```text
/opt/privacy-agent/secrets/google_oauth_client.json
```

## Run

```bash
docker compose exec -it privacy-api python scripts/gmail_oauth_headless.py
```

The script prints a Google authorization URL. Open it on the phone or another browser, approve Gmail read-only access, and allow Google to redirect to a URL such as:

```text
http://localhost:8765/?state=...&code=...&scope=...
```

Because the browser is not running on the NUC, that page may show a connection error. This is expected. Copy the **entire URL from the browser address bar** and paste it back into the terminal prompt.

The helper exchanges the code and writes:

```text
/app/secrets/gmail_token.json
```

No Gmail message is read and no email is sent during this authorization step.

## Verify

```bash
docker compose exec privacy-api sh -lc 'test -f /app/secrets/gmail_token.json && echo "Gmail token: OK" || echo "Gmail token: MISSING"'
```

After that, Gmail discovery can be run through the API:

```bash
curl -X POST http://localhost:8000/discovery/gmail
```

The discovery module uses only Gmail metadata and the `gmail.readonly` scope. Email sending uses a separate OAuth token and explicit request approval workflow.
