# KNEXUS

Knowledge Network for EXploration and Unified Services is a three-member academic project for cited answers over permitted organizational documents, followed by one human-approved sandbox action.

## Start here

- [Project status](docs/PROJECT_STATUS.md): delivered work, evidence and next tasks.
- [Setup and Git workflow](CONTRIBUTING.md): environments, branches and laptop/server connections.
- [Phase 1 playbook](docs/PHASE_1_TEAM_GUIDE.md): ordered tasks and completion gates.
- [Documentation index](docs/INDEX.md): requirements, contracts, designs and academic references.

## What exists

The reviewed generation and persistence baseline is merged into `main` through [PR #5](https://github.com/Hassan092-prog/KNEXUS/pull/5) at `5104a19e61f35d4a10e38000737e68513069f2a5`, preserving the persistence work reviewed in PR #4. See [project status](docs/PROJECT_STATUS.md) for remaining tasks.

Implemented code includes FastAPI root/health routes, canonical contract models, a server-owned synthetic actor, an injectable async generation boundary with explicit fake/Ollama providers, six PostgreSQL/pgvector ORM tables, an initial Alembic migration and offline tests. Persistence was also verified using a separate disposable database. The shared database has not been migrated.

Upload, parsing, embedding inference, retrieval and query APIs, authentication, approval/audit features and the frontend application remain to be implemented. The generation adapter is not wired into an HTTP query route. Live Ollama quality and an end-to-end browser flow remain unverified.

## Local development

Use Python 3.12 for the backend. Docker is needed for a local PostgreSQL instance; offline generator checks need neither Docker nor Ollama. Follow [CONTRIBUTING.md](CONTRIBUTING.md) for Linux and Windows commands. Existing shared services and databases require explicit approval before changes.

Implemented application routes are `GET /` and `GET /api/v1/health`, with Swagger at `/docs`, ReDoc at `/redoc` and OpenAPI at `/api/v1/openapi.json`. Health HTTP 200 is a diagnostic response, not proof of generation, migrations or readiness.

## Source layout

| Path | Purpose |
|---|---|
| `backend/app/` | API, settings, canonical imports, generation and persistence models |
| `backend/alembic/`, `alembic.ini` | Explicit schema migrations; no startup table creation |
| `backend/tests/` | Offline boundary/generation/persistence checks and opt-in live harness |
| `contracts/phase1/` | Canonical models, generated schema and synthetic wire examples |
| `frontend/` | Instructions; no application scaffold is committed |
| `data/` | Corpus policy; no benchmark corpus/importer is committed |
| `docker/`, `docker-compose.yml` | PostgreSQL development bootstrap |
| `docs/` | Product/technical documentation and academic references |

The repository has four persistent branches: `main`, `dev-hassan`, `dev-naveed` and `dev-zaid`. Temporary integration/review branches have been retired after preserving their work in main. Member ownership is maintained in [team responsibilities](docs/TEAM_RESPONSIBILITIES.md).

Major Project Team 3, MJCET CSE (AI&ML), academic year 2026-2027.
