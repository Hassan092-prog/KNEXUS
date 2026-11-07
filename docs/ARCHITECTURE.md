# Architecture

KNEXUS is a modular FastAPI application with PostgreSQL/pgvector persistence and an injected generation adapter. [Project status](PROJECT_STATUS.md) records what is published; [ownership](TEAM_RESPONSIBILITIES.md) assigns modules.

## Target versus implemented architecture

### Model Policy
- All real AI usage goes through hosted APIs, called by the backend with server-held keys:
  - embeddings: Google gemini-embedding-001 at 384 dimensions via outputDimensionality, in backend/app/services/ingestion/embedding.py;
  - generation: Groq openai/gpt-oss-120b.
- The browser only calls the KNEXUS backend, never a provider, and holds no keys.
- Local models (MiniLM sentence-transformers/all-MiniLM-L6-v2) and the fake generator are for tests, CI and local development only. They are not the demo or production path.
- No automatic retries or fallback between providers. No paid usage without Hassan's approval.

PR #13 merged hosted generation transport; PR #15 merged the generation evaluation harness; PR #16 merged offline dispatch protection and quota ledger; PR #19 merged hosted input token validation; PR #21 wired generation into backend dependencies; PR #23 merged the frontend dashboard; PR #26 added CI tokenizer caching.

## Implemented components

- `main.py` registers root, health, CORS and generated API docs. Startup logs initialization; shutdown disposes the engine. It does not create tables, seed data or load models.
- Cached root-anchored Settings and the async database/session layer supply configuration and connectivity.
- Canonical schemas live in `contracts/phase1/models.py` and are re-exported by `app.schemas`.
- `build_demo_actor` provides fixed synthetic identity and effective roles; it authenticates nobody.
- `run_generation` awaits an injected concrete service and validates result/evidence membership.
- Generation implements explicit fake/Ollama providers, structured evidence, schema validation, typed errors and deadlines. The query endpoint integrates generation through the canonical `run_generation` boundary.
- Six ORM tables, an initial Alembic revision and explicit seed helper implement persistence. Ingestion processing and pgvector retrieval run in-process; background tasks are not durable. Recovery marks queued/processing jobs only after the operator confirms all old workers stopped.
- The frontend application (frontend/app) is merged on origin/main (PR #23) with overview, documents, and chat views.

## Phase 1 flow

The document/query API and ingestion/retrieval services exist as modular FastAPI services. This flow shows the revised hosted target; hosted embeddings and generation API wiring remain pending although generation transport is implemented.

~~~mermaid
flowchart LR
    UI["Zaid: upload/chat/status UI"] --> API["Hassan: document/query API"]
    API --> JOB["Persist document + ingestion job"]
    JOB --> ING["Parse, preserve source, chunk"]
    ING --> EMB["Local MiniLM embedder (sentence-transformers, 384-d)"]
    EMB --> DB["PostgreSQL + pgvector"]
    API --> RET["Authorize and retrieve"]
    RET --> QEMB["Local query embedding (MiniLM, 384-d)"]
    RET --> DB
    RET --> BOUNDARY["H01 run_generation"]
    BOUNDARY --> GEN["Naveed: structured generator"]
    GEN --> HOSTED["Hosted Groq generation (openai/gpt-oss-120b)"]
    GEN --> API
    API --> UI
~~~

Upload must commit document/job before returning accepted status. Processing failures and interruptions update persisted state. Retrieval checks the server actor, tenant, effective roles, current parent permissions, completion/deletion and active model before supplying evidence. Empty/weak evidence abstains before inference.

Generation receives no authority over identity, database access or tools. It returns a canonical result or typed failure. The API builds public citations from retrieved metadata and returns a non-streaming response. See [Phase 1 contract](PHASE_1_CONTRACT.md); diagrams do not register endpoints.

## Persistence boundary

The [database document](DATABASE_SCHEMA.md) maps actual tables/constraints. Composite tenant foreign keys enforce consistent parent relationships but not request authorization. The HNSW index uses cosine distance over 384-dimensional vectors. Models and migrations are authoritative; no parallel SQL schema is maintained here.

## Deployment boundary

Compose currently starts PostgreSQL only. The API runs as an explicitly started local process. The Phase 1 demo stack makes outbound backend calls to the Groq generation API, using local MiniLM for embeddings (Google embedder present in codebase but off for demo). No local LLM inference or model tunnels are required. The browser talks only to the backend and never holds provider keys.

No live server/tunnel is assumed from a historical check. Keep synthetic local data until authentication and authorization are verified. Compose's current DB port publication and health diagnostics need hardening before external exposure.

## Later architecture

Authentication/session management, append-only audit and one typed sandbox action form Phase 2. An action requires server policy, immutable reviewed envelope, authorized approval, expiry/replay/concurrency protection, execution-time recheck, idempotency and outcome verification. The LLM only proposes.

Hosted providers are the Phase 1 target; generation transport (PR #13), offline embedding dispatch foundation (PR #16), and input validation (PR #19) are merged, while final configuration, route integration, live token correspondence, and corpus activation remain pending. Broader platform modules, streaming, queues and connectors remain separate reviewed decisions. No Redis/Celery, ChromaDB or speculative duplicate application tree is part of the current baseline.
