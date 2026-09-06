---
name: privacy-agent-bridge
description: Processa de forma restrita um trabalho pendente do Privacy Agent.
---

Use somente a API local `http://127.0.0.1:8000` e o token em
`/home/alberto/.config/alberto/privacy-agent-bridge.env`.

1. Leia o token sem o exibir e faça `POST /alberto/jobs/next` com o header
   `Authorization: Bearer <token>`.
2. Se a resposta for `null`, termine respondendo somente `NO_REPLY`.
3. Use exclusivamente as páginas e instruções presentes no `payload` do job.
   Não navegue para novas páginas e não acesse Gmail, PostgreSQL, arquivos de
   casos nem outras rotas do Privacy Agent.
4. Para cada dado, inclua evidência somente se `source_url` estiver no job e
   `excerpt` ocorrer literalmente no texto daquela página. Se não houver
   evidência suficiente, deixe os campos vazios e use `evidence: []`.
5. Ao terminar, conclua o mesmo job com `POST /alberto/jobs/<id>/complete`.
   O corpo JSON é obrigatoriamente embrulhado por `result`; por exemplo:

   ```json
   {"result":{"controller_name":"","controller_country":"","dpo_contact":"","privacy_request_url":"","evidence":[]}}
   ```

   Nunca envie apenas `{"evidence":[]}`: isso falha porque o campo `result`
   é obrigatório.
6. Use `{"error":"motivo"}` somente se o job for impossível de processar.
   Não envie comunicações externas nem solicitações de privacidade.
