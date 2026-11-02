# Architecture

KNEXUS is a modular FastAPI application with PostgreSQL/pgvector persistence and an injected generation adapter. [Project status](PROJECT_STATUS.md) records what is published; [ownership](TEAM_RESPONSIBILITIES.md) assigns modules.

## Implemented components

- `main.py` registers root, health, CORS and generated API docs. Startup logs initialization; shutdown disposes the engine. It does not create tables, seed data or load models.
- Cached root-anchored Settings and the async database/session layer supply configuration and connectivity.
- Canonical schemas live in `contracts/phase1/models.py` and are re-exported by `app.schemas`.
- `build_demo_actor` provides fixed synthetic identity and effective roles; it authenticates nobody.
- `run_generation` awaits an injected concrete service and validates result/evidence membership.
- Generation implements explicit fake/Ollama providers, structured evidence, schema validation, typed errors and deadlines. Main has no feature route; the dev-hassan review implementation calls it through the canonical run_generation boundary.
- Six ORM tables, an initial Alembic revision and explicit seed helper implement published storage structure. The dev-hassan review implementation adds processing and pgvector retrieval; the background task is not durable. Recovery marks queued/processing jobs only after the operator confirms all old workers stopped.
- The frontend has no committed app, manifest or build.

## Phase 1 flow

The document/query API and ingestion/retrieval services below are implemented on dev-hassan based on main. They are published for review on dev-hassan but have not been merged into main.

~~~mermaid
flowchart LR
    UI["Zaid: upload/chat/status UI"] --> API["Hassan: document/query API"]
    API --> JOB["Persist document + ingestion job"]
    JOB --> ING["Parse, tokenize, embed"]
    ING --> DB["PostgreSQL + pgvector"]
    API --> RET["Authorize and retrieve"]
    RET --> DB
    RET --> BOUNDARY["H01 run_generation"]
    BOUNDARY --> GEN["Naveed: structured generator"]
    GEN --> OLL["Ollama on laptop"]
    GEN --> API
    API --> UI
~~~

Upload must commit document/job before returning accepted status. Processing failures and interruptions update persisted state. Retrieval checks the server actor, tenant, effective roles, current parent permissions, completion/deletion and active model before supplying evidence. Empty/weak evidence abstains before inference.

Generation receives no authority over identity, database access or tools. It returns a canonical result or typed failure. The API builds public citations from retrieved metadata and returns a non-streaming response. See [Phase 1 contract](PHASE_1_CONTRACT.md); diagrams do not register endpoints.

## Persistence boundary

The [database document](DATABASE_SCHEMA.md) maps actual tables/constraints. Composite tenant foreign keys enforce consistent parent relationships but not request authorization. The HNSW index uses cosine distance over 384-dimensional vectors. Models and migrations are authoritative; no parallel SQL schema is maintained here.

## Deployment boundary

Compose currently starts PostgreSQL only. The API runs as an explicitly started local process. Naveed's laptop serves Ollama over loopback, optionally forwarded to the server through the authorized reverse tunnel in [CONTRIBUTING](../CONTRIBUTING.md). The browser talks only to the backend.

No live server/tunnel is assumed from a historical check. Keep synthetic local data until authentication and authorization are verified. Compose's current DB port publication and health diagnostics need hardening before external exposure.

## Later architecture

Authentication/session management, append-only audit and one typed sandbox action form Phase 2. An action requires server policy, immutable reviewed envelope, authorized approval, expiry/replay/concurrency protection, execution-time recheck, idempotency and outcome verification. The LLM only proposes.

Broader platform modules, hosted providers, streaming, queues and connectors are separate reviewed decisions after the core path is complete. No Redis/Celery, ChromaDB or speculative duplicate application tree is part of the current baseline.
