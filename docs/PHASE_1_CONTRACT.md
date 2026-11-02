# Phase 1 implementation baseline

**Version 0.1 - initial baseline merged in [PR #1](https://github.com/Hassan092-prog/KNEXUS/pull/1).** Hassan owns integration/schema contracts, Naveed owns generation and Zaid owns the frontend. Use these field shapes for implementation and review later contract changes together before updating consumers. The HTTP definitions remain targets. The generation boundary and initial persistence schema are implemented in the reviewed shared baseline on main; see [current status](PROJECT_STATUS.md).

For Phase 1 details below, this baseline narrows the broader [API proposal](API_SPEC.md) and [database implementation](DATABASE_SCHEMA.md). Future streaming/actions/admin contracts remain design proposals. Scope changes need a reviewed update to this baseline, [reference models](../contracts/phase1/models.py), [schema export](../contracts/phase1/schema.json) and examples together.

## First vertical slice

One synthetic PDF/DOCX -> queued upload -> visible processing state -> parsed/chunked/embedded document -> authorized retrieval -> non-streaming answer with real retrieved IDs or abstention -> frontend citation/status display.

Start with local synthetic fixtures and a server-owned demo actor. Do not infer identity from client `org_id`, `user_id` or `role`. Query/upload metadata rejects additional identity fields. A fixed demo actor is not authentication; no shared-sensitive-data or external deployment is accepted before the planned authentication/authorization work exists.

## HTTP boundary

All paths use the existing `/api/v1` prefix.

| Method/path | Phase 1 contract |
|---|---|
| POST `/documents/upload` | One `file` part, PDF or DOCX, at most 10 MiB; optional title/description; `allowed_roles` is a repeated multipart form field, not a JSON-encoded string. See UploadMetadata. Return UploadAccepted / 202 after input validation and persisted job creation. |
| GET `/documents` | DocumentList; limit defaults to 20 and is 1-100; offset >= 0. Filter by the active actor's organization/permissions before pagination. |
| GET `/documents/{document_id}` | DocumentDetail for an accessible document; 404 for missing/cross-tenant IDs, 403 for same-tenant role denial. |
| GET `/documents/{document_id}/status` | DocumentStatus; require an eligible uploader/admin context and ownership. Queued totals/progress may be null. Complete requires known totals, all chunks processed and progress 100. Failed requires safe failure_code/failure_message; other states keep those fields null. |
| POST `/query` | QueryRequest: trimmed question 1-4000 characters; top_k defaults to 5, range 1-20; stream must be false. Return QueryResponse / 200 for an answer or evidence-based abstention. |

`source_type` is pdf/docx for this slice; additional formats in broader schema drafts are deferred. Repeated `allowed_roles` values must be unique and belong to employee/manager/orgadmin/superadmin. File extension, content signature, size and parser limits are backend checks; Pydantic metadata validation alone cannot enforce them.

Use UTC timezone-aware timestamps, UUID identifiers and the stable document/chunk IDs used by storage. Treat all returned content as text in the frontend. Preserve the existing `/`, health, docs and OpenAPI routes; the current health behavior is not the new API contract's readiness policy.

## Stable query output

QueryResponse always contains answer, citations, abstained, abstention_reason, session_id and meta. The meta fields are retrieval_time_ms, generation_time_ms and model. Timing is measured by implementation, not supplied by the browser/model.

- Answered: nonempty answer, at least one citation, abstained=false, abstention_reason=null.
- Abstained: answer=null, citations=[], abstained=true, nonempty reason. A successful abstention is HTTP 200, not a provider error.
- Inline markers such as [1] must match the returned citation-ID set. Citation IDs are positive integers scoped to one query; chunk_id/document_id are stable storage UUIDs.
- `session_id` is a fresh response/query correlation UUID for Phase 1. It does not promise stored conversation history, a stream endpoint or a resumable session.
- `stream=true` is rejected as 422 / VALIDATION_ERROR until a separately reviewed streaming contract exists.

See [answered example](../contracts/phase1/examples/query-answer.json) and [abstention example](../contracts/phase1/examples/query-abstention.json). These supersede the optional/missing abstention meta fields in older illustrative API examples for this slice.

## Retrieval/generation boundary

Hassan's retrieval service resolves the active actor, filters tenant/permissions, excludes deleted/incomplete documents and returns unique ranked EvidenceChunk objects. Use server-expanded effective roles: employee; manager+employee; orgadmin+manager+employee; superadmin+orgadmin+manager+employee. Even a superadmin is tenant-scoped by default.

Evidence fields are citation_id, chunk_id, document_id, document_title, chunk_index, optional page, content and similarity_score. Similarity ranges from -1 to 1; chunk_index is zero-based and page is one-based when known. Keep original source IDs/provenance in storage metadata.

Naveed's generator receives GenerationRequest with the question and 1-20 already-authorized chunks. Empty/weak evidence produces backend abstention before any model call. The initial 0.35 similarity cutoff is a development proposal to calibrate, not a proven quality threshold.

The generator returns GenerationResult with answer, cited_ids, abstained and abstention_reason. It cannot invent document metadata, choose a tenant, grant permissions or execute tools. `validate_generation_result` rejects IDs outside the supplied evidence. The backend assembles public Citation records from its own retrieved objects, not model-provided filenames/excerpts. Inline marker consistency is checked too; actual claim support still requires evaluation.

The context builder must respect the chosen LLM's real token/context budget; the per-field limits in reference types do not replace token counting. Use MiniLM 384-dimensional embeddings, tokenizer-aware chunks starting at 240 tokens / overlap 32, and cosine retrieval. Larger embeddings require a schema/index migration and full re-embedding.

## Runtime imports and accepted generator handoff

The canonical Pydantic definitions remain in `contracts/phase1/models.py`; do not create parallel application model classes. Backend code imports the accepted request/response types through `app.schemas`. That package re-exports the canonical classes and validators.

The team accepted the async call boundary `app.core.generation.GenerationService`:

```python
async def generate(self, request: GenerationRequest) -> GenerationResult: ...
```

The backend calls `run_generation(service, request)` to await an injected implementation and validate that cited IDs belong to the already-authorized evidence. A generator must not read the database, choose a tenant, grant permissions or execute tools. The reviewed shared baseline on main includes a compatible provider; HTTP integration and live model quality still require verification.

The local synthetic actor helper is `app.core.demo_identity.build_demo_actor()`. It returns the fixed actor in `contracts/phase1/examples/actor-context.json`, using the documented orgadmin-to-manager-to-employee expansion. It is demo identity only and does not authenticate requests. Public query/upload metadata continues to reject identity fields; upload `allowed_roles` remains document metadata.

## Initial persistence contract

Hassan owns the migration implementation. Use organizations/users for a server-owned demo actor, documents, document_chunks, embeddings, and an ingestion-job record. The reviewed ORM and initial Alembic revision implement the storage foundation; services must preserve these invariants:

- Each tenant-owned child references a parent in the same organization; enforce composite ownership constraints and service checks.
- Document lifecycle is queued -> processing -> complete or failed. Only complete, nondeleted, currently authorized documents can be retrieved.
- Unique chunk positions per document; stable chunk IDs; one active 384-dimensional baseline embedding per chunk/model version.
- Persist job ID (`task_id`), organization/document ownership, state, chunk counters, safe failure code and timestamps in `ingestion_jobs`. Status lookup is by document and its latest attempt. A persisted row does not make FastAPI background tasks durable; mark interrupted attempts failed and keep restart/retry behavior explicit.
- Upload returns 202 only after a job/document record is committed. Failed/partial indexing cannot be presented as complete. Keep raw parser/DB/provider diagnostics out of public error fields.
- Migrations are reviewed revisions, not SQL pasted manually into the shared development database. Test migration round trips only on a disposable database.

The initial revision includes ingestion_jobs and tenant constraints and passed disposable verification. It has not been applied to the shared database; service orchestration remains pending. Refresh sessions, conversation history, controlled-action persistence and durable queues are outside this first slice.

## Error behavior

| HTTP | ErrorResponse code | Use |
|---|---|---|
| 400 | INVALID_FILE | Invalid signature/type or unreadable content detected before accepting the upload |
| 413 | FILE_TOO_LARGE | File exceeds 10 MiB |
| 422 | VALIDATION_ERROR | Metadata/query/limit validation, unsupported stream=true |
| 403 / 404 | FORBIDDEN / NOT_FOUND | Role denial / absent or cross-tenant resource |
| 503 | PROVIDER_UNAVAILABLE | Ollama unavailable/overloaded |
| 504 | PROVIDER_UNAVAILABLE | Bounded generation timeout |
| 502 | INVALID_CITATIONS | Provider output fails source-ID/answer contract after validation |
| 500 | INTERNAL_ERROR | Unexpected error with safe public detail |

Parsing/indexing failures discovered after 202 update the persisted job/document to failed and appear through the status resource; they cannot retroactively change the accepted upload response. Use safe status failure fields, not raw exceptions.

The public error shape is detail/code/request_id, with a server-owned correlation UUID. The canonical Phase 1 error envelope is implemented in Hassan's isolated local review implementation; published main still has only root/health routes. FastAPI defaults are mapped to safe contract-shaped errors in that implementation. Provider failure is an error state, not a fabricated answer or an evidence abstention.

## Current handoffs

- Hassan: H03-H06 code exists as an isolated local review implementation based on main; review before publishing.
- Naveed: preserve the reviewed provider boundary and complete context policy, live evaluation and the backend handoff.
- Zaid: initialize frontend and use query/document/status/error fixtures as typed mocks, then integrate only the accepted APIs.

Run [the contract check](../contracts/phase1/README.md) before changing shared fields. One member implements a contract change; the other two review their consumer impact. Do not silently change fields in parallel branches.
