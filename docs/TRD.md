# Technical requirements and decisions

Use [project status](PROJECT_STATUS.md) for delivered behavior. This document records implementation decisions and standards; it does not duplicate setup commands, schemas or API payloads.

## Current integration decision record (7 November 2026)

The Phase 1 demo architecture pairs local MiniLM embeddings (sentence-transformers/all-MiniLM-L6-v2, 384 dimensions) with Groq hosted generation (openai/gpt-oss-120b). The Google hosted embedder (gemini-embedding-001, 	ext-embedding-004) is implemented and verified offline in ackend/app/services/ingestion/google_embedder.py but kept disabled (EMBEDDING_PROVIDER="local") for the demo to preserve existing 384-d vectors and zero-cost operation.

Project direction remains free-first:  expenditure, no billing upgrades, and no automatic model/provider fallback. Groq openai/gpt-oss-120b is the confirmed generation model. PR #13 merged hosted transport; PR #15 supplies the generation harness; PR #16 merged offline dispatch protection and quota ledger; PR #19 merged input token validation and candidate splitting; PR #21 wires generation into backend dependencies. Local Ollama LLM hosting is deprecated and refused.

Hassan's CLI proposal described a parallel hosted index, immutable configuration profile and explicit resumable re-embedding while preserving legacy vectors. That is an unimplemented preservation design, not approval to alter data. No plain ALTER converts 384-dimensional vectors into another model's space. No API calls belong in migrations; any destructive downgrade or data removal requires explicit approval.

Naveed's rev-2 handoff is a review artifact. Constructor names and new fields are proposals until coordinated; explicit masked Settings secrets are valid and must stay excluded from logs/exports. url=None is one possible default-resolution path, not mandatory. Inspect actual constructor behavior rather than assuming the url and api_base_url arguments have identical precedence.

Strict input-token enforcement remains unresolved. chars/3 is not a defensible Unicode/framing/schema bound; usage is post-call accounting. Harmony tokenization alone does not establish Groq's server prompt representation. If the agreed input cap cannot be enforced, live execution remains blocked until an explicit alternative policy is approved. Do not silently relax it.

Reasoning_effort=low and include_reasoning=false are proposed controls; hiding reasoning does not establish reduced completion usage/billing. Resolve whether all reasoning and visible output fit the completion cap before claiming enforcement.

Any provider schema projection must be deliberate and provider-aware: retain names, structure and required/null semantics; keep all canonical local constraints. Undocumented keywords are not confirmed rejected. Do not use recursive filters that accidentally remove properties. Canonical validation stays authoritative; structured output does not prove factual support.

## Approved hosted-API and reuse decision (2 November 2026)

For the Phase 1 demo, generation uses Groq hosted API (openai/gpt-oss-120b) while embeddings use local MiniLM (sentence-transformers/all-MiniLM-L6-v2, 384 dimensions). The Google hosted embedder is implemented and verified offline in ackend/app/services/ingestion/google_embedder.py but kept disabled (EMBEDDING_PROVIDER="local") for the Phase 1 demo to preserve existing 384-d vectors and zero-cost operation. Laptop Ollama LLM hosting is deprecated and refused.

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
| Embeddings | Local MiniLM (sentence-transformers/all-MiniLM-L6-v2, 384-d) for demo; Google embedder present in codebase but off |
| Chunking | Source-preserving candidate proposal with bounded exact token validation and splitting merged (PR #19) |
| Generation | Groq hosted provider (openai/gpt-oss-120b), offline fake provider; PR #13 transport, PR #21 wiring |
| Model host | Hosted Groq generation; local MiniLM embeddings for demo; no laptop LLM inference or model tunnel |
| Frontend | Vite + React 19 UI in rontend/app merged on origin/main (PR #23) |
| Ingestion | Persisted jobs with explicit interruption/retry behavior; no durable worker implemented |
| CI | GitHub Actions workflow committed (.github/workflows/ci.yml) running backend and frontend checks |

[backend/requirements.txt](../backend/requirements.txt) is the dependency source of truth. Its minimum bounds are not a lockfile. Installed auth/parsing/ML packages do not implement features. Do not add unused provider SDKs, ChromaDB, Redis/Celery or a second storage engine by default.

Alternate embedding dimensions require a schema/index migration and full re-embedding. Switching model_name alone cannot make vectors compatible. Hosted transport (PR #13), offline embedding dispatch protection (PR #16), and hosted input validation (PR #19) are merged; final model/configuration, API wiring, live token correspondence, and corpus activation remain pending.

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
