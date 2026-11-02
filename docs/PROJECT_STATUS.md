# Current status and next actions

**Checked: 2 November 2026.** This page records published work separately from local drafts. Requirements remain in the contract and playbook.

## Published baseline

- **PR #5** (https://github.com/Hassan092-prog/KNEXUS/pull/5) merged the reviewed H01, generation and persistence baseline into main at `5104a19e61f35d4a10e38000737e68513069f2a5`.
- **PR #7** (https://github.com/Hassan092-prog/KNEXUS/pull/7) merged the reviewed H03-H06 ingestion, retrieval, and API endpoints into main at merge commit `728f30b7e8eb58309c1c0b4e8949499515fe37fc`.
- **PR #8** (https://github.com/Hassan092-prog/KNEXUS/pull/8) merged the maintainable opt-in disposable database verification suite (`backend/tests/test_persistence_postgres.py` and `backend/tests/test_h03_h06_postgres.py`) and streamlined documentation into main at merge commit `0ee317b90c60d6106efebfacffd54fa177d60972`.
- The shared database (`knexus-postgres`, port 5435) remains unmigrated and preserved.

The accepted baseline includes the canonical H01 boundary, async fake/Ollama generation service, six persistence tables, tenant constraints, 384-dimensional pgvector embeddings, Alembic migrations, explicit demo seeding, and an opt-in disposable database verification harness (`KNEXUS_ENABLE_DISPOSABLE_PG_TESTS=1`).

## Backend implementation (Sprint 3 Verified)

The Phase 1 backend provides canonical document upload, document list/detail/status, and non-streaming query routes (`POST /api/v1/documents/upload`, `GET /api/v1/documents`, `GET /api/v1/documents/{id}`, `GET /api/v1/documents/{id}/status`, `POST /api/v1/query`). It includes:
- DOCX and PDF parsing with bounded tokenizer-aware chunking.
- Local sentence-transformers MiniLM-L6-v2 embedding service running offline with cached model weights.
- Persisted ingestion processing with transaction rollback and staged upload file cleanup on database errors.
- Tenant- and role-filtered vector retrieval before top-k ranking in PostgreSQL/pgvector.
- Demo actor identity context enforcement and safe 502/503/504 error mapping.

Sprint 3 end-to-end verification (`test_real_minilm_synthetic_corpus_e2e_flow`) confirmed the complete pipeline using real MiniLM embeddings over the synthetic employee handbook corpus:
1. `synthetic_handbook.docx` uploaded via API and stored in private upload storage.
2. Ingestion pipeline processed, chunked, and embedded into 384-dimensional pgvector records using real MiniLM weights.
3. Query `SYN-Q01` ("How many annual leave days do full-time employees receive?") returned relevant answer citations with excerpt matching.
4. Query `SYN-Q03` ("What is the organization's health insurance vendor?") abstained cleanly due to low similarity.
5. Cross-tenant query by an unauthorized actor returned zero leaked citations and abstained cleanly.

## Phase 1 progress

| Area | State | Remaining evidence or work |
|---|---|---|
| H01 boundary | Published in main | Reuse canonical schemas, synthetic actor and run_generation |
| H02 persistence | Published in main; verified in disposable PG suite | Shared database remains unmigrated; disposable migrations passed |
| Generation | Published in main; offline tests passed | Host Ollama daemon (port 11434) is offline; Naveed handoff pending live evaluation |
| H03 upload/parse/chunk | Merged in main; verified in disposable PG suite | Verified with file rollback and cleanup on DB errors |
| H04 embed/index | Merged in main; real MiniLM embedding verified | Verified real sentence-transformers inference using cached weights on synthetic corpus |
| H05 retrieval | Merged in main; verified with real MiniLM vectors | SQL tenant/role filters before top-k verified against pgvector |
| H06 API | Merged in main; verified in disposable PG suite | Document and query routes, citations, abstentions, and safe error mappings verified |
| H07 integrated demo | Backend pipeline verified on synthetic corpus | Browser frontend integration remains pending Zaid's frontend branch |
| Authentication, audit, governed actions | Not implemented | Phase 2 scope; do not use demo identity for sensitive data |
| Frontend | Zaid owns it; accepted main has no frontend app | Coordinate API contracts with Zaid once frontend is published |

