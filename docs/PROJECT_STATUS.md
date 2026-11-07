# Current status and next actions

**Checked: 6 November 2026.** This page records published work separately from local drafts. Requirements remain in the contract and playbook.

## Approved rectification and immediate work

As of 2 November 2026, the target is hosted APIs for both generation and embeddings with selective reuse from the exact personal-project revision in [TRD](TRD.md). Local inference, model downloads and Ollama reverse tunnels are superseded setup instructions. Historical code and results remain preserved, not relabeled as hosted success.

Fresh remote checks: main and dev-hassan are `7e56499d23d538216d9d1074973e11b325143626`; dev-naveed is `e2658b627c8d92f35bd2d6e77b812175985e99d2`; dev-zaid is `5ba45ba30eb66d4d0dee5f0a2750f437575aa8e5`.

[PR #13](https://github.com/Hassan092-prog/KNEXUS/pull/13) merged the hosted chat-completions adapter. [PR #15](https://github.com/Hassan092-prog/KNEXUS/pull/15) is independently verified open, draft and unmerged, with four changed files and one commit e2658b6; it adds the hosted evaluation harness and development/held-out groups. Its gates do not authorize calls or enforce a spending budget.

Immediate sequence:
1. Keep the latest free-first direction: no paid API expenditure, billing upgrade, automatic model/provider fallback or retries is authorized. The older Groq/OpenAI-1536 and $5 envelope is a proposal, not an operational grant. Account-specific free access, quotas, privacy and the final embedding model/dimension remain unresolved.
2. Review/reuse PR #15 and agree Settings-to-constructor wiring. Current API dependencies still pass legacy OLLAMA_* configuration; hosted environment variables alone do not establish working route integration.
3. Resolve strict generation input-token enforcement, reasoning/output accounting, schema compatibility and a shared durable attempt/quota ledger before live acceptance. Continue mocks without external calls.
4. Hassan owns hosted embeddings and safe model/profile/storage transition preserving existing vectors. Naveed owns bounded generation changes. Zaid owns frontend adaptation and browser evidence. Preserve the pinned source-reuse policy in TRD.
5. Verify isolated API and hosted/browser acceptance only under explicit authorization; no merge is a prerequisite for isolated testing. Phase 1 remains incomplete.

The primary checkout was observed on local main at b8414f2 with 70 tracked modified paths plus an untracked H:/ directory. Preserve every pending file; do not assume older reports of 43 changes are current. Status synchronization is prepared in a separate checkout and performs no application or database changes.

## Published baseline

- **PR #5** (https://github.com/Hassan092-prog/KNEXUS/pull/5) merged the reviewed H01 boundary, generation foundation, and persistence baseline into main at `5104a19e61f35d4a10e38000737e68513069f2a5`.
- **PR #7** (https://github.com/Hassan092-prog/KNEXUS/pull/7) merged the reviewed H03-H06 ingestion, retrieval, and API endpoints into main at merge commit `728f30b7e8eb58309c1c0b4e8949499515fe37fc`.
- **PR #8** (https://github.com/Hassan092-prog/KNEXUS/pull/8) merged the maintainable disposable database verification suite (`backend/tests/test_persistence_postgres.py` and `backend/tests/test_h03_h06_postgres.py`) and centralized documentation into main at merge commit `0ee317b90c60d6106efebfacffd54fa177d60972`.
- **PR #9** (https://github.com/Hassan092-prog/KNEXUS/pull/9) merged the end-to-end synthetic corpus integration test with real MiniLM embeddings into main at merge commit `52e7c18d0afa1a51e46f151e0df1ff569e814433`.
- **PR #10** (https://github.com/Hassan092-prog/KNEXUS/pull/10) merged the hardened database isolation guards into main at merge commit `b8414f2f0a53bcd0d6078a5b63b910845a1dc53e`.
- **PR #11** (https://github.com/Hassan092-prog/KNEXUS/pull/11) merged the live docker inspection guard corrections and image-ID verification into main at merge commit `52d6ab392b3a82a28236433c34f8038b0dffbe0c`.
- **PR #12** (https://github.com/Hassan092-prog/KNEXUS/pull/12) merged Naveed's seven-file generation baseline and evaluation harness into main at merge commit `d65a1a80477008b987874041b3a69f25580e5377`.
- **PR #14** (https://github.com/Hassan092-prog/KNEXUS/pull/14) published the hosted-API/source-reuse documentation at merge commit `8664551ea87ceec47e2c99c4c133b987c987376e`.
- **PR #13** (https://github.com/Hassan092-prog/KNEXUS/pull/13) merged the hosted generation transport at `1d4a06100b590a5f2a77830cbb3772eb789f0f47`. Transport presence does not establish hosted API wiring or live acceptance.
- **PR #16** (https://github.com/Hassan092-prog/KNEXUS/pull/16) merged the offline hosted embedding and dispatch policy foundation into main at merge commit `da306c657c47280d370b4402afe31cb1b104035e`.
- **PR #18** (https://github.com/Hassan092-prog/KNEXUS/pull/18) merged dev-zaid branch synchronization into main at merge commit `0b0dc009c1cda6f68abd3da7925182bf23dfc3b4`.
- **PR #19** (https://github.com/Hassan092-prog/KNEXUS/pull/19) merged the hosted input validation, token counting, monotonic deadline enforcement, and source-preserving candidate splitting slice into main at merge commit `7e56499d23d538216d9d1074973e11b325143626`.
- The shared development database (`knexus-postgres`, port 5435) remains unmigrated and strictly protected.

## Backend implementation and verification scope

The Phase 1 backend provides canonical document upload, document status/detail, and non-streaming query routes (`POST /api/v1/documents/upload`, `GET /api/v1/documents`, `GET /api/v1/documents/{id}`, `GET /api/v1/documents/{id}/status`, `POST /api/v1/query`).

### Historical Sprint 3 integration verification (local embedding, fake generation)
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
- Requires non-empty expected settings (`KNEXUS_DISPOSABLE_CONTAINER`, `KNEXUS_DISPOSABLE_VOLUME`, `KNEXUS_DISPOSABLE_NETWORK`, `KNEXUS_DISPOSABLE_RUN_ID`), failing closed if any are missing or malformed.
- Rejects protected resource names unconditionally (`knexus-postgres`, `knexus_postgres_data`, `knexus`, `knexus_admin`).
- Removed `KNEXUS_DISPOSABLE_INSPECT_JSON` environment bypass from runtime behavior; retains `inspect_fn` injection solely for offline unit tests.
- Requires exact approved tag (`pgvector/pgvector:pg16`) AND immutable image ID (`sha256:7b822b0aac60967beb1ea5e576b8602c94c300a157d187f385ae3e0da199b90a`).
- Verifies ownership labels on container, volume, and network (`com.knexus.pgverify.owner` and `com.knexus.pgverify.run`).
- Enforces exactly one volume mount to `/var/lib/postgresql/data` (rejecting host bind mounts) and loopback publication.
- Dedicated offline regressions (`backend/tests/test_postgres_guard.py`: 18 tests) verify all 4 confirmed reviewer bypasses and safety assertions without Docker or database calls.

## Phase 1 progress

| Area | State | Remaining evidence or work |
|---|---|---|
| H01 boundary | Published in main | Reuse canonical schemas, synthetic actor and run_generation |
| H02 persistence | Published in main; verified in disposable PG suite | Shared database remains unmigrated; disposable migrations passed |
| Generation | PR #13 hosted adapter merged; PR #15 harness remains draft | Legacy API wiring, provider accounting/schema work and live acceptance remain open |
| H03 upload/parse/chunk | Merged in main; verified in disposable PG suite | Verified with file rollback and cleanup on DB errors |
| H04 embed/index | Offline foundation (PR #16) and input validation (PR #19) merged in main | Live Google token correspondence verification, account eligibility, and existing-corpus transition/activation remain pending. Paid budget is $0; live calls unauthorized |
| H05 retrieval | Merged in main; verified with real MiniLM vectors | SQL tenant/role filters before top-k verified against pgvector; query token limit validation merged (PR #19) |
| H06 API | Merged in main; verified in disposable PG suite | Document and query routes, citations, abstentions, safe error mappings, and token limit HTTP 422/503 errors verified |
| H07 integrated demo | Backend pipeline verified offline with mocks; integration handoff prepared | PR #15 generation integration, live acceptance authorization, and Zaid's frontend application remain pending |
| Authentication, audit, governed actions | Not implemented | Phase 2 scope; do not use demo identity for sensitive data |
| Frontend | Zaid owns it; accepted main has no frontend app | Coordinate API contracts with Zaid once frontend is published |

## Verification evidence

### Historical offline verification baseline (not a fresh run)

- Full backend pytest suite: **100 passed, 18 skipped** (in ~2.1s; database integration tests skipped cleanly when no disposable DB is configured; all 18 guard regressions pass offline).
- Canonical contract checker (`contracts/phase1/check.py`): **17 examples and 24 negative cases passed**.
- Offline Alembic SQL rendering with synthetic settings: **passed**.
- `git diff --check` and whitespace check: **passed** (0 errors).

### Historical disposable PostgreSQL/pgvector verification

Executed against an isolated disposable container (`pgvector/pgvector:pg16`) on loopback via hardened runner `verify_phase1_tooling_hardened.sh`:
- Full disposable test suite: **40 passed, 0 failed** in 19.04s:
  - 18 offline guard regressions (`test_postgres_guard.py`).
  - 6 persistence & pgvector integration tests (`test_persistence_postgres.py`).
  - 16 H03-H06 API, role-filtering, and real MiniLM synthetic corpus tests (`test_h03_h06_postgres.py`).
- Full Alembic upgrade/downgrade/re-upgrade lifecycle verified against disposable database.
- Complete absence of all disposable containers, networks, and volumes verified post-run. Protected `knexus-postgres` (port 5435) untouched.
- Fresh run log recorded at `/home/hassan/verification_archive/run_tooling_hardened_success.log`.
- SHA-256 manifests preserved at `/home/hassan/verification_archive/manifest_tooling_hardened_20261102.sha256` and `/home/hassan/verification_archive/tested-source-20261102_hardened_3440601e.sha256`.

## Teammate Handoff & Dependencies

### Naveed (Generation Service: N01-N06)
- PR #13 adapter is merged. Draft PR #15 head is e2658b627c8d92f35bd2d6e77b812175985e99d2; main/base is 1d4a06100b590a5f2a77830cbb3772eb789f0f47. GitHub currently reports zero comments/reviews. No new generation implementation was authorized by the supplied handoff requests.
- Rev 2 of Naveed's 4 November handoff supersedes rev 1. The handoff is an external local artifact, not a PR comment or merged code. It proposes provider-aware output/schema handling, pre-validation usage capture, optional reasoning controls and durable cross-process reservations.
- Remaining gates: real input-token bound including framing/schema, reasoning completion accounting, shared ledger/recovery design, schema compatibility projection and agreed secret-safe Settings wiring. include_reasoning=false does not establish reduced generation or billing; chars/3 and post-call usage do not enforce a pre-call token ceiling.
- Fixed public rate tables are not account limits, and a maximum campaign allowance does not require immediate use or a paid plan. Do not repeat rev 1's incorrect rate figures or rev 2's residual reference to the superseded 8K-TPD assumption.
- Teammate-reported Windows checks: 195 passed, 18 skipped, 1 failed; canonical checker reported passing. The pre-existing Windows permission failure remains separate. These outputs were not rerun or independently inspected during this status update and are not hosted acceptance evidence.
- Live calls, paid expenditure and implementation remain unapproved by the handoff. No model tunnel or local inference is required.

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
| main | Accepted shared implementation | Baseline for all teammate work (`7e56499d23d538216d9d1074973e11b325143626`) |
| dev-hassan | Hassan's implementation branch | Fast-forwarded to merged PR #19 (`7e56499d23d538216d9d1074973e11b325143626`) |
| dev-naveed | Naveed's generation branch | PR #13 adapter merged; PR #15 draft at `e2658b6`; resolve integration decisions |
| dev-zaid | Zaid's frontend branch | PR #18 merged into main; await Zaid's frontend application commit/PR |

## Phase 1 Acceptance Gate Summary

- [x] Canonical contracts and Pydantic validation (`contracts/phase1/models.py`).
- [x] Schema migrations and 6 persistence tables (`backend/alembic/`).
- [x] Bounded DOCX/PDF ingestion and chunking (`backend/app/services/ingestion/`).
- [x] Historical local MiniLM implementation and 384-dimensional pgvector index; this is not hosted acceptance.
- [x] Tenant- and role-isolated vector retrieval (`backend/app/services/retrieval/`).
- [x] Document and Query REST endpoints (`backend/app/api/v1/endpoints/`).
- [x] Hardened disposable PostgreSQL/pgvector integration suite with container/volume/network ownership proof, immutable image ID, and protected-port rejection (`backend/tests/`).
- [x] Historical synthetic corpus flow verified with local MiniLM embeddings, vector search, and fake generation (`test_real_minilm_synthetic_corpus_e2e_flow`).
- [x] Hosted generation transport merged through PR #13; mocked evidence only.
- [x] Offline hosted embedding dispatch protection and quota ledger foundation (PR #16).
- [x] Hosted input-token validation, correspondence checks, candidate splitting, and monotonic deadline enforcement (PR #19).
- [ ] Live Google embedding token correspondence verification and corpus activation/migration (Hassan).
- [ ] PR #15 review, hosted API wiring, token/usage controls and live acceptance (Hassan/Naveed).
- [ ] Browser-based UI application (blocked on external input; assigned to Zaid).
