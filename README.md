# blog_be

`blog_ui` (Next.js)의 백엔드. FastAPI + PostgreSQL + async SQLAlchemy 기반.

## Stack

- Python 3.14.5
- FastAPI · Uvicorn
- SQLAlchemy 2.0 (async, asyncpg)
- PostgreSQL 16
- pytest-asyncio · ruff · mypy(strict)

> Schema is created via `Base.metadata.create_all()` on app startup (idempotent).
> No migration tool — column/type changes are done by manual DDL on the live DB.

## Getting started

```bash
# 1) Postgres
docker compose up -d postgres

# 2) venv & deps
python3.14 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3) env  (layered, Next.js-style — see "Env files" below)
cp .env.example .env
# Fill JWT_PRIVATE_KEY_PEM (openssl genrsa) and ADMIN_PASSWORD_HASH.
# Keep secrets in .env.local (gitignored), not in committed files.

# 4) seed (tables get created lazily on first connect)
python -m seed.fixtures

# 5) run
python main.py --env local --debug
```

- Swagger UI: http://127.0.0.1:8080/swagger_ui
- ReDoc: http://127.0.0.1:8080/redoc

When running blog_be alongside the local gateway, start blog_be on port 8000
(`APP_PORT=8000 python main.py --env local`) — the gateway's `application-local.yaml`
points its JWKS URI at `http://localhost:8000/.well-known/jwks.json` because its own
server uses 8080.

## Layout

```
api/         # FastAPI routers (root_router → v1/)
app/
  core/      # config, db, exception, security, utils
  post/      # domain / application / infrastructure
  tag/
seed/        # fixtures import
tests/
docs/contract/  # FE 계약 문서 (BACKEND.md, fixtures.ts, index.ts)
```

## Env files

Layered, Next.js-style. `{env}` is what you pass to `main.py --env` (default `local`).
Later files override earlier ones — only set the keys you actually want to override.

| File               | Priority                               | Committed?              |
|--------------------|----------------------------------------|-------------------------|
| `.env`             | lowest — common defaults               | only if values are safe |
| `.env.{env}`       | env-specific defaults                  | only if values are safe |
| `.env.local`       | personal/local overrides               | **never** (gitignored)  |
| `.env.{env}.local` | highest — env-specific local overrides | **never** (gitignored)  |

Typical setup:

- `.env` with shared dev defaults
- `.env.local` (gitignored) with your real secrets — copy from `.env.local.example`

## Test

```bash
# unit only (no DB)
pytest

# integration (requires real Postgres)
TEST_DATABASE_URL="postgresql+asyncpg://USER:PASS@HOST:5432/blog_test?ssl=require" \
  pytest -m integration
```
