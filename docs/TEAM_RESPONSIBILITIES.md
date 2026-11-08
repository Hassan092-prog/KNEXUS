# Team responsibilities

This is the source of truth for identity, ownership and persistent branches. [Project status](PROJECT_STATUS.md) records completion; the [Phase 1 playbook](PHASE_1_TEAM_GUIDE.md) defines task acceptance.

| Member | Name / GitHub | Branch | Ownership |
|---|---|---|---|
| 1 | Hassan / Hassan092-prog | `dev-hassan` | Architecture, backend/API, models/migrations, ingestion/embeddings/retrieval, identity/authorization, approval/audit persistence, data/runtime, integration and release |
| 2 | Naveed / MrMax3757 | `dev-naveed` | Generation adapters, prompts/context, result/citation validation, model evaluation, typed tool definitions/handlers and research |
| 3 | Zaid / MohammedZaid1946 | `dev-zaid` | Entire frontend (`frontend/app`), framework/build setup, API types/client/mocks, upload/chat/citations, later login/admin/approval screens, accessibility, UI evidence and user guidance |

## Branch policy
- The only remote branches are `main`, `dev-hassan`, `dev-naveed`, and `dev-zaid`.
- Members open PRs from their own branch; only Hassan merges into `main` and teammate branches.
- Temporary branches must be deleted once merged; the 4 branches above are permanent.

## Model policy
- All real AI usage goes through hosted APIs, called by the backend with server-held keys:
  - embeddings: Google gemini-embedding-001 at 384 dimensions via outputDimensionality, in backend/app/services/ingestion/embedding.py;
  - generation: Groq openai/gpt-oss-120b.
- The browser only calls the KNEXUS backend, never a provider, and holds no keys.
- Local models (MiniLM sentence-transformers/all-MiniLM-L6-v2) and the fake generator are for tests, CI and local development only. They are not the demo or production path.
- No automatic retries or fallback between providers. No paid usage without Hassan's approval.

No local inference for the product; local models and fake providers are allowed for testing, CI and offline verification only.

## File boundaries

| Owner | Primary paths |
|---|---|
| Hassan | `backend/app/api/`, `core/`, `models/`, `db/`, `schemas/`, `backend/alembic/`, ingestion/retrieval, persistence/API/security tests, runtime/dependencies and corpus provenance |
| Naveed | `backend/app/services/generation/`, generation tests, future typed tool handlers, prompt/evaluation cases and research |
| Zaid | Entire `frontend/` (`frontend/app`), its dependencies/tests, UI screenshots/manual and presentation visuals |

Hassan coordinates `contracts/phase1/` changes with both consumers reviewing impact. Ownership does not authorize silently changing an interface.

Naveed supplies typed tool definitions and sandbox handlers; Hassan owns authorization, approval, expiry, integrity, duplicate-execution protection and audit around them. The model never grants permission or approves an action.

Hassan maintains corpus provenance, Naveed answer labels/rubrics and Zaid frontend mocks. Each member explains actual contributions and reviews another member's work. Use the [project plan](KNEXUS_Project_Plan.md) for later phases and [setup/workflow](../CONTRIBUTING.md) for Git commands.
