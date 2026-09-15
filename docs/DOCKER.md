# SmashGo com Docker

O ambiente contém três serviços:

- `database`: PostgreSQL 17 com volume persistente e verificação de disponibilidade;
- `frontend`: aplicação React compilada e servida pelo Nginx na porta `8080`;
- `backend`: API FastAPI acessível pelo frontend através de `/api`, sem exposição direta ao host.

O PostgreSQL fica no volume persistente `smashgo_postgres_data` e é publicado na porta `5432` para acesso pelo DBeaver.

## Pré-requisitos

- Docker Desktop com Docker Compose v2.

## Primeira execução

Na raiz do projeto:

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

Edite `.env` e substitua `ADMIN_PASSWORD`, `POSTGRES_PASSWORD` e `CPF_ENCRYPTION_KEY` por segredos fortes. Preserve a chave do CPF em backup: sem ela, os CPFs existentes não podem ser recuperados. Depois execute:

```powershell
docker compose up --build -d
```

Acesse o sistema em `http://localhost:8080`. A API é encaminhada pelo mesmo endereço em `http://localhost:8080/api/v1`.

## Conectar pelo DBeaver

- Tipo: PostgreSQL
- Host: `localhost`
- Porta: `5432`
- Banco: `smashgo`
- Usuário: `smashgo`
- Senha: o valor de `POSTGRES_PASSWORD` no arquivo `.env`

## Operação

```powershell
# Ver estado e saúde dos serviços
docker compose ps

# Acompanhar logs
docker compose logs -f

# Parar os contêineres sem apagar o banco
docker compose down

# Reconstruir depois de alterar o código
docker compose up --build -d
```

Para verificar a compilação Python dentro de uma imagem isolada (não executa os testes automatizados):

```powershell
docker build --target runtime -t smashgo-api ./src/backend
docker run --rm --entrypoint python smashgo-api -m compileall -q app
```

## Persistência e remoção

`docker compose down` preserva os pedidos. Para também excluir permanentemente o PostgreSQL, use `docker compose down --volumes`. Essa segunda operação é destrutiva.

## Segurança

- A API roda como usuário sem privilégios dentro do contêiner.
- O Nginx e o PostgreSQL publicam portas no host; a API permanece na rede interna.
- O cabeçalho de versão do servidor é desabilitado.
- A senha administrativa vem do `.env`, que não entra no contexto de build.
- O banco não é gravado na camada descartável do contêiner, mas em volume nomeado.

## Portas ocupadas por outro projeto

O Compose utiliza `FRONTEND_PORT` e `POSTGRES_PORT` do `.env` (padrões: 8080 e 5432). Para executar em paralelo com outro projeto sem editar o arquivo, use no PowerShell:

```powershell
$env:FRONTEND_PORT = '8081'
$env:POSTGRES_PORT = '5433'
docker compose up --build -d --wait --wait-timeout 120
```

Nesse caso, acesse `http://localhost:8081` e configure o DBeaver na porta `5433`. Execute os comandos de atualização no mesmo terminal ou exporte novamente essas variáveis. A comunicação interna continua usando `database:5432` e `backend:8000`; a origem permitida pelo backend acompanha `FRONTEND_PORT`.

## Testes de integração isolados

Na raiz do projeto:

```powershell
docker compose -p smashgo-tests -f config/compose.test.yml up --build --abort-on-container-exit --exit-code-from tests
docker compose -p smashgo-tests -f config/compose.test.yml down
```

O serviço `tests` usa a imagem do backend e monta `tests/` somente para leitura. O PostgreSQL de testes usa armazenamento temporário em memória, sem publicar portas nem acessar o volume da aplicação. A primeira operação retorna o código de saída do pytest; a segunda remove os contêineres temporários. Os dados de teste são descartados ao parar o banco.

## Verificações rápidas

```powershell
docker compose config --quiet
docker compose exec frontend nginx -t
docker compose ps
```

Verifique a página inicial, `/health-api`, `/api/v1/products` e `/assets/welcome-food.png` na porta do frontend. Os três serviços devem aparecer como `healthy`.

## Estrutura dos builds

- Backend: contexto `src/backend`, Python 3.13, dependências do `requirements.txt`, processo sem privilégios e verificação em `/health`.
- Frontend: contexto `src/frontend`, build com Node.js 22 e `npm ci`, saída servida pelo Nginx com proxy `/api/` para o backend.
- Banco: PostgreSQL 17, disponibilidade verificada antes da inicialização do backend e volume persistente preservado.
- `src/api/index.py` é a entrada para Vercel. Docker continua executando `app.main:app` diretamente, sem depender dessa entrada.
