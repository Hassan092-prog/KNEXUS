# Current status and next actions

**Checked: 2 November 2026.** This page records published work separately from local drafts. Requirements remain in the contract and playbook.

## Published baseline

PR #5 (https://github.com/Hassan092-prog/KNEXUS/pull/5) merged the reviewed H01, generation and persistence baseline into main at 5104a19e61f35d4a10e38000737e68513069f2a5. PR #7 (https://github.com/Hassan092-prog/KNEXUS/pull/7) merged the reviewed H03-H06 ingestion, retrieval, and API endpoints into main at merge commit 728f30b7e8eb58309c1c0b4e8949499515fe37fc. The shared database has not been migrated.

The accepted baseline includes the canonical H01 boundary, async fake/Ollama generation service, six persistence tables, tenant constraints, 384-dimensional pgvector embeddings, Alembic and explicit demo seeding. The generation context limit is a character ceiling, not model token accounting.

## Backend implementation (merged via PR #7)

The Phase 1 backend registers canonical upload, document list/detail/status and non-streaming query routes. It adds PDF/DOCX parsing, bounded tokenizer-aware chunking, local MiniLM embedding code, persisted ingestion processing, SQL-filtered retrieval, server-owned demo identity and contract-shaped errors.

Disposable PostgreSQL/pgvector integration verification passed across migrations, upload lifecycle rollback, and role-filtered retrieval (21/21 passed). Reusable database tests are maintained in `backend/tests/` with opt-in loopback target protection. The shared database remains unmigrated.

## Phase 1 progress

| Area | State | Remaining evidence or work |
|---|---|---|
| H01 boundary | Published in main | Reuse canonical schemas, synthetic actor and run_generation |
| H02 persistence | Published in main; separate disposable migration/test run passed | Shared database remains unmigrated; attempt-5 source-snapshot fingerprint is unavailable |
| Generation | Published in main; offline tests passed | Naveed: live Ollama quality, context policy/evaluation handoff |
| H03 upload/parse/chunk | Merged in PR #7; disposable PostgreSQL/pgvector verification passed | File cleanup on DB error and rollback assertions confirmed; background task runs in-process; abandoned-job recovery is manual only |
| H04 embed/index | Merged in PR #7; local 384-dimensional MiniLM implementation and fake embedder verified in disposable DB suite | Actual sentence-transformers inference on real weights and full corpus indexing remain separate verification steps |
| H05 retrieval | Merged in PR #7; SQL filters before top-k verified against disposable PostgreSQL | Relevance threshold, document join, and evidence formatting verified; full corpus evaluation remains |
| H06 API | Merged in PR #7; canonical document and query routes verified against disposable DB | Evidence citations, abstention, and safe 502/503/504 error mapping verified; browser and live LLM integration remain separate |
| H07 integrated demo | Small synthetic DOCX and labeled questions merged in PR #7 | Complete real upload -> processing -> authorized retrieval -> answer/abstention -> browser flow remains |
| Authentication, audit, governed actions | Not implemented | Later phase; do not use demo identity for sensitive data |
| Frontend | Zaid owns it; accepted main has no frontend application | Coordinate API types and verify with Zaid's actual frontend branch |

Naveed's older unpushed work cannot be established from GitHub. Do not restore the old generator over the reviewed main baseline. Zaid's laptop changes are likewise not visible unless published or shared.

## Verification evidence

For the merged backend implementation:

### Offline verification baseline

- Full backend pytest suite: **119 passed**.
- Canonical contract checker, run separately: **17 examples and 24 negative cases passed**.
- Offline Alembic SQL rendering with synthetic settings: **passed**; expected tables and vector(384) were present.
- git diff --check and final-newline/whitespace scan: **passed**.
- Tokenizer/chunker tests use a deterministic fake tokenizer. A separate earlier check loaded the actual MiniLM tokenizer from its existing cache with offline-only settings; no embedding inference occurred.

### Disposable PostgreSQL/pgvector integration verification (H03-H06)

