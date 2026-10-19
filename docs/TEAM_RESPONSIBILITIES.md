# Team responsibilities and delivery ownership

**Effective: 19 October 2026.** This is the source of truth for KNEXUS member identity, task ownership and branch names. The project plan and phase guides must follow it.

| Member | Name | Branch | Primary responsibility |
| --- | --- | --- | --- |
| 1 | Hassan | `dev-hassan` | Architecture, backend/API, database/migrations, ingestion/retrieval, security/governance, data/runtime, integration and release |
| 2 | Naveed | `dev-naveed` | LLM adapter, prompts/context, citation validation, tool definitions/handlers, answer-quality evaluation and research |
| 3 | Zaid | `dev-zaid` | Entire frontend: React/TypeScript/Vite, design system, upload/chat/citation screens, login/admin/approval UI, accessibility and UI documentation |

## Work packages

Each package has one accountable owner. Coordinate shared interfaces before implementation and have a teammate review completed changes.

| Phase | Owner | Included work |
| --- | --- | --- |
| 0 | Hassan | Requirements/API/service contracts; schema/runtime baseline and delivery coordination |
| 0 | Naveed | Literature/model/prompt baseline and quality rubric |
| 0 | Zaid | Frontend flow map, wireframes and UI/API-state inventory |
| 1 | Hassan | Models/migrations/vector storage; parsing/chunking/embeddings; filtered retrieval; API/import fixtures/integration |
| 1 | Naveed | Ollama adapter; versioned prompt and context builder; citation/abstention validation and answer cases |
| 1 | Zaid | Frontend foundation/design system; upload/status UI; chat/citation/abstention UI; UI states and component checks |
| 2 | Hassan | Authentication/tenant authorization; approval transactions/idempotency/audit persistence; security/integration verification |
| 2 | Naveed | Typed tool registry/sandbox handlers; action-envelope integrity helpers and tool cases; prompt/model regression cases |
| 2 | Zaid | Login/navigation/session UI; approval/admin screens; document/citation/permission UI states |
| 3 | Hassan | CI/integration automation; deployment/configuration; retrieval/load measurement; final-report compilation/API/runtime documentation |
| 3 | Naveed | Controlled model/prompt experiments; research/methodology/results sections; evidence-grounded demo narrative |
| 3 | Zaid | Frontend integration/accessibility/usability; UI manual/screenshots/report contribution; presentation visuals |
| 4 | Hassan | Full-pipeline regression/release/archive; final report integration and defense coordination |
| 4 | Naveed | Research/metrics/demo rehearsal; limitations and results verification |
| 4 | Zaid | Frontend polish/demo presentation; UI screenshots and submission/hardcopy assembly |

## File and interface ownership

These paths include proposed modules that do not exist yet; ownership does not imply implementation.

| Owner | Primary paths and contracts |
|---|---|
| Hassan | `backend/app/api/`, `backend/app/core/`, `backend/app/models/`, `backend/app/schemas/`, `backend/alembic/`, ingestion/retrieval services, approval/audit persistence, database and API/integration tests, `docker/`, `docker-compose.yml`, backend dependencies, dataset import/fixtures, CI and deployment docs |
| Naveed | `backend/app/services/generation/`, tool registry/typed sandbox handlers in `backend/app/services/tools/`, versioned prompts, answer-quality cases/rubrics and literature/research sections |
| Zaid | Entire `frontend/` tree, UI components/pages/hooks/API client/types/mock payloads, frontend dependencies/build configuration, UI/component tests, accessibility/user manual and presentation visuals |

Naveed owns tool definitions and safe handler behavior; Hassan owns the authorization, approval state machine, concurrency/idempotency, and audit boundary around execution. Coordinate those files before adding a shared tools directory. Hassan owns imported corpus provenance/security fixtures; Naveed supplies answer labels and Zaid owns frontend-only API mocks. Zaid consumes agreed API contracts; a UI permission indicator cannot enforce backend access.

Each member commits/pushes their own persistent branch. Integrate with one PR at a time per branch using merge commits; synchronize with `origin/main` before starting the next task. A file owner implements the change and another member reviews it. Coordinate shared contracts before editing another owner's paths.

## Coordination and review

At the weekly check-in, review task status, blockers, dependencies and completion evidence. Record interface decisions and update this document and affected phase guides when ownership changes. Each member explains their implementation and reviews a teammate's changes before integration.

The repository is still a backend scaffold. These responsibilities describe planned delivery and do not imply that application features, frontend screens, migrations or evaluation results already exist.
