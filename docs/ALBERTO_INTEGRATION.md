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
ALBERTO_JOB_LEASE_MINUTES=20
ALBERTO_JOB_MAX_ATTEMPTS=3
TELEGRAM_BOT_TOKEN=<token-do-seu-bot>
TELEGRAM_APPROVAL_CHAT_ID=<seu-chat-id-numerico>
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

## Operação contínua

O bridge é assíncrono: resolver uma empresa guarda imediatamente o resultado
determinístico e cria um job apenas para os dados ainda em falta. O skill agora
consome todos os jobs disponíveis em uma única execução. Crie uma única tarefa
recorrente no agendador nativo do Alberto/OpenClaw, a cada 5 minutos, com este
texto:

> Execute o skill `privacy-agent-bridge` para processar toda a fila do Privacy Agent. Se não houver trabalho, responda somente `NO_REPLY`. Não execute nenhuma outra ação.

Assim, novos jobs são processados sem intervenção. Se uma execução morrer no
meio, o job é automaticamente devolvido à fila após
`ALBERTO_JOB_LEASE_MINUTES`; após `ALBERTO_JOB_MAX_ATTEMPTS` tentativas ele é
marcado como `FAILED`, evitando loops infinitos. Consulte a saúde da fila sem
expor os dados privados:

```bash
curl -fsS http://127.0.0.1:8000/alberto/jobs/summary \
  -H "Authorization: Bearer $PRIVACY_AGENT_ALBERTO_TOKEN"
```

Para automatizar também o lado seguro do Privacy Agent (descobrir contas no
Gmail já autorizado, resolver controladores e criar rascunhos), instale o
timer incluído. Ele nunca aprova, envia emails, submete portais, nem tenta
passar por MFA/CAPTCHA:

```bash
sudo install -m 644 deploy/alberto-privacy-autopilot.service /etc/systemd/system/
sudo install -m 644 deploy/alberto-privacy-autopilot.timer /etc/systemd/system/
sudo install -m 644 deploy/alberto-privacy-telegram.service /etc/systemd/system/
sudo install -m 644 deploy/alberto-privacy-telegram.timer /etc/systemd/system/
# Edite WorkingDirectory no .service para apontar para este clone antes de ativar.
sudo systemctl daemon-reload
sudo systemctl enable --now alberto-privacy-autopilot.timer
sudo systemctl enable --now alberto-privacy-telegram.timer
```

O timer executa `scripts/run_autopilot.py` a cada 15 minutos. A primeira
autorização OAuth do Gmail continua sendo interativa; depois disso, o token é
renovado normalmente em background.

## Aprovação de emails pelo Telegram

Crie um bot com o BotFather, inicie uma conversa com ele e configure o token e
o ID numérico do seu chat no `.env`. O autopilot faz polling para a API do
Telegram; não há webhook nem porta pública adicional. Para cada rascunho com
destinatário de email verificado, ele envia uma mensagem com **Aprovar e
enviar** e **Recusar**. Só aquele chat pode responder. A aprovação contém uma
capacidade de uso único, guardada no banco apenas como hash, e o próximo ciclo
envia o email automaticamente. O timer separado de Telegram faz esse ciclo a
cada minuto, portanto a aprovação normalmente é atendida em até um minuto.
Recusar não apaga o rascunho nem envia nada.
