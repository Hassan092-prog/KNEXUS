# KNEXUS

Knowledge Network for EXploration and Unified Services is a three-member academic project for cited answers over permitted organizational documents, followed by one human-approved sandbox action.

## Model Policy

All real AI usage goes through hosted APIs, called by the backend with server-held keys:
- embeddings: Google gemini-embedding-001 at 384 dimensions via outputDimensionality, in backend/app/services/ingestion/embedding.py;
- generation: Groq openai/gpt-oss-120b.
- The browser only calls the KNEXUS backend, never a provider, and holds no keys.
- Local models (MiniLM sentence-transformers/all-MiniLM-L6-v2) and the fake generator are for tests, CI and local development only. They are not the demo or production path.
- No automatic retries or fallback between providers. No paid usage without Hassan's approval.

## Quick Start & Navigation

- [Project Status](docs/PROJECT_STATUS.md): Current delivery state, PRs, and Phase 1 next steps.
- [Setup and Git Workflow](CONTRIBUTING.md): Environments, 4-branch policy, and contributor setup.
- [Demo Runbook](docs/DEMO_RUNBOOK.md): Verified local dry run and unverified live demo commands.
- [Phase 1 Playbook](docs/PHASE_1_TEAM_GUIDE.md): Task sequence and acceptance criteria.
- [Team Responsibilities](docs/TEAM_RESPONSIBILITIES.md): Ownership and file boundaries.
- [Documentation Index](docs/INDEX.md): Requirements, architecture, database schema, and contracts.

## Architecture and Status

The backend foundation is merged into `main` (FastAPI, PostgreSQL/pgvector, ORM models, Alembic migrations, demo identity seeding, generation dispatch with atomic QuotaLedger, UTC normalization, and offline test suite).

The web frontend is merged in `frontend/app` (Vite + React 19 + TypeScript dashboard, documents, and chat views).

### Branch Policy
The repository maintains four persistent branches only:
- `main`
- `dev-hassan`
- `dev-naveed`
- `dev-zaid`

Members open PRs from their own branch; only Hassan merges into `main` and teammate branches. Temporary branches are deleted once merged.

Major Project Team 3, MJCET CSE (AI&ML), academic year 2026-2027.
