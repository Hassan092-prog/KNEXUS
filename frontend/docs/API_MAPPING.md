# KNEXUS Backend API Mapping (Phase 1)

**Source of truth:** `backend/app/api/v1/endpoints/{documents.py,query.py,health.py}`, `backend/app/api/errors.py`, `backend/app/api/dependencies.py`, canonical schemas in `contracts/phase1/models.py`, fixtures in `contracts/phase1/examples/`.
**Verified:** by reading implementation code, not just `docs/API_SPEC.md`. Every endpoint below was traced to its handler in the merged `main` (commit `0b0dc00`, 5 Nov 2026).

Global transport notes:

- Base URL: `/api/v1` (settings-controlled; `.env.example` has `API_V1_PREFIX=/api/v1`).
- Every response carries `X-Request-ID` (UUID) middleware header.
- **No authentication** in Phase 1. Server fixes the actor `orgadmin` (effective `[orgadmin, manager, employee]`, `user_id 00000000-0000-4000-8000-000000000031`, `org_id …0032`). Client identity isn't just unused — sending it is rejected.
- Error envelope for all client-visible errors: `{ detail, code, request_id }` with codes `VALIDATION_ERROR | INVALID_FILE | FILE_TOO_LARGE | UNAUTHORIZED | FORBIDDEN | NOT_FOUND | CONFLICT | PROVIDER_UNAVAILABLE | INVALID_CITATIONS | INTERNAL_ERROR`.
- CORS whitelist: `http://localhost:3000|5173`, `127.0.0.1:3000|5173` — dev frontend must run on port 5173 (Vite default).

## Endpoints

| Feature | Endpoint | Method | Request | Response | Authentication | Error handling | Implementation status | Frontend usage |
|---|---|---|---|---|---|---|---|---|
| Root | `/` | GET | — | `{message, docs, health}` | none | generic | Implemented (`main.py:71`) | Not used by UI (links only) |
| Health | `/api/v1/health` | GET | — | `{status:"healthy"\|"degraded", app, environment, database:"connected"\|"unavailable", pgvector_extension, generation:"configured"\|"not_configured", embedding, ollama}` | none | Always 200 | Implemented (`health.py`) — **diagnostic only, not readiness**; still reports Ollama reachability (hosted model/keys may change this after Hassan's migration) | Optional sidebar "Connection" indicator; do not gate pages |
| Upload | `/api/v1/documents/upload` | POST | multipart/form-data: `file` (one, PDF/DOCX, ≤ 10 MiB); `allowed_roles` (repeated form fields, ≥1 of `employee\|manager\|orgadmin\|superadmin`, no dupes); `title` (optional, ≤512); `description` (optional, ≤2000). Must contain no `org_id`/`user_id`/etc. | 202 `{document_id:UUID, task_id:UUID, status:"queued", message:str}` | none | 413 `FILE_TOO_LARGE`; 400 `INVALID_FILE` (bad name/signature/no extractable text); 422 `VALIDATION_ERROR`; 500 `INTERNAL_ERROR` | Implemented (`documents.py:84`) | Uploader page (Phase 2, Z03). Frontend should prevent double-submit because backend creates a new document every attempt (no dedup) |
| List | `/api/v1/documents` | GET | query: `limit` (1–100, default 20), `offset` (≥0) | 200 `DocumentList`: `{data: DocumentSummary[], meta:{total,limit,offset}}` where `DocumentSummary` = `{id, title, source_type:"pdf"\|"docx", status:"queued"\|"processing"\|"complete"\|"failed", allowed_roles:Role[], chunk_count, created_at:ISO8601+tz}` | none | 422 | Implemented (`documents.py:205`) | Document library list (Phase 2, Z03) |
| Detail | `/api/v1/documents/{document_id}` | GET | path: `document_id` UUID | 200 `DocumentDetail` = `DocumentSummary` + `{description\|null, metadata:object}` | none | 404 `NOT_FOUND` (missing/cross-tenant/deleted), 403 `FORBIDDEN` (role), 422 | Implemented (`documents.py:241`) | Document details page (Phase 2, Z03) |
| Status | `/api/v1/documents/{document_id}/status` | GET | path: `document_id` UUID | 200 `DocumentStatus` `{document_id, status, chunks_processed, total_chunks\|null, progress_percent\|null (0–100; complete ⇒ 100), failure_code\|null, failure_message\|null}` | none (demo actor is orgadmin ⇒ passes uploader/orgadmin check) | 403, 404, 500 when job record missing | Implemented (`documents.py:255`) | Processing-status polling (Phase 2, Z03). stop conditions: `complete`/`failed` are terminal; honor `progress_percent` capped at 99 |
| Query | `/api/v1/query` | POST | JSON: `{question:str(1–4000), top_k:int(1–20, default5), stream:false (true ⇒ 422)}` | 200 `QueryResponse` `{answer:str\|null, citations:Citation[], abstained:bool, abstention_reason:str\|null, session_id:UUID, meta:{retrieval_time_ms, generation_time_ms, model}}` where `Citation` = `{id, chunk_id, document_id, document_title, chunk_index, page\|null, excerpt, similarity_score(-1..1)}`; answer contains inline `[N]` markers exactly matching citation ids; abstained ⇒ answer null, citations empty, reason non-null | none | 422; 503 `PROVIDER_UNAVAILABLE` (embedding down / provider down / config); 504 timeout; 502 `INVALID_CITATIONS`; errors keep canonical envelope | Implemented (`query.py`) | Assistant chat (Phase 2, Z04). One-shot, no history |

## Cleared-for-upload request example (matches backend expectations)

```bash
curl -X POST http://localhost:8000/api/v1/documents/upload \
  -F'file=@handbook.pdf' \
  -F'allowed_roles=employee' -F'allowed_roles=manager' \
  -F'title=Employee Handbook'
```

## Canonical response example (query)

```json
{
  "answer": "The synthetic handbook allows 21 days of annual leave per year [1].",
  "citations": [
    {"id": 1, "chunk_id": "…011", "document_id": "…001", "document_title": "Synthetic Employee Handbook",
     "chunk_index": 0, "page": 1, "excerpt": "Employees receive 21 days of annual leave per year.",
     "similarity_score": 0.9}
  ],
  "abstained": false,
  "abstention_reason": null,
  "session_id": "…021",
  "meta": {"retrieval_time_ms": 0.0, "generation_time_ms": 0.0, "model": "llama3.2:3b"}
}
```

## Documented-but-unimplemented / phase-2 endpoints (do not build UI against these)

- Login / refresh / logout / session-revocation — not present.
- Document deletion, retry upload, chunk/page source download, query history, streaming — not present.
- Admin/user/organization management, audit log — Phase 2 contract.
- Hosted generation/embedding acceptance — code exists, but final acceptance gate unresolved (Hassan/Naveed).

## Constraints and uncertainties (explicit)

1. `GET /documents/{id}/status` requires uploader or orgadmin — demo actor covers it, but any actor change would cause 403; UI must render this state.
2. Duplicate file uploads are accepted and become distinct documents — client must own double-submit prevention.
3. `POST /query` 200 with `abstained:true` is a *valid* response, not an error; do not treat as failure.
4. `meta.model` may be `"fake"`, `"not_configured"`, `"llama3.2:3b"`, or a hosted model id; do not hardcode.
5. PDF-only `page` field: present for PDFs, `null` for DOCX; UI must render nullable page safely.
6. Timing values in fixtures are illustrative; never derive analytics/statistics from the docs pages.
7. The backend rejects client identity in query params *and* headers (`x-user-id`, `x-org-id`, …). The axios instance must not set any such header.
