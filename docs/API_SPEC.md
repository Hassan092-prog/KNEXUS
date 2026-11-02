# API inventory and actual behavior

[Canonical Phase 1 contracts](PHASE_1_CONTRACT.md) own wire fields, limits and error codes. [Reference examples](../contracts/phase1/examples/manifest.json) provide complete success, abstention, lifecycle and failure payloads; do not create a second schema.

The routes below are implemented in Hassan's isolated local review implementation at /tmp/knexus-hassan-phase1-next, based on main 84f0eb284f0b59adf96d053f72a36129c832cb13. They have not been published or merged into main. Main remains at H01/H02 until this review implementation is approved and published.

## Registered routes in the local review implementation

| Method/path | Actual behavior |
|---|---|
| GET / | Welcome message and docs/health links |
| GET /api/v1/health | DB, pgvector and Ollama reachability summary; always HTTP 200, not readiness |
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
- Embeddings use all-MiniLM-L6-v2 at 384 dimensions. Production loading is local-files-only and cached per process; an injected deterministic fake is for tests only and has no semantic quality.
- Retrieval pushes tenant, role overlap, current parent-document completion/deletion, active-vector and model-revision filters into the pgvector SQL query before top-k. The 0.35 similarity cutoff is uncalibrated.
- No authorized evidence or only weak evidence returns an HTTP 200 abstention before calling the generation provider. Provider unavailable/timeout and malformed citations remain errors.
- CORS remains limited to configured local origins. Error bodies use the canonical detail/code/request_id envelope and do not include exception text.

Health returns HTTP 200 even when a dependency is unavailable. It now reports generic availability labels rather than raw database exceptions. Ollama tags show reachability, not successful generation. There is no dedicated readiness route.

## Verification limits

Hassan's local review implementation has offline fake/mock route and service tests (including OpenAPI and CORS checks), and covered route/database scenarios have passed against disposable PostgreSQL/pgvector. Real embedding inference on model weights, live Ollama generation service evaluation, and Zaid's browser integration remain pending. The shared database remains unmigrated; the demo seed is explicit.

## Later contracts

Login/refresh/logout, document deletion, user/admin management, audit viewing and typed action proposal/approval/rejection are future work. Session revocation, action integrity/idempotency and safe HTTP responses need reviewed contracts before implementation.

Streaming is deferred: stream=true returns 422 under Phase 1. There is no stream/history endpoint. See [security](SECURITY_MODEL.md) and [status](PROJECT_STATUS.md).
