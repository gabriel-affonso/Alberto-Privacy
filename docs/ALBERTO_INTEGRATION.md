# Alberto integration on the NUC

## Security boundary

The Privacy Agent and Alberto are separate services on the same NUC.

```text
Alberto / OpenClaw Gateway                 Privacy Agent
127.0.0.1:18789                            Docker API: 127.0.0.1:8000
Gateway token stays here                   Gmail, PostgreSQL, files stay here
             <-- restricted job bridge -->
```

Do not put `OPENCLAW_GATEWAY_TOKEN`, Gateway passwords, or `127.0.0.1:18789` in the Privacy Agent configuration. The Gateway token is administrative and must remain owned by Alberto.

The bridge is intentionally narrow. Alberto can only claim a pending controller-interpretation task and complete or reject that task. It cannot list companies, send requests, read response files, access Gmail, or connect to PostgreSQL.

## Enable the bridge

Generate a distinct bridge secret on the NUC:

```bash
openssl rand -hex 32
```

Put it in the Privacy Agent's `.env` file:

```env
OPENCLAW_ENABLED=true
OPENCLAW_MODEL=
ALBERTO_BRIDGE_TOKEN=<the-generated-secret>
```

Restart the API after changing the configuration:

```bash
docker compose up -d --build
docker compose exec privacy-api alembic upgrade head
```

Store the same value in an Alberto-only file, readable only by the `alberto` user:

```bash
sudo -u alberto install -d -m 700 /home/alberto/.config/alberto
sudo -u alberto sh -c 'umask 077; printf "%s\n" "PRIVACY_AGENT_ALBERTO_TOKEN=<the-generated-secret>" > /home/alberto/.config/alberto/privacy-agent-bridge.env'
```

Never add either file to Git, send it in chat, or place this token in OpenClaw's Gateway configuration.

## Bridge protocol

All calls are made by Alberto to the local Privacy Agent API. Use `127.0.0.1`, not the NUC LAN address.

Claim one pending task:

```bash
source /home/alberto/.config/alberto/privacy-agent-bridge.env
curl -fsS -X POST http://127.0.0.1:8000/alberto/jobs/next \
  -H "Authorization: Bearer $PRIVACY_AGENT_ALBERTO_TOKEN" \
  -H 'X-Alberto-Worker: alberto'
```

When it returns `null`, there is no work. Otherwise, Alberto receives public pages, an instruction, and a required result schema. It must not browse for additional facts. It should use only the supplied text and return an empty string when evidence is insufficient.

Complete a job after interpretation:

```bash
curl -fsS -X POST http://127.0.0.1:8000/alberto/jobs/<job-id>/complete \
  -H "Authorization: Bearer $PRIVACY_AGENT_ALBERTO_TOKEN" \
  -H 'content-type: application/json' \
  --data @result.json
```

`result.json` must have this shape:

```json
{
  "result": {
    "controller_name": "",
    "controller_country": "",
    "dpo_contact": "",
    "privacy_request_url": "",
    "evidence": [
      {
        "field": "controller_name",
        "value": "Example Europe Ltd",
        "source_url": "https://example.test/privacy",
        "excerpt": "Example Europe Ltd is the data controller."
      }
    ]
  }
}
```

The API accepts a value only when the source URL was supplied in the task and the excerpt occurs in that exact page text. Unsupported or invented claims are discarded.

To reject an unworkable task instead:

```json
{"error":"The supplied pages do not contain enough evidence."}
```

Post the same body to the `complete` endpoint.

## Alberto operating instruction

Install the versioned skill from this repository into Alberto's OpenClaw workspace:

```bash
sudo install -d -o alberto -g alberto /home/alberto/.openclaw/workspace/skills/privacy-agent-bridge
sudo install -o alberto -g alberto -m 644 openclaw/skills/privacy-agent-bridge/SKILL.md /home/alberto/.openclaw/workspace/skills/privacy-agent-bridge/SKILL.md
```

It is important that the completion request sends a JSON body with a top-level
`result` object, even when no evidence was found. Sending `{"evidence":[]}`
directly is invalid.

Add this instruction to Alberto's privacy-agent workflow or skill:

> For a Privacy Agent task, claim one job using the local bridge. Interpret only the supplied page text. Do not browse, call the Privacy Agent's other endpoints, access Gmail, send communications, or use the OpenClaw Gateway token. Return a value only if a supplied excerpt proves it; otherwise leave it empty. Submit the structured result to the same bridge.

The bridge is asynchronous: resolving a company saves the deterministic result immediately and queues a task only for missing controller details. Run the Alberto workflow periodically or invoke it after a resolution.
