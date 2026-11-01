# Technical requirements and decisions

Use [project status](PROJECT_STATUS.md) for delivered behavior. This document records implementation decisions and standards; it does not duplicate setup commands, schemas or API payloads.

## Selected foundation

| Area | Baseline |
|---|---|
| Backend | Python 3.12, FastAPI, Pydantic v2, async SQLAlchemy 2, asyncpg |
| Persistence | PostgreSQL 16, pgvector, Alembic; one database engine |
| Embeddings | all-MiniLM-L6-v2, 384 dimensions; service implementation pending |
| Chunking | Embedding-tokenizer-aware initial budget 240 tokens / 32 overlap, checked against runtime model/special-token limits |
| Generation | Explicit fake/Ollama provider, async H01 boundary and canonical structured result |
| Model host | Naveed's laptop; explicit installed model tag for evaluation, currently llama3.2:3b baseline |
| Frontend | React + TypeScript; Zaid must confirm Vite/Next.js before scaffolding |
| Ingestion | Persisted jobs with explicit interruption/retry behavior; no durable worker implemented |
| CI | No committed workflow or attached PR checks; do not claim automation |

[backend/requirements.txt](../backend/requirements.txt) is the dependency source of truth. Its minimum bounds are not a lockfile. Installed auth/parsing/ML packages do not implement features. Do not add unused provider SDKs, ChromaDB, Redis/Celery or a second storage engine by default.

Alternate embedding dimensions require a schema/index migration and full re-embedding. Switching model_name alone cannot make vectors compatible. A hosted generation adapter is not selected or implemented.

## Configuration boundaries

[Settings](../backend/app/core/config.py) loads the repository-root `.env` independently of process cwd. Environment variables override it; settings are cached. Keep secrets out of browser variables, source and logs.

`DATABASE_URL` is a standalone async connection URL; `POSTGRES_*` configures Compose and does not derive it. Default host/container ports are 5435/5432. `DATABASE_SYNC_URL` is not used by the current async Alembic environment.

`API_V1_PREFIX` defaults to `/api/v1`. `BACKEND_CORS_ORIGINS` supports a JSON array. `DEBUG` enables SQL echo. `SECRET_KEY`/token settings are development placeholders, not authentication.

Generation has its own explicit constructor/process-environment controls. Pydantic loading does not export root `.env`; the [generation README](../backend/app/services/generation/README.md) owns exact names, precedence and examples. The current general model default differs from the explicit 3B evaluation tag, so pass a tag deliberately.

## Engineering standards

- Reuse canonical types through `app.schemas`; review contract/model/schema/example changes together.
- Keep async network/database work bounded and preserve external cancellation. Move CPU/blocking parsing/embedding off the request event loop.
- No schema creation or implicit seeding on startup; apply reviewed migrations only to approved targets.
- Persist accepted ingestion work before 202. A row plus FastAPI background task does not provide durable execution.
- Filter organization and current parent-document permissions before pagination/retrieval evidence leaves the backend.
- Do not silently truncate context or equate characters with tokens. Preserve the documented generation context limitation.
- Use typed service errors and map them at the API boundary. Never return provider failures as evidence-based abstention.
- Use type hints, focused modules and safe structured logging. No secrets or private document text in ordinary diagnostics.
- Add focused offline regressions; real DB/model/browser checks are separately identified and approved.
- Use actual configured tools/scripts; Ruff, coverage and load tooling are not configured merely because designs mention them.

[API inventory](API_SPEC.md), [database schema](DATABASE_SCHEMA.md), [security](SECURITY_MODEL.md), [evaluation](EVALUATION_STRATEGY.md) and [setup](../CONTRIBUTING.md) own their detailed contracts and commands.
