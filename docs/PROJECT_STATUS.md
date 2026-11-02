# Current status and next actions

**Checked: 2 November 2026.** This page records published work separately from local drafts. Requirements remain in the contract and playbook.

## Published baseline

- **PR #5** (https://github.com/Hassan092-prog/KNEXUS/pull/5) merged the reviewed H01 boundary, generation foundation, and persistence baseline into main at `5104a19e61f35d4a10e38000737e68513069f2a5`.
- **PR #7** (https://github.com/Hassan092-prog/KNEXUS/pull/7) merged the reviewed H03-H06 ingestion, retrieval, and API endpoints into main at merge commit `728f30b7e8eb58309c1c0b4e8949499515fe37fc`.
- **PR #8** (https://github.com/Hassan092-prog/KNEXUS/pull/8) merged the maintainable disposable database verification suite (`backend/tests/test_persistence_postgres.py` and `backend/tests/test_h03_h06_postgres.py`) and centralized documentation into main at merge commit `0ee317b90c60d6106efebfacffd54fa177d60972`.
- **PR #9** (https://github.com/Hassan092-prog/KNEXUS/pull/9) merged the end-to-end synthetic corpus integration test with real MiniLM embeddings into main at merge commit `52e7c18d0afa1a51e46f151e0df1ff569e814433`.
- The shared development database (`knexus-postgres`, port 5435) remains unmigrated and strictly protected.

## Backend implementation and verification scope

The Phase 1 backend provides canonical document upload, document status/detail, and non-streaming query routes (`POST /api/v1/documents/upload`, `GET /api/v1/documents`, `GET /api/v1/documents/{id}`, `GET /api/v1/documents/{id}/status`, `POST /api/v1/query`).

### Scope of Sprint 3 Integration Verification
The end-to-end verification (`test_real_minilm_synthetic_corpus_e2e_flow`) proves **real embedding, vector retrieval, and REST API integration with fake generation**:
- Ingests `synthetic_handbook.docx` via `POST /api/v1/documents/upload`.
- Generates 384-dimensional vector embeddings using cached `sentence-transformers/all-MiniLM-L6-v2` weights loaded offline.
- Persists chunks and vector embeddings into pgvector.
- Performs cosine similarity retrieval with tenant and role SQL filtering.
- Exercises `EchoGenerator` to verify canonical response citations and abstentions without external network access.
- Proves policy citation excerpt extraction (`SYN-Q01`), clean abstention on irrelevant queries (`SYN-Q03`), and complete cross-tenant evidence isolation.
- **Important boundary**: This test does **not** evaluate live LLM generation quality or browser interaction. Live LLM answer quality and browser UI acceptance gates remain incomplete.

## Hardened database isolation guard

Disposable PostgreSQL tests require explicit opt-in (`KNEXUS_ENABLE_DISPOSABLE_PG_TESTS=1`). A hardened shared guard (`backend/tests/postgres_guard.py`) enforces strict isolation gates before any database connection:
- Rejects protected port 5435 unconditionally, regardless of database or username.
- Requires a valid unique run identity (`KNEXUS_DISPOSABLE_RUN_ID` / `KNEXUS_RUN_TAG`).
- Requires synthetic naming for both database and user incorporating the unique run identity.
- Performs bounded container inspection (5s timeout) to verify that the target URL matches the owned disposable container's inspected runtime port.
- Verifies image (`pgvector/pgvector:pg16`), volume mount (`/var/lib/postgresql/data`), absence of host bind mounts, network attachment, and ownership labels (`com.knexus.pgverify.owner` and `com.knexus.pgverify.run`).
- Fails closed with explicit `DatabaseGuardError` exceptions on any missing evidence, mismatch, or inspection error.
- Dedicated offline regressions (`backend/tests/test_postgres_guard.py`) verify all negative rejection paths and positive acceptance without connecting to any database.

## Phase 1 progress

| Area | State | Remaining evidence or work |
|---|---|---|
| H01 boundary | Published in main | Reuse canonical schemas, synthetic actor and run_generation |
| H02 persistence | Published in main; verified in disposable PG suite | Shared database remains unmigrated; disposable migrations passed |
| Generation | Baseline generator in main; offline tests pass | Blocked on Naveed: live generation evaluation and agreed endpoint handoff |
| H03 upload/parse/chunk | Merged in main; verified in disposable PG suite | Verified with file rollback and cleanup on DB errors |
| H04 embed/index | Merged in main; real MiniLM embedding verified | Verified real sentence-transformers inference using cached weights on synthetic corpus |
| H05 retrieval | Merged in main; verified with real MiniLM vectors | SQL tenant/role filters before top-k verified against pgvector |
| H06 API | Merged in main; verified in disposable PG suite | Document and query routes, citations, abstentions, and safe error mappings verified |
| H07 integrated demo | Backend pipeline verified on synthetic corpus | Browser frontend integration remains pending Zaid's frontend branch |
| Authentication, audit, governed actions | Not implemented | Phase 2 scope; do not use demo identity for sensitive data |
| Frontend | Zaid owns it; accepted main has no frontend app | Coordinate API contracts with Zaid once frontend is published |

