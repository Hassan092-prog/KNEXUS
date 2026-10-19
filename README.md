# KNEXUS: Knowledge Network for EXploration and Unified Services

KNEXUS is an academic project for a local enterprise knowledge assistant with cited answers, permission-aware retrieval, and human-approved sandbox actions.

## Current implementation

As reviewed on **19 October 2026**, this repository contains a **FastAPI backend scaffold**, an async SQLAlchemy connection/session layer, a dependency health endpoint, and Docker Compose for PostgreSQL 16 with pgvector.

Document ingestion, embeddings, retrieval, LLM answer generation, authentication/RBAC, approvals, audit storage, and the React interface are **planned and not implemented**. Installing their dependencies does not enable these features. There is no feature-level test suite, migration setup, frontend package manifest or CI workflow yet. The draft shared contracts include a standalone validator and synthetic examples; they do not implement features.

See the [repository review](docs/REPOSITORY_REVIEW.md) for file coverage, findings, validation, and remaining work. The design documents describe the target system, not the current API.

The [team start guide](docs/TEAM_START.md) records member access/branches and Naveed's Ollama handoff. The [Phase 1 contract proposal](docs/PHASE_1_CONTRACT.md) and [reference fixtures](contracts/phase1/README.md) define the fields for review before integration.

## Quick start

Use Python 3.12, Git, and Docker with Compose. Run these commands from the repository root in a POSIX shell:

```bash
if [ ! -f .env ]; then
    cp .env.example .env
fi
python3.12 -m venv backend/venv
backend/venv/bin/python -m pip install -r backend/requirements.txt
docker compose up -d postgres
backend/venv/bin/python -m uvicorn app.main:app --app-dir backend --reload --host 127.0.0.1 --port 8000
```

The root working directory matters: settings read `.env` relative to the process working directory. [CONTRIBUTING.md](CONTRIBUTING.md) includes PowerShell commands, verification, configuration details, and troubleshooting. Do not overwrite an existing `.env` when repeating setup.

- API landing response: <http://localhost:8000/>
- Health: <http://localhost:8000/api/v1/health>
- Swagger: <http://localhost:8000/docs>
- ReDoc: <http://localhost:8000/redoc>
- OpenAPI: <http://localhost:8000/api/v1/openapi.json>

Ollama is optional for the scaffold. To make its health probe report online, run Ollama separately; Compose currently starts only PostgreSQL. No model is used for generation yet.

The health endpoint returns HTTP 200 even when dependencies fail. Its aggregate `status` becomes `degraded` only on a database exception; inspect the individual fields too. No authentication is enforced. Treat this as a local development scaffold.

## Repository layout

```text
backend/app/                 FastAPI routes, settings, async database plumbing
backend/requirements.txt     Dependencies (minimum versions, not a lockfile)
frontend/README.md           Planned React/TypeScript/Vite interface
data/README.md               Planned datasets and fixtures
docker/init.sql              Enables vector on first database initialization
docker-compose.yml           PostgreSQL service and persistent named volume
docs/                        Designs, roadmap, academic artifacts, research
Guidelines and NOtices/      University requirements and scanned notice
Templates/                   Original abstract and presentation templates
```

## Planned capabilities

The MVP targets PDF/DOCX ingestion, dense retrieval with pgvector, local Ollama answers, validated citations and abstention, tenant/role filtering, one governed sandbox action, and audit logging. Hybrid BM25/dense retrieval, reranking, streaming, and additional integrations follow the core path.

The [project plan](docs/KNEXUS_Project_Plan.md) defines phases 0-4 and team responsibilities. Start with the [documentation index](docs/INDEX.md) for the full reading order and reference-material status.

## Team ownership

| Member | Branch | Primary ownership |
| --- | --- | --- |
| Hassan (1) | `dev-hassan` | Backend/API, database/migrations, ingestion/retrieval, security, data/runtime and integration |
| Naveed (2) | `dev-naveed` | LLM/prompt/citation, typed tools, answer evaluation and research |
| Zaid (3) | `dev-zaid` | Entire frontend, UI verification, user manual and presentation visuals |

The [team responsibilities](docs/TEAM_RESPONSIBILITIES.md) define task and path ownership. The [Phase 1 guide](docs/PHASE_1_TEAM_GUIDE.md) gives tasks, branch commands and collaboration prompts.

## Contributors

Major Project Team 3, MJCET CSE (AI&ML), academic year 2026-2027.
