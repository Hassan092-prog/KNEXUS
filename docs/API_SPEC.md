# API inventory and scope

[Canonical Phase 1 contracts](PHASE_1_CONTRACT.md) own planned wire fields, limits and HTTP errors. [Reference examples](../contracts/phase1/examples/manifest.json) provide complete success, abstention, lifecycle and failure payloads; do not maintain a second set here.

## Implemented routes

With the default prefix:

| Method/path | Actual behavior |
|---|---|
| `GET /` | Welcome message and docs/health links |
| `GET /api/v1/health` | Database, vector and Ollama-tag diagnostics |
| `GET /docs`, `GET /redoc` | Generated API documentation |
| `GET /api/v1/openapi.json` | Schema for registered routes only |

No authentication is enforced. Generation and persistence modules exist but have no feature API yet. Root returns:

~~~json
{"message":"Welcome to the KNEXUS API","docs":"/docs","health":"/api/v1/health"}
~~~

Health fields are `status`, `app`, `environment`, `database`, `pgvector_extension` and `ollama`. HTTP status remains 200 on dependency failures. DB exceptions degrade the aggregate and expose raw exception text; missing vector/offline Ollama do not necessarily degrade it. The Ollama HTTP timeout is not an overall handler/DB deadline. Tags do not verify loaded-model generation. There are no dedicated readiness/liveness routes.

## Phase 1 routes to implement

The accepted contract defines upload, document list/detail/status and non-streaming query under `/api/v1`. These currently return 404 because they are not registered. Use canonical models and examples for exact request/response shapes, including explicit nulls and error codes.

A valid evidence abstention is HTTP 200; provider errors are failures. Upload 202 requires committed document/job records. Identity is server-owned demo context in this phase, not an unimplemented login token. No generic data/error wrapper is selected.

## Later contracts

Login/refresh/logout, document deletion, user/admin management, audit viewing and typed action proposal/approval/rejection are future work. Session revocation, cookies/storage, state transitions, action integrity/idempotency and safe HTTP responses need reviewed contracts before implementation.

Streaming is deferred: `stream=true` is rejected under Phase 1. There is no stream/history endpoint. Old illustrative routes and example payloads are removed rather than presented as approved interfaces.

See [security](SECURITY_MODEL.md) for required authorization/action boundaries and [status](PROJECT_STATUS.md) for implementation evidence. Use generated OpenAPI to discover what actually runs.