## Verification evidence

### Offline verification baseline

- Full backend pytest suite: **136 passed, 18 skipped** (in ~2.5s; database integration tests skipped cleanly when no disposable DB is configured; all 13 guard regressions pass offline).
- Canonical contract checker (`contracts/phase1/check.py`): **17 examples and 24 negative cases passed**.
- Offline Alembic SQL rendering with synthetic settings: **passed**.
- `git diff --check` and whitespace check: **passed** (0 errors).

### Disposable PostgreSQL/pgvector integration verification

Executed against an isolated disposable container (`pgvector/pgvector:pg16`) on loopback:
- Full disposable test suite: **22 passed, 0 failed** (persistence, H03-H06 integration, real MiniLM embedding and retrieval flow).
- Complete absence of all disposable containers, networks, and volumes verified post-run. Protected `knexus-postgres` (port 5435) untouched.
- Historical log preserved at `/home/hassan/verification_archive/run_sprint3_success.log`. Fresh hardened run log recorded at `/home/hassan/verification_archive/run_hardened_guard_success.log`.

## Teammate Handoff & Dependencies

### Naveed (Generation Service: N01-N06)
- **Current status**: `origin/dev-naveed` remains at published commit `be967583426495ee70b0d6c49bc364ba2aa8ef78` (Oct 26), which diverged before the Phase 1 canonical contracts and merged backend baseline. His branch is preserved without rebasing, force-pushing, or overwriting.
- **Specific inputs needed**:
  1. Provide Naveed's actual generation patch/commit resolving merge conflicts against `origin/main` (`52e7c18`).
  2. Provide the reachable approved Ollama endpoint and model configuration agreed with Naveed (`llama3.2:3b` default per `backend/app/services/generation/README.md`, or his specified alternative).
  3. Provide live generation evaluation results (N02-N06) documenting citation retention, response shaping, and abstention behavior on contradictory evidence.

### Zaid (Frontend Application: Z01-Z06)
- **Current status**: `origin/dev-zaid` contains only `frontend/README.md`. No frontend application or scaffold has been published.
- **Specific inputs needed**:
  1. Provide Zaid's actual frontend commit or pull request targeting `main`.
  2. Implement client views against the published API specification (`docs/API_SPEC.md`): document upload (`POST /api/v1/documents/upload`), document list/status (`GET /api/v1/documents`, `GET /api/v1/documents/{id}/status`), and non-streaming query (`POST /api/v1/query`).
  3. Ensure UI cleanly renders citations and evidence-based abstentions.

## Four-branch workflow

The persistent team branches are:

| Branch | Owner/purpose | Next step |
|---|---|---|
| main | Accepted shared implementation | Baseline for all teammate work |
| dev-hassan | Hassan's implementation branch | Fast-forward to merged PRs; maintain clean history |
| dev-naveed | Naveed's generation branch | Preserve published commit; await Naveed's generation patch |
| dev-zaid | Zaid's frontend branch | Preserve published commit; await Zaid's frontend commit/PR |

## Phase 1 Acceptance Gate Summary

- [x] Canonical contracts and Pydantic validation (`contracts/phase1/models.py`).
- [x] Schema migrations and 6 persistence tables (`backend/alembic/`).
- [x] Bounded DOCX/PDF ingestion and chunking (`backend/app/services/ingestion/`).
- [x] Sentence-transformers MiniLM-L6-v2 embeddings with 384-dim pgvector index (`backend/app/services/ingestion/embedding.py`).
- [x] Tenant- and role-isolated vector retrieval (`backend/app/services/retrieval/`).
- [x] Document and Query REST endpoints (`backend/app/api/routes/`).
- [x] Hardened disposable PostgreSQL/pgvector integration suite with container ownership proof and protected-port rejection (`backend/tests/`).
- [x] End-to-end synthetic corpus flow verified with real MiniLM embeddings, vector search, and fake generation (`test_real_minilm_synthetic_corpus_e2e_flow`).
- [ ] Live LLM generation quality evaluation (blocked on external input; assigned to Naveed).
- [ ] Browser-based UI application (blocked on external input; assigned to Zaid).