Executed under explicit approval against an isolated disposable container (`pgvector/pgvector:pg16`, image ID `sha256:7b822b0aac60967beb1ea5e576b8602c94c300a157d187f385ae3e0da199b90a`) on published loopback port `127.0.0.1:32774`:

- Migration cycle: **passed** (initial upgrade -> idempotent repeat upgrade -> 6 schema tables verified -> downgrade base -> 0 tables verified and pgvector extension retained -> re-upgrade head -> 6 tables verified).
- Combined integration suite: **21 passed** (17 database integration cases + 4 offline cases, in 4.49s).
  - Persistence foundation suite (`test_persistence_postgres.py`): 5 database cases and 1 offline case passed.
  - H03-H06 integration suite (`test_h03_h06_postgres.py`): 12 database cases and 3 offline cases passed.
- Upload failure cleanup and rollback: **passed** (verified that a rejected upload deletes its staged file from private storage, rolls back the transaction, and persists zero document records).
- All disposable resources cleaned up and absence verified (container, bridge network, volume, sanitized temp copy). Protected `knexus-postgres` and `knexus_postgres_data` were untouched.
- Successful run log: `run_20261102_005900.log` under `/tmp/knexus-h03-h06-verification-20261101-ppbpi3wh/`.
- Tested snapshot manifest: `tested-source-20261101_h03h06_1a6c360d.sha256` (SHA-256: `709c91bf43b14b6bc43dd2879f0f3b82c529dc8231be0245a49425e3c096626f`).
- Historical Run 1 evidence preserved: `run_20261102_004144.log` (19 passed, 1 failed due to harness exception-inspection unwrapping defect, since resolved).
- Note: Documentation updates made after the snapshot are tracked separately.

### Earlier H02 persistence verification

The earlier disposable H02 verification was a separate run against a disposable PostgreSQL/pgvector database: migration upgrade, repeat upgrade, downgrade, downgraded-state check and re-upgrade passed. It reported five database tests plus one offline wrapped-exception regression. The attempt-5 log is retained outside Git under `/tmp/knexus-pgverify-review-20261101/`. **Provenance limitation:** it does not fingerprint the exact sanitized source snapshot used for that run.

### Remaining limitations

- Merged into main via PR #7.
- The shared database (`knexus-postgres`) has not been migrated.
- Deterministic fake providers were used for embedding and generation in the integration tests; live MiniLM embedding inference and Naveed's Ollama generation service remain separate verification steps.
- Ingestion runs in-process via FastAPI background tasks; a durable worker queue remains future work.
- Zaid's browser frontend integration remains separate.

## Four-branch workflow

The persistent team branches are:

| Branch | Owner/purpose | Next step |
|---|---|---|
| main | Accepted shared implementation | Use the published revision as baseline |
| dev-hassan | Hassan's implementation/publication branch | Preserve original checkout's existing pending changes; fast-forward to merged baseline for future sprints |
| dev-naveed | Naveed's generation branch | Coordinate a reviewed sync from main and report live evaluation evidence |
| dev-zaid | Zaid's frontend | Coordinate a reviewed sync from main and confirm framework/API fixtures |

Temporary integration and review branches were retired only after their merged work remained reachable from main. Local branch/worktree state does not reveal unpublished laptop changes.

## Next sequence

1. PR #7 merged into main. Complete Sprint 1 maintainable tests/docs.
2. Naveed completes and reports the agreed generation evaluation against the reviewed baseline.
3. Zaid confirms the frontend framework and connects the published API contract using mock and live failure states.
4. Live embedding and generation service verification and browser end-to-end integration remain pending, requiring explicit approval when components are published and ready.
5. Close Phase 1 only when upload, persisted processing, authorized retrieval, cited answer/abstention and failure cases work together with evidence.

The playbook (PHASE_1_TEAM_GUIDE.md) defines task gates; CONTRIBUTING.md owns setup and Git commands. Historical checks do not prove today's service, permissions or shared database state.
