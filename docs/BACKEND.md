# SmashGo API

API FastAPI com PostgreSQL para o totem existente em `src/frontend`. O catálogo é inicializado com os 12 produtos da interface e os preços são sempre recalculados no servidor.

## Executar

```powershell
cd src/backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
uvicorn app.main:app --env-file .env --reload
```

O comando acima carrega explicitamente o `.env` local; variáveis já exportadas têm prioridade. Em produção, altere obrigatoriamente `ADMIN_PASSWORD` e `CPF_ENCRYPTION_KEY`, preserve a chave de CPF em backup e restrinja `ALLOWED_ORIGINS`.

- API: `http://localhost:8000`
- Swagger: `http://localhost:8000/docs`
- OpenAPI: `http://localhost:8000/openapi.json`

## Fluxo do frontend

1. `GET /api/v1/categories` e `GET /api/v1/products`
2. `POST /api/v1/orders` com cliente, CPF e itens
3. `POST /api/v1/orders/{id}/payments`
4. `GET /api/v1/orders/{id}` para acompanhar o estado e exibir a senha

Atualizações de pagamento/pedido são administrativas e exigem Bearer token obtido em `POST /api/v1/auth/login`.

## Segurança exigida pelo documento

- Toda entrada vai para o PostgreSQL usando parâmetros `%s`; valores do usuário nunca são concatenados ao SQL. A única composição dinâmica é a quantidade controlada de placeholders.
- Exceções inesperadas recebem um identificador, ficam detalhadas no log do servidor e retornam uma mensagem genérica, sem stack trace.
- O login aceita no máximo 10 tentativas por IP numa janela de 60 segundos e retorna `429` com `Retry-After` durante o bloqueio.
- Validação de CPF, limites de tamanho/quantidade e preços calculados exclusivamente pelo servidor.

## Testes

Configure DATABASE_URL para um PostgreSQL exclusivo de testes antes de executar; os testes gravam dados. Consulte o [README da raiz](../README.md#testes).

```powershell
# Na raiz do projeto
src/backend/.venv/Scripts/python.exe -m pytest -c config/pytest.ini tests
```

## Docker

As instruções para executar frontend e backend juntos estão em [`DOCKER.md`](DOCKER.md).
