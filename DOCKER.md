# SmashGo com Docker

O ambiente contém dois serviços:

- `frontend`: aplicação React compilada e servida pelo Nginx na porta `8080`;
- `backend`: API FastAPI acessível pelo frontend através de `/api`, sem exposição direta ao host.

O PostgreSQL fica no volume persistente `smashgo_postgres_data` e é publicado na porta `5432` para acesso pelo DBeaver.

## Pré-requisitos

- Docker Desktop com Docker Compose v2.

## Primeira execução

Na raiz do projeto:

```powershell
Copy-Item .env.example .env
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

Para executar os testes dentro de uma imagem isolada:

```powershell
docker build --target runtime -t smashgo-api ./backend
docker run --rm --entrypoint python smashgo-api -m compileall -q app
```

## Persistência e remoção

`docker compose down` preserva os pedidos. Para também excluir permanentemente o PostgreSQL, use `docker compose down --volumes`. Essa segunda operação é destrutiva.

## Segurança

- A API roda como usuário sem privilégios dentro do contêiner.
- Apenas o Nginx publica uma porta no host; a API permanece na rede interna.
- O cabeçalho de versão do servidor é desabilitado.
- A senha administrativa vem do `.env`, que não entra no contexto de build.
- O banco não é gravado na camada descartável do contêiner, mas em volume nomeado.
