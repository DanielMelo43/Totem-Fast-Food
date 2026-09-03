# SmashGo

Sistema de autoatendimento para fast-food com frontend React, API FastAPI e PostgreSQL.

## Executar com Docker

1. Copie `.env.example` para `.env`.
2. Substitua todas as senhas e a chave de criptografia por valores fortes.
3. Execute:

```powershell
docker compose up --build -d
```

A aplicação estará disponível em `http://localhost:8080`.

Consulte [DOCKER.md](DOCKER.md) para configuração, operação, conexão pelo DBeaver e cuidados com persistência.

## Segurança

- CPFs são armazenados com criptografia autenticada e pesquisados por um índice HMAC.
- Preços são recalculados no servidor.
- Consultas ao PostgreSQL usam parâmetros.
- Rotas administrativas exigem Bearer token.
- O login administrativo possui limitação de tentativas.
- Credenciais e chaves são fornecidas por variáveis de ambiente e não devem ser versionadas.

Guarde `CPF_ENCRYPTION_KEY` em local seguro. Sem essa chave, CPFs existentes não podem ser recuperados.
