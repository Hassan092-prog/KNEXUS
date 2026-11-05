# Team responsibilities

This is the source of truth for identity, ownership and persistent branches. [Project status](PROJECT_STATUS.md) records completion; the [Phase 1 playbook](PHASE_1_TEAM_GUIDE.md) defines task acceptance.

| Member | Name / GitHub | Branch | Ownership |
|---|---|---|---|
| 1 | Hassan / Hassan092-prog | `dev-hassan` | Architecture, backend/API, models/migrations, ingestion/embeddings/retrieval, identity/authorization, approval/audit persistence, data/runtime, integration and release |
| 2 | Naveed / MrMax3757 | `dev-naveed` | Generation adapters, prompts/context, result/citation validation, model evaluation, typed tool definitions/handlers and research |
| 3 | Zaid / MohammedZaid1946 | `dev-zaid` | Entire frontend, framework/build setup, API types/client/mocks, upload/chat/citations, later login/admin/approval screens, accessibility, UI evidence and user guidance |

The target is these branches plus `main`. Transitional branches follow [contribution guidance](../CONTRIBUTING.md); they do not change ownership.

## Hosted migration and source reuse

All members inspect and selectively adapt the exact personal-project revision in [TRD](TRD.md), preserving licence notices and actual authorship. This instruction is not evidence that every reusable feature has been migrated.

- Hassan: backend/ingestion/retrieval/API adaptation, hosted embeddings, token policy, vector model/dimension compatibility, migrations and integration.
- Naveed: hosted generation/provider adaptation, structured results, deadlines/cancellation, safe errors and API-based quality evaluation.
- Zaid: reusable frontend components with redesigned UI and typed KNEXUS backend client. No provider secrets or direct model API calls in the browser.

No local inference, downloads or Ollama tunnels. Coordinate provider/model/settings and embedding dimensions before shared changes. Use mocked HTTP pending credential and spending authorization.

## File boundaries

| Owner | Primary paths |
|---|---|
| Hassan | `backend/app/api/`, `core/`, `models/`, `db/`, `schemas/`, `backend/alembic/`, ingestion/retrieval, persistence/API/security tests, runtime/dependencies and corpus provenance |
| Naveed | `backend/app/services/generation/`, generation tests, future typed tool handlers, prompt/evaluation cases and research |
| Zaid | Entire `frontend/`, its dependencies/tests, UI screenshots/manual and presentation visuals |

Hassan coordinates `contracts/phase1/` changes with both consumers reviewing impact. Ownership does not authorize silently changing an interface.

Naveed supplies typed tool definitions and sandbox handlers; Hassan owns authorization, approval, expiry, integrity, duplicate-execution protection and audit around them. The model never grants permission or approves an action.

Hassan maintains corpus provenance, Naveed answer labels/rubrics and Zaid frontend mocks. Each member explains actual contributions and reviews another member's work. Use the [project plan](KNEXUS_Project_Plan.md) for later phases and [setup/workflow](../CONTRIBUTING.md) for Git commands.
