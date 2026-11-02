# KNEXUS

Knowledge Network for EXploration and Unified Services is a three-member academic project for cited answers over permitted organizational documents, followed by one human-approved sandbox action.

## Approved direction

KNEXUS will use hosted APIs for generation and embeddings and selectively adapt code/features from Hassan's [pinned personal project](https://github.com/Hassan092-prog/enterprise-knowledge-bot/tree/e67771a15f49a79443a365fbce85b8559ef43fb7). No local model hosting, downloads or Ollama tunnels belong to the revised setup. [Technical decisions](docs/TRD.md) owns reuse, privacy, provider selection and embedding migration policy.

Existing code still contains fake/Ollama generation and local 384-dimensional MiniLM embeddings. Hosted adapters are not implemented by this documentation update. Provider/model choices, credentials and hosted acceptance remain pending; Phase 1 is incomplete.

## Start here

- [Project status](docs/PROJECT_STATUS.md): delivered work, evidence and next tasks.
- [Setup and Git workflow](CONTRIBUTING.md): environments, branches and laptop/server connections.
- [Phase 1 playbook](docs/PHASE_1_TEAM_GUIDE.md): ordered tasks and completion gates.
- [Documentation index](docs/INDEX.md): requirements, contracts, designs and academic references.

## What exists

The backend foundation is merged into `main` through PR #4, PR #5, and [PR #7](https://github.com/Hassan092-prog/KNEXUS/pull/7). See [Project status](docs/PROJECT_STATUS.md) for pull request history and dated verification evidence.

Implemented capabilities before the hosted migration:
- Canonical Phase 1 contracts and schemas in `contracts/phase1/models.py`.
- Async generation boundary (`run_generation`) with explicit fake/Ollama providers, structured evidence validation, and safe error mapping.
- Six PostgreSQL/pgvector ORM tables, Alembic migrations, and explicit demo identity seeding.
- Document ingestion pipeline supporting PDF/DOCX parsing (up to 10 MiB), tokenizer-aware chunking (240 tokens ceiling, 32-token overlap), local MiniLM embeddings (384 dimensions), and private storage.
- In-process processor lifecycle (`queued`, `processing`, `complete`, `failed`) with guarded operator recovery.
- SQL-level tenant isolation and role-filtered retrieval before pagination/top-k ranking.
- Canonical document management routes (`POST /upload`, `GET /documents`, `GET /{id}`, `GET /{id}/status`) and query route (`POST /query`).
- Offline checks and opt-in disposable PostgreSQL/pgvector tests; dated evidence is recorded in project status, not recomputed by this documentation update.

The shared database remains unmigrated. Historical MiniLM verification does not satisfy the revised hosted-embedding gate. Hosted embedding/generation integration, live quality and browser acceptance remain incomplete.

## Local development

Use Python 3.12 for the backend. Docker is needed for a local PostgreSQL instance; offline generator checks need neither Docker nor Ollama. Follow [CONTRIBUTING.md](CONTRIBUTING.md) for Linux and Windows commands. Existing shared services and databases require explicit approval before changes.

Registered routes:
- `GET /` and `GET /api/v1/health`
- `POST /api/v1/documents/upload`
- `GET /api/v1/documents`
- `GET /api/v1/documents/{document_id}`
- `GET /api/v1/documents/{document_id}/status`
- `POST /api/v1/query`
- Swagger at `/docs`, ReDoc at `/redoc`, OpenAPI at `/api/v1/openapi.json`

## Source layout

| Path | Purpose |
|---|---|
| `backend/app/` | API, settings, canonical imports, generation and persistence models |
| `backend/alembic/`, `alembic.ini` | Explicit schema migrations; no startup table creation |
| `backend/tests/` | Offline checks and opt-in disposable database integration suite |
| `contracts/phase1/` | Canonical models, generated schema and synthetic wire examples |
| `frontend/` | Instructions; no application scaffold is committed |
| `data/` | Corpus policy; no benchmark corpus/importer is committed |
| `docker/`, `docker-compose.yml` | PostgreSQL development bootstrap |
| `docs/` | Product/technical documentation and academic references |

The repository has four persistent branches: `main`, `dev-hassan`, `dev-naveed` and `dev-zaid`. Member ownership is maintained in [team responsibilities](docs/TEAM_RESPONSIBILITIES.md).

Major Project Team 3, MJCET CSE (AI&ML), academic year 2026-2027.
