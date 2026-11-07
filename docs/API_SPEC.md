# API inventory and actual behavior

[Canonical Phase 1 contracts](PHASE_1_CONTRACT.md) own wire fields, limits and error codes. [Reference examples](../contracts/phase1/examples/manifest.json) provide complete success, abstention, lifecycle and failure payloads; do not create a second schema.

The routes below are implemented in the Phase 1 backend application. See [Project status](PROJECT_STATUS.md) for pull request history and dated verification evidence.

## Hosted transition

For the Phase 1 demo, the architecture uses local MiniLM embeddings (sentence-transformers/all-MiniLM-L6-v2, 384 dimensions) paired with Groq hosted generation (openai/gpt-oss-120b). The Google hosted embedder is implemented and verified offline in the codebase but kept disabled (EMBEDDING_PROVIDER="local") for the demo to preserve existing 384-d vectors and zero-cost operation. PR #13 merged hosted transport; PR #15 supplies the generation harness; PR #16 merged offline dispatch protection and quota ledger; PR #19 merged hosted input validation; PR #21 wires generation into backend dependencies. No local LLM hosting, downloads or model reverse tunnels are required. Public routes and canonical fields remain unchanged.

## Registered routes

| Method/path | Actual behavior |
|---|---|
| GET / | Welcome message and docs/health links |
| GET /api/v1/health | DB, pgvector, generation, and embedding status summary; always HTTP 200, not readiness |
| POST /api/v1/documents/upload | One PDF/DOCX up to 10 MiB; repeated allowed_roles form fields; validates signature and extractable text, stores under generated private key, commits document and job, then returns 202 |
| GET /api/v1/documents | Lists same-tenant, nondeleted documents visible to the server-owned demo actor; filters before count and pagination |
| GET /api/v1/documents/{document_id} | Accessible document details; 404 for missing/cross-tenant/deleted, 403 for same-tenant role denial |
| GET /api/v1/documents/{document_id}/status | Latest persisted ingestion attempt; uploader or orgadmin context required |
| POST /api/v1/query | Non-streaming, role/tenant/status-filtered retrieval followed by injected generation; returns backend-built citations or a valid evidence abstention |
| GET /docs, GET /redoc | Generated API docs |
| GET /api/v1/openapi.json | Schema for registered routes |

Use the canonical [upload](../contracts/phase1/examples/upload-metadata.json), [query](../contracts/phase1/examples/query-request.json), [answer](../contracts/phase1/examples/query-answer.json), [abstention](../contracts/phase1/examples/query-abstention.json) and [error](../contracts/phase1/examples/validation-error.json) fixtures.

## Implemented boundaries and limits

- There is no login. API requests use the fixed server-owned synthetic orgadmin actor. Identity sent in request body, form fields, identity headers or query parameters is rejected; it never selects an actor or tenant.
- Upload accepts a single PDF or DOCX, at most 10 MiB. The PDF parser uses installed pdfplumber; DOCX uses python-docx. Scanned PDFs without extractable text are rejected; OCR is not implemented.
- Files use a random UUID storage key under the ignored private local storage directory. Original basename and parser page/paragraph/table source metadata are persisted.
- Chunking preserves original source spans and uses the configured MiniLM tokenizer. The effective ceiling is the minimum of the configured 240-token limit, tokenizer limit and loaded encoder max_seq_length, including special tokens; default overlap is 32. Loading and chunking stay off the event loop. Tokenizer loading is local-files-only.
- Ingestion uses a FastAPI background task, not a durable queue. The job and document are committed before 202; polling reports persisted states. Internal retry and abandoned-job recovery exist, but no public retry route is contracted. Run recovery only after confirming the old process and all ingestion workers are stopped; it marks queued and processing attempts failed for explicit retry.
- Embeddings use all-MiniLM-L6-v2 at 384 dimensions. The historical implementation loads local-files-only and caches per process; an injected deterministic fake is for tests only and has no semantic quality.
- Retrieval pushes tenant, role overlap, current parent-document completion/deletion, active-vector and model-revision filters into the pgvector SQL query before top-k. The 0.35 similarity cutoff is uncalibrated.
- Re-ingest documents after switching EMBEDDING_PROVIDER: retrieval strictly isolates embedding spaces by filtering on the active model name and revision. Chunks embedded under another model/provider are never scored or ranked, and untagged legacy chunks are excluded fail-closed.
- No authorized evidence or only weak evidence returns an HTTP 200 abstention before calling the generation provider. Provider unavailable/timeout and malformed citations remain errors.
- CORS remains limited to configured local origins. Error bodies use the canonical detail/code/request_id envelope and do not include exception text.

Health returns HTTP 200 even when a dependency is unavailable. It now reports generic availability labels rather than raw database exceptions. Ollama tags show reachability, not successful generation. There is no dedicated readiness route.

## Verification limits

Offline fake/mock route and service tests (including OpenAPI and CORS checks) run without database access. Reusable disposable database integration tests cover migration round trips, upload failure rollback, and role-filtered retrieval against an isolated loopback PostgreSQL/pgvector container. Historical MiniLM inference has separate evidence, but hosted embedding/generation evaluation and browser integration remain open. The shared database remains unmigrated; the demo seed is explicit.

## Later contracts

Login/refresh/logout, document deletion, user/admin management, audit viewing and typed action proposal/approval/rejection are future work. Session revocation, action integrity/idempotency and safe HTTP responses need reviewed contracts before implementation.

Streaming is deferred: stream=true returns 422 under Phase 1. There is no stream/history endpoint. See [security](SECURITY_MODEL.md) and [status](PROJECT_STATUS.md).
