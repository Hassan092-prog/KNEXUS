# Architecture

KNEXUS is a modular FastAPI application with PostgreSQL/pgvector persistence and an injected generation adapter. [Project status](PROJECT_STATUS.md) records what is published; [ownership](TEAM_RESPONSIBILITIES.md) assigns modules.

## Target versus implemented architecture

The target remains hosted generation and embeddings. PR #13 has merged the hosted generation transport; draft PR #15 supplies the unmerged evaluation harness. PR #16 merged the offline hosted embedding dispatch foundation, and PR #19 merged hosted input token validation and candidate splitting. API wiring and live acceptance remain pending, and historical database vectors remain local MiniLM. No provider account access, paid expenditure or hosted embedding dimension is established by these docs. No local model hosting, downloads or model reverse tunnels are required. [TRD](TRD.md) owns the pinned source-reuse policy and coordinated embedding migration. This documentation decision does not implement hosted behavior. The diagram is the hosted target; generation transport and embedding validation exist, while API configuration paths and corpus activation still need migration.

## Implemented components

- `main.py` registers root, health, CORS and generated API docs. Startup logs initialization; shutdown disposes the engine. It does not create tables, seed data or load models.
- Cached root-anchored Settings and the async database/session layer supply configuration and connectivity.
- Canonical schemas live in `contracts/phase1/models.py` and are re-exported by `app.schemas`.
- `build_demo_actor` provides fixed synthetic identity and effective roles; it authenticates nobody.
- `run_generation` awaits an injected concrete service and validates result/evidence membership.
- Generation implements explicit fake/Ollama providers, structured evidence, schema validation, typed errors and deadlines. The query endpoint integrates generation through the canonical `run_generation` boundary.
- Six ORM tables, an initial Alembic revision and explicit seed helper implement persistence. Ingestion processing and pgvector retrieval run in-process; background tasks are not durable. Recovery marks queued/processing jobs only after the operator confirms all old workers stopped.
- The frontend has no committed app, manifest or build.

## Phase 1 flow

The document/query API and ingestion/retrieval services exist as modular FastAPI services. This flow shows the revised hosted target; hosted embeddings and generation API wiring remain pending although generation transport is implemented.

~~~mermaid
flowchart LR
    UI["Zaid: upload/chat/status UI"] --> API["Hassan: document/query API"]
    API --> JOB["Persist document + ingestion job"]
    JOB --> ING["Parse, preserve source, chunk"]
    ING --> EMB["Hosted embedding API (offline dispatch & validation merged; activation pending)"]
    EMB --> DB["PostgreSQL + pgvector"]
    API --> RET["Authorize and retrieve"]
    RET --> QEMB["Hosted query embedding (same model/revision)"]
    RET --> DB
    RET --> BOUNDARY["H01 run_generation"]
    BOUNDARY --> GEN["Naveed: structured generator"]
    GEN --> HOSTED["Hosted generation API (transport exists; wiring pending)"]
    GEN --> API
    API --> UI
~~~

Upload must commit document/job before returning accepted status. Processing failures and interruptions update persisted state. Retrieval checks the server actor, tenant, effective roles, current parent permissions, completion/deletion and active model before supplying evidence. Empty/weak evidence abstains before inference.

Generation receives no authority over identity, database access or tools. It returns a canonical result or typed failure. The API builds public citations from retrieved metadata and returns a non-streaming response. See [Phase 1 contract](PHASE_1_CONTRACT.md); diagrams do not register endpoints.

## Persistence boundary

The [database document](DATABASE_SCHEMA.md) maps actual tables/constraints. Composite tenant foreign keys enforce consistent parent relationships but not request authorization. The HNSW index uses cosine distance over 384-dimensional vectors. Models and migrations are authoritative; no parallel SQL schema is maintained here.

## Deployment boundary

Compose currently starts PostgreSQL only. The API runs as an explicitly started local process. The target makes outbound backend calls to hosted embedding/generation APIs, without local inference or model tunnels. Hosted transport exists, but API Settings wiring and hosted embedding integration still require migration. The browser talks only to the backend and never holds provider keys.

No live server/tunnel is assumed from a historical check. Keep synthetic local data until authentication and authorization are verified. Compose's current DB port publication and health diagnostics need hardening before external exposure.

## Later architecture

Authentication/session management, append-only audit and one typed sandbox action form Phase 2. An action requires server policy, immutable reviewed envelope, authorized approval, expiry/replay/concurrency protection, execution-time recheck, idempotency and outcome verification. The LLM only proposes.

Hosted providers are the Phase 1 target; generation transport (PR #13), offline embedding dispatch foundation (PR #16), and input validation (PR #19) are merged, while final configuration, route integration, live token correspondence, and corpus activation remain pending. Broader platform modules, streaming, queues and connectors remain separate reviewed decisions. No Redis/Celery, ChromaDB or speculative duplicate application tree is part of the current baseline.
