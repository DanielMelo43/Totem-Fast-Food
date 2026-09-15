# SmashGo

Sistema de autoatendimento para fast-food com frontend React/Vite, API FastAPI e PostgreSQL.

## Estrutura

```text
src/
  api/index.py        # Entrada serverless da API
  backend/            # API, Dockerfile, requirements.txt e .env.example
    app/
  frontend/           # React/Vite, package.json, lockfile, Dockerfile e nginx.conf
    src/
    public/assets/    # Imagens exclusivas da interface
tests/backend/       # Testes automatizados da API
docs/                # Backend, Docker e especificações
assets/              # Recursos compartilhados entre aplicações
config/pytest.ini    # Caminhos e descoberta dos testes
pyproject.toml       # Entrada FastAPI da Vercel em src/api/index.py
docker-compose.yml   # Serviços e volume persistente do PostgreSQL
vercel.json          # Build e roteamento da Vercel
requirements.txt     # Dependências da função Python na Vercel
.env.example         # Modelo de ambiente do Docker Compose
.gitignore
README.md
```

Não há necessidade atual de `data/`: o PostgreSQL utiliza um volume Docker. Os arquivos exigidos pelas ferramentas permanecem na raiz ou junto à respectiva aplicação. `assets/` está reservado para recursos compartilhados; a imagem atual permanece no `public` do frontend.

## Executar com Docker

Na raiz, copie `.env.example` para `.env` **somente se o arquivo ainda não existir**. Configure as credenciais e a chave de criptografia e execute:

```powershell
docker compose up --build -d
```

Acesse `http://localhost:8080`. O Compose lê o `.env` da raiz e injeta as variáveis no backend; o banco permanece no volume `smashgo_postgres_data`.

Veja [operação com Docker](docs/DOCKER.md) e [documentação da API](docs/BACKEND.md).

## Desenvolvimento local

Pré-requisitos: Python 3.13, Node.js 22 com npm e PostgreSQL acessível. Execute os comandos abaixo a partir da raiz, em terminais separados para backend e frontend.

### Backend

```powershell
python -m venv src/backend/.venv
src/backend/.venv/Scripts/python.exe -m pip install -r src/backend/requirements.txt
```

Crie `src/backend/.env` a partir de `src/backend/.env.example` se ainda não existir e ajuste `DATABASE_URL`, `ADMIN_USERNAME`, `ADMIN_PASSWORD`, `CPF_ENCRYPTION_KEY` e `ALLOWED_ORIGINS`. Para desenvolvimento com Vite, permita `http://localhost:5173`.

```powershell
src/backend/.venv/Scripts/python.exe -m uvicorn app.main:app --app-dir src/backend --env-file src/backend/.env --reload
```

O argumento `--env-file` carrega explicitamente o ambiente local (suportado por `uvicorn[standard]`, já declarado nas dependências). A aplicação lê variáveis do processo; ela não procura arquivos `.env` automaticamente. Variáveis já exportadas têm prioridade. Não substitua chaves de um banco existente.

API: `http://localhost:8000`; Swagger: `http://localhost:8000/docs`.

### Frontend

```powershell
npm.cmd ci --prefix src/frontend
$env:VITE_API_URL = 'http://localhost:8000/api/v1'
npm.cmd run dev --prefix src/frontend
```

Acesse `http://localhost:5173`. `VITE_API_URL` também pode ser configurada em `src/frontend/.env.local`; reinicie o Vite após alterações. Sem essa variável, a interface usa `/api/v1`, como no Docker e na Vercel. Variáveis `VITE_*` são públicas no build e não devem conter segredos.

No Windows, `npm.cmd` evita depender da permissão de execução do script `npm.ps1`. Em Linux/macOS, use `npm` e o Python em `src/backend/.venv/bin/python`.

## Testes

Para executar os testes em Docker com banco temporário, veja [testes de integração isolados](docs/DOCKER.md#testes-de-integração-isolados).

Os testes existentes são de integração e precisam de um PostgreSQL **exclusivo para testes**, pois criam tabelas e gravam clientes, pedidos e pagamentos. Configure a conexão no terminal antes de executar:

```powershell
$env:DATABASE_URL = 'postgresql://USUARIO:SENHA@localhost:5432/smashgo_test'
src/backend/.venv/Scripts/python.exe -m pytest -c config/pytest.ini tests -q
```

Substitua os campos da conexão por valores do banco de testes. O pytest não carrega `.env` automaticamente. Sua configuração centralizada inclui `src/backend` no caminho de imports; não é necessário alterar `PYTHONPATH` manualmente.

Para apenas conferir a descoberta dos testes, sem acessar o banco:

```powershell
src/backend/.venv/Scripts/python.exe -m pytest -c config/pytest.ini tests --collect-only -q
```

## Build e verificação de configuração

```powershell
npm.cmd run build --prefix src/frontend
python -m compileall -q src/backend/app src/api tests
docker compose config --quiet
```

O build é gerado em `src/frontend/dist`. Os Dockerfiles mantêm seus contextos locais, referenciados pelo Compose. `vercel.json` aponta para a nova localização do frontend e `src/api/index.py` importa a API de `src/backend`.

## Segurança

- CPFs são armazenados com criptografia autenticada e pesquisados por um índice HMAC.
- Preços são recalculados no servidor.
- Consultas ao PostgreSQL usam parâmetros.
- Rotas administrativas exigem Bearer token.
- O login administrativo possui limitação de tentativas.
- Credenciais e chaves são fornecidas por variáveis de ambiente e não devem ser versionadas.

Guarde `CPF_ENCRYPTION_KEY` em local seguro. Sem essa chave, CPFs existentes não podem ser recuperados.

A entrada personalizada da Vercel é declarada em `pyproject.toml` como `src.api.index:app`, conforme a [documentação oficial](https://vercel.com/docs/frameworks/backend/fastapi#exporting-the-fastapi-application).
