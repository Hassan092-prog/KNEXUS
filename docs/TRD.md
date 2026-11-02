# Technical requirements and decisions

Use [project status](PROJECT_STATUS.md) for delivered behavior. This document records implementation decisions and standards; it does not duplicate setup commands, schemas or API payloads.

## Approved hosted-API and reuse decision (2 November 2026)

This decision supersedes laptop Ollama and local MiniLM hosting. Both generation and embedding inference must use hosted APIs. Offline fakes remain explicit test tools, never silent fallbacks.

Selectively adapt relevant code/features from [enterprise-knowledge-bot](https://github.com/Hassan092-prog/enterprise-knowledge-bot/tree/e67771a15f49a79443a365fbce85b8559ef43fb7), pinned to `e67771a15f49a79443a365fbce85b8559ef43fb7`. Inspect that revision before reuse; do not silently substitute newer source. Preserve applicable copyright/licence notices and accurate authorship. Verify actual adaptation through code review; this decision is not proof that migration is complete.

Hassan adapts backend models, parsing/chunking, API and retrieval to KNEXUS's async layout and PostgreSQL/pgvector. Naveed adapts hosted generation/provider code. Zaid adapts and redesigns useful frontend components. Do not import ChromaDB, duplicate database engines, old entry points, CSV agents, Graph RAG, Redis/Celery, unused SDKs, secrets or source data stores by default.

Agree generation and embedding provider/model/endpoint, model revision/dimension, credential setup, privacy/retention, token limits, deadlines, rate limits and spending authorization before live use. No provider/model or new environment-variable contract is selected here. Use mocked HTTP pending reviewed adapters and authorized credentials/billable calls; do not run local inference as a substitute.

Storage currently enforces vector(384). Even a different 384-dimensional model creates a different vector space: re-embed the corpus and use the identical model/revision for queries and documents. A dimension change additionally requires a reviewed schema/index migration. Do not change a model name alone or mix old MiniLM vectors with hosted query vectors.

Preserve original source text and validate chunking against the hosted embedding model's actual token policy. Historical 240-token/32-overlap defaults remain compatibility defaults until validated; MiniLM limits do not establish hosted limits. The generation character ceiling is not token counting or proof of context fit.

Only the backend holds provider credentials and calls hosted APIs. Review third-party retention/data policy before sending synthetic-first document text or authorized evidence. No credentials in browser variables, Git, chat or logs. No silent model switching or local fallback on provider failure.

Preserve canonical GenerationRequest, EvidenceChunk, GenerationResult, H01 run_generation, tenant permissions, cancellation, bounded failures and public API errors. Validate embedding dimensions, finite values and model/revision provenance. Coordinate shared settings/contracts before changing them.

## Selected foundation

| Area | Baseline |
|---|---|
| Backend | Python 3.12, FastAPI, Pydantic v2, async SQLAlchemy 2, asyncpg |
| Persistence | PostgreSQL 16, pgvector, Alembic; one database engine |
| Embeddings | Target: hosted API, provider/model pending; historical MiniLM and vector(384) need coordinated migration |
| Chunking | Preserve source; validate historical 240/32 defaults against the hosted model's actual token limits |
| Generation | Target: hosted API through H01; existing fake/Ollama adapters are historical implementation |
| Model host | Hosted APIs; no laptop/server inference or model tunnel |
| Frontend | React + TypeScript; Zaid must confirm Vite/Next.js before scaffolding |
| Ingestion | Persisted jobs with explicit interruption/retry behavior; no durable worker implemented |
| CI | No committed workflow or attached PR checks; do not claim automation |

[backend/requirements.txt](../backend/requirements.txt) is the dependency source of truth. Its minimum bounds are not a lockfile. Installed auth/parsing/ML packages do not implement features. Do not add unused provider SDKs, ChromaDB, Redis/Celery or a second storage engine by default.

Alternate embedding dimensions require a schema/index migration and full re-embedding. Switching model_name alone cannot make vectors compatible. Hosted adapters are required by the revised plan; selection and implementation remain pending.

## Configuration boundaries

[Settings](../backend/app/core/config.py) loads the repository-root `.env` independently of process cwd. Environment variables override it; settings are cached. Keep secrets out of browser variables, source and logs.

`DATABASE_URL` is a standalone async connection URL; `POSTGRES_*` configures Compose and does not derive it. Default host/container ports are 5435/5432. `DATABASE_SYNC_URL` is not used by the current async Alembic environment.

`API_V1_PREFIX` defaults to `/api/v1`. `BACKEND_CORS_ORIGINS` supports a JSON array. `DEBUG` enables SQL echo. `SECRET_KEY`/token settings are development placeholders, not authentication.

Generation has its own explicit constructor/process-environment controls. Pydantic loading does not export root `.env`; the [generation README](../backend/app/services/generation/README.md) owns exact names, precedence and examples. Existing OLLAMA_* and MiniLM defaults are historical code paths, not hosted configuration. Implement and review hosted settings before documenting runnable commands.

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