## Verification evidence

### Offline verification baseline

- Full backend pytest suite: **123 passed, 18 skipped** (in ~2.2s; database integration tests skipped cleanly when no disposable DB is configured).
- Canonical contract checker (`contracts/phase1/check.py`): **17 examples and 24 negative cases passed**.
- Offline Alembic SQL rendering with synthetic settings: **passed**.
- `git diff --check` and final-newline/whitespace scan: **passed** (0 errors).

### Sprint 3 Disposable PostgreSQL/pgvector verification

Executed against an isolated disposable container (`pgvector/pgvector:pg16`) on loopback:
- Full disposable test suite: **22 passed, 0 failed** (in 15.07s).
- Persistence suite (`test_persistence_postgres.py`): 6/6 passed.
- Integration suite (`test_h03_h06_postgres.py`): 16/16 passed, including `test_real_minilm_synthetic_corpus_e2e_flow`.
- Complete absence of all disposable containers, networks, and volumes verified post-run. Protected `knexus-postgres` (port 5435) untouched.
- Durable run log: `/home/hassan/verification_archive/run_sprint3_success.log`.

## Teammate Handoff & Dependencies

### Naveed (Generation Service)
- **Current status**: Commit `be96758` on `origin/dev-naveed` is on an obsolete baseline before PR #5/7/8. The host Ollama daemon on port 11434 is currently offline (`Connection refused`).
- **Required actions**:
  1. Fast-forward or rebase `dev-naveed` onto current `main`.
  2. Implement/integrate live Ollama provider with model `qwen2.5:7b-instruct` (or approved alternative).
  3. Validate against canonical `run_generation` contract and evaluate citation retention and contradictory evidence handling.

### Zaid (Frontend Application)
- **Current status**: `origin/dev-zaid` contains only `frontend/README.md`. No UI application or scaffold has been pushed.
- **Required actions**:
  1. Base frontend development on published API specification (`docs/API_SPEC.md`).
  2. Connect to endpoints: `POST /api/v1/documents/upload`, `GET /api/v1/documents`, `GET /api/v1/documents/{id}/status`, `POST /api/v1/query`.
  3. Support non-streaming query responses, displaying citations and abstention states cleanly.

## Four-branch workflow

The persistent team branches are:

| Branch | Owner/purpose | Next step |
|---|---|---|
| main | Accepted shared implementation | Baseline for all teammate work |
| dev-hassan | Hassan's implementation branch | Fast-forward to merged PRs; maintain clean history |
| dev-naveed | Naveed's generation branch | Sync from main; evaluate live Ollama |
| dev-zaid | Zaid's frontend branch | Sync from main; build UI against verified API |

## Phase 1 Acceptance Gate Summary

- [x] Canonical contracts and Pydantic validation (`contracts/phase1/models.py`).
- [x] Schema migrations and 6 persistence tables (`backend/alembic/`).
- [x] Bounded DOCX/PDF ingestion and chunking (`backend/app/services/ingestion/`).
- [x] Sentence-transformers MiniLM-L6-v2 embeddings with 384-dim pgvector index (`backend/app/services/ingestion/embedding.py`).
- [x] Tenant- and role-isolated vector retrieval (`backend/app/services/retrieval/`).
- [x] Document and Query REST endpoints (`backend/app/api/routes/`).
- [x] Disposable PostgreSQL/pgvector integration suite with loopback protection (`backend/tests/`).
- [x] End-to-end synthetic corpus flow verified with real embeddings (`test_real_minilm_synthetic_corpus_e2e_flow`).
- [ ] Live LLM generation quality evaluation (blocked on host Ollama daemon; assigned to Naveed).
- [ ] Browser-based UI application (assigned to Zaid).
