# KNEXUS repository and documentation review

**Review date:** 19 October 2026. **Scope:** the original review covered all 37 files then tracked, including source/configuration, Markdown, Office documents/templates, PDFs and research references. Follow-ups include this report, the Phase 1 guide and the team responsibilities guide. Workspace operations use SSH to `hassan@192.168.1.92`. The original review began with a clean tree; later edits retain the preceding uncommitted documentation work.

## Assessment

KNEXUS is a **foundation scaffold**, with much more extensive design documentation than implementation. It is not yet a working RAG assistant or a secure multi-tenant application. The documentation now distinguishes current behavior from planned requirements. This review changes documentation only; code findings below remain implementation work.

## Current implementation and file coverage

| Files | What was reviewed / actual behavior |
|---|---|
| `backend/app/__init__.py` | Package version 0.1.0 |
| `backend/app/main.py` | FastAPI setup, local CORS allowlist, docs/OpenAPI paths, root response, startup logging and shutdown engine disposal |
| `backend/app/api/v1/router.py` | Includes only the health router |
| `backend/app/api/v1/endpoints/health.py` | SQL connectivity/vector probes and Ollama `/api/tags`; no generation |
| `backend/app/core/config.py` | Cached Pydantic settings; `.env` relative to process working directory; independent URL/POSTGRES defaults |
| `backend/app/core/database.py` | Async engine, session dependency, empty declarative base; no models or table creation |
| `backend/requirements.txt` | Framework/database/ML/document/auth/test dependencies declared with minimum versions; no lockfile; Ruff/Locust/evaluation libraries absent |
| `docker-compose.yml`, `docker/init.sql` | PostgreSQL 16 with vector extension and persistent volume; Ollama commented out; API/frontend services absent; init creates extension only |
| `.env.example`, `.gitignore` | Development defaults and standard exclusions; auth/model settings do not implement those features; no dedicated raw-dataset ignore rules |
| `README.md`, `CONTRIBUTING.md` | Rewritten current capabilities and root-based POSIX/PowerShell setup |
| `frontend/README.md`, `data/README.md` | Clarified that proposed application/data directories and fixtures are absent |
| `docs/INDEX.md` | Complete linked inventory and document precedence |
| `docs/PRD.md`, `TRD.md`, `ARCHITECTURE.md` | Target requirements, technical baseline, proposed tree/diagrams; added current-state boundaries and corrected conflicts |
| `docs/API_SPEC.md`, `DATABASE_SCHEMA.md`, `SECURITY_MODEL.md` | Current routes/DB/security behavior separated from proposed contracts and controls |
| `docs/EVALUATION_STRATEGY.md`, `KNEXUS_Project_Plan.md`, `KNEXUS_Team_Git_Workflow_Guide.md`, `PHASE_1_TEAM_GUIDE.md` | Corrected benchmark accounting, planning/academic conflicts, persistent branches, task ownership, and collaboration prompts |

No ingestion, embedding inference, search, answer generation, JWT validation, tenant/role policy, approval engine, business audit log, frontend source/package manifest, migration files, feature-level test suite or CI workflow is implemented. Standalone contract references/checks are prepared separately for the first team review. SQLAlchemy metadata is empty. Installed packages are not feature implementations.

## Prioritized implementation findings

| Priority | Finding and evidence | Required next action |
|---|---|---|
| High | `health.py` returns HTTP 200 for dependency failure. Missing vector/offline Ollama can leave `status=healthy`. Confirmed with controlled failure probes. | Define required dependencies; add separate liveness/readiness behavior and appropriate failure status codes. Test each dependency state. |
| High | `health.py` includes raw database exception text in a public response. SQL echo follows `DEBUG=True`. | Return bounded generic diagnostics, keep redacted detail in server logs, and disable SQL echo outside development. |
| High | No auth/RBAC/tenant enforcement exists. Compose publishes PostgreSQL on all host interfaces, using the bootstrap administrator by default. | Keep the current scaffold local with synthetic data; implement identity and tenant checks with initial data APIs, use a least-privilege runtime role, and decide explicit network bindings. |
| High (design) | Draft DDL has independent tenant/parent foreign keys; duplicated `org_id` does not prove parent ownership. Embedding ACLs can become stale. | Add composite ownership constraints, synchronized permission changes, and parent-document checks before exposing retrieval. |
| High (design) | Hash-only action examples did not establish atomic claims, replay protection, or exact action binding. | Specify immutable action envelopes, atomic transitions, execution-time authorization, idempotency, and verification before tool execution. |
| Medium | `Settings` uses `env_file=".env"`; old setup changed into `backend/` but copied the root file. | Documentation now launches from root with `--app-dir backend`. A future code change could resolve the env path explicitly. |
| Medium | `DATABASE_URL` is a separate literal default; changing `POSTGRES_*` alone does not update it. | Explicitly update the URL today; consider constructing/validating it in settings later. |
| Medium | Backend startup does not verify database/model readiness. DB probes have no explicit handler-level deadline. | Define connection/query timeouts and readiness policy; do not interpret the Ollama HTTP timeout as an end-to-end bound. |
| Medium | Requirements are lower bounds, not pinned dependencies; no automated checks exist. | Establish a tested dependency lock and meaningful tests/CI with actual tooling installed. |
| Medium (design) | No sessions/history/sandbox-action persistence is defined in the current seven-table DDL proposal. | Decide these schemas before implementing refresh revocation, streaming history, or governed writes. |

## Documentation corrections made

- Removed claims that RAG, autonomous agents, UI, observability, or production readiness are delivered today. Added status notices to every core design document.
- Standardized the documented API launch port to **8000**, PostgreSQL host port **5435** / container port **5432**, and Python team baseline **3.12**.
- Fixed root `.env` setup/launch commands, included PowerShell equivalents, and explained cached settings, explicit database URLs, existing-volume behavior, and optional Ollama.
- Listed implemented routes before proposed contracts; documented HTTP-200 health limitations and absent authentication. Corrected proposed JSON examples, proposal status filters, hash representation, and role inheritance consistency.
- Reconciled the TRD error contract with API_SPEC and labeled the alternative response envelope as an unselected proposal. Corrected the example Ruff configuration location/table format.
- Replaced the proposed 512/50-token chunk setting with a **240-token / 32-token overlap starting budget** for MiniLM, with tokenizer-based validation. Documented dimension migration requirements. This is a design correction, not a configured chunker or measured optimum.
- Restored **20 Miscellaneous** questions so the evaluation categories total **500**. Corrected Constrained-category meaning; added subset/source coverage, held-out evaluation, document/chunk scoring boundaries, and false-abstention reporting.
- Aligned planned precision@5 to **0.70**, first-token targets to **p50 <= 5s / p95 <= 8s**, and full-response p95 to **12s**. These are acceptance targets, not results.
- Marked sample benchmark results and tests/CI snippets as illustrative. Removed the unsupported `--benchmark` invocation and the claim that dependencies are pinned.
- Reconciled contribution guides around persistent `dev-hassan`, `dev-naveed` and `dev-zaid` branches with merge-commit PRs. Removed guarantees about merge conflicts and fast-forward frequency.
- Corrected the RAG paper publication year, noted academic eligibility concerns, and made security enforcement a prerequisite for initial ingestion/retrieval rather than an optional later layer.

## Academic and binary document review

Text-bearing PDFs were extracted with `pdftotext`; DOCX/PPTX text and slide notes were inspected from their XML. Legacy DOCs were converted in temporary directories solely for text inspection. The scanned notice was rendered and visually read. Original binary files were preserved. This is a content/consistency review, not a full visual-layout certification of every Office artifact or independent replication of research results.

| Artifact | Findings / disposition |
|---|---|
| `Guidelines and NOtices/Project Guidelines.pptx` | Requires base paper in a reputed journal on/after 2021 and at least ten surveyed papers not earlier than 2021. Also describes ten-minute base-paper and fifteen-minute final seminars. Preserve original requirements. |
| `Guidelines and NOtices/major project review notice.pdf` | Scanned notice dated **3 October 2026** lists eight content sections, one-page abstract plus base/two supporting paper hardcopies, and no rescheduling. It does not establish the actual seminar date. Eight sections do not require exactly eight slides. |
| `Templates/Major Project Abstract Template-2026-2027.doc` | Original blank institutional form; placeholders are intentional. Preserve it. |
| `Templates/PROJECT PPT TEMPLATE.pptx` | Original slide template with placeholders and comparison-table layouts. Preserve it. |
| `docs/Abstract/Major Project Abstract 2026-2027.doc`, `docs/Abstract/Abstract.pdf` | Proposal text is consistent with the planned platform. Course, branch, team number/size, student details, guide details, and signatures remain incomplete. Fill verified details and regenerate the PDF together before submission. |
| `docs/PPT/KNEXUS Team 3.pptx` | Ten-slide proposal covers the eight required topics, with architecture and contents slides. Surveys three papers only. Uses PyMuPDF while backend requirements/TRD select pdfplumber; reconcile parser choice in the next deck revision. Claims describe proposed capabilities, not completed implementation. |
| `docs/KNEXUS_Dataset_Selection_and_Evaluation_Strategy.pdf` | Correctly includes Miscellaneous and cautions against treating a corpus as an RBAC/action benchmark. Counts are a historical research snapshot. Use the corrected Markdown strategy and pin an imported revision before formal scoring. |
| `docs/OpsPilot_AI_Final_Startup_Blueprint.docx` | Broader startup/background proposal: eight-week schedule, different role names/memberships, organization-prefixed API, PDF/TXT/Markdown ingestion, and PyMuPDF differ from KNEXUS designs. It explicitly excludes incident management from the MVP. Treat it as background; do not silently mix its routes/schema with KNEXUS API_SPEC. |
| `docs/Research Papers/Base_Paper.pdf` | Lewis et al., RAG, **NeurIPS 2020**. Bundled arXiv v4 is dated April 2021; that is a revision date. Foundation for retrieval/generation, not evidence that KNEXUS has permissions or governed actions. |
| `docs/Research Papers/research_paper_1.pdf` | Toolformer, Schick et al., 2023. Research background for learned tool use, not an authorization/approval design or enterprise corpus. |
| `docs/Research Papers/research_paper_2.pdf` | AgentCDM, Zhao et al., 2025 preprint. Structured collaborative decision-making background; does not establish an enterprise RAG/citation/security evaluation. |

**Academic decision still needed:** the current base paper's year and conference venue conflict with the bundled journal/2021+ guideline. The deck already cites it correctly as 2020. Obtain a guide/coordinator ruling or select a qualifying base paper, retaining Lewis et al. as foundational background. Do not relabel a revision year as publication year. Expand the literature survey to meet the ten-paper requirement with qualifying references. The actual Review-I date and authorization for exceptions are not established by this repository.

## Validation performed

Using the existing Python 3.12 backend virtual environment:

- Parsed all tracked Python source files for syntax errors.
- Ran the FastAPI lifespan and HTTPX ASGI probes: root, Swagger, ReDoc, and generated OpenAPI returned 200. OpenAPI application paths are exactly `/` and `/api/v1/health`.
- Confirmed representative proposed auth/query/document/action routes return 404.
- Ran the real read-only health query against the existing PostgreSQL container: database connected, vector installed, Ollama offline. Aggregate status was still healthy, as the source predicts.
- Overrode the database and Ollama dependencies in memory to confirm missing-vector/offline behavior and HTTP-200/degraded/raw-exception behavior on database failure. No persistent test files or application changes were made.
- Checked Compose configuration with `docker compose config --quiet`; the existing PostgreSQL service reported healthy. No services or data volumes were created, stopped, or reset.
- Checked Markdown relative links, JSON example syntax, control characters, benchmark category arithmetic, and patch whitespace with `git diff --check`.

No fresh dependency installation, Windows runtime launch, frontend build, retrieval benchmark, load test, security guarantee, or academic compliance signoff is claimed. Those capabilities are absent or outside this documentation review.

## Primary references checked

- [EnterpriseRAG-Bench upstream repository](https://github.com/onyx-dot-app/EnterpriseRAG-Bench): 500 questions across ten categories; Constrained and Miscellaneous definitions. Exact import counts still need a pinned manifest.
- [MiniLM model card](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2): 384-dimensional embeddings and default truncation above 256 wordpieces.
- [NeurIPS RAG publication](https://papers.nips.cc/paper/2020/hash/6b493230205f780e1bc26945df7481e5-Abstract.html): publication year 2020.
- [Ollama Llama 3.2 model listing](https://ollama.com/library/llama3.2): default 3B model; the prior 8B Llama 3.2 description was incorrect.

## Team workflow and ownership

Hassan is Member 1, Naveed is Member 2 and Zaid is Member 3. The [team responsibilities](TEAM_RESPONSIBILITIES.md), [Phase 1 guide](PHASE_1_TEAM_GUIDE.md) and [Git workflow](KNEXUS_Team_Git_Workflow_Guide.md) use persistent branches `dev-hassan`, `dev-naveed` and `dev-zaid` respectively. Hassan owns backend/API, schema/migrations, data/runtime, security and integration; Naveed owns LLM/prompt/citation, typed tool handlers and answer evaluation; Zaid owns the entire frontend from Phase 1 onward. Each member pushes their own branch and opens a merge-commit PR to `main`.

All application source/configuration files were reread; they contain no member-specific runtime ownership or frontend implementation to change. Member summaries, Phase 1 tasks, Git and contribution guides, frontend/data READMEs, core design notes and the index now follow the same ownership map. External papers, institutional templates and the archived startup blueprint are references rather than current delivery contracts. Planning changes do not implement features or resolve the code findings above. Documentation checks cover member/branch/owner consistency, source syntax, relative links, JSON examples and patch formatting.

## Phase 1 readiness audit - 19 October 2026

**Verdict:** ready to begin Phase 1 foundation work. Complete the publishing, personal-branch/setup and contract handoff steps in [PHASE_1_TEAM_GUIDE.md](PHASE_1_TEAM_GUIDE.md) before expecting independent workstreams to integrate. This is not a claim that the Phase 1 product is implemented or that all environments are ready.

| Area | Audit evidence / status |
|---|---|
| Documentation | All current source/document paths inventoried, including the two new team guides. Relative links, JSON examples, source syntax and patch whitespace pass; member/branch/owner mappings agree. |
| Shared Python environment | Python 3.12.3; `pip check` reports no broken requirements. A fresh installation on each laptop is still unverified; requirements remain lower bounds without a lockfile. |
| Compose/database | Compose config validates; existing PostgreSQL container is healthy. Live read-only probes confirm database connectivity and vector extension 0.8.7. No public application tables exist yet, matching the absence of migrations/models. |
| Backend | Lifespan startup/shutdown and root, Swagger, ReDoc and OpenAPI probes pass. Application paths are exactly `/` and `/api/v1/health`; proposed upload/query routes return 404. The default localhost:5173 CORS preflight passes. |
| Health limitations | Live health returns HTTP 200 / aggregate healthy while Ollama is offline. The earlier readiness/error-handling findings remain tracked implementation work. |
| Ollama | Not found in the remote shell; service probe offline. Install/run it on the chosen inference host and load the model before live generation. Fake-provider/prompt work can start now. |
| Frontend | Remote Node v20.20.2 and npm 10.8.2 are available, but no frontend manifest/source/build exists yet. The scaffold task must select compatible package/runtime versions on Zaid's machine. |
| Git handoff | Latest documentation edits remain uncommitted; the two team guides are untracked. The local branch inventory has `main` only. Publish the baseline and have members create/push their own branches; GitHub write access/protection settings were not verified. |
| Contracts | API and schema are draft designs. Review the first contract PR before live frontend/generator integration; mock/stub work can proceed against agreed examples. |
| Academic materials | Base-paper eligibility, literature-survey coverage and blank abstract fields remain documented submission issues. They do not block initial software implementation. |

This audit did not install packages/models, start/stop services, change database state or run nonexistent frontend/RAG test suites. It corrected environment-copy examples to preserve existing `.env` files and replaced an in-place frontend scaffold instruction that could conflict with the existing README.

## Coordination handoff follow-up - 19 October 2026

The preceding readiness table is an audit snapshot. The documentation baseline has since been committed/published as `1a258e6`, and dev-hassan/dev-naveed/dev-zaid now exist locally and on origin with tracking. The shared checkout is on dev-hassan. Naveed/MrMax3757 already has write access; Zaid/MohammedZaid1946 has an existing pending write invitation. No invitations were sent during this handoff. Merge commits are enabled; protection/ruleset API inspection returned 403 and is not represented as verified.

The [draft implementation baseline](PHASE_1_CONTRACT.md) now has standalone Pydantic contract references, a generated JSON Schema, synthetic HTTP/generation fixtures and positive/negative validation checks. This is concrete material for the team's contract PR, not already-approved or implemented endpoints, migrations or frontend code. No additional runtime dependency was installed.

The shared server has an i3-7100U, about 8 GB RAM, Intel HD 620 graphics and about 13 GB free disk. Naveed confirmed his computer is substantially stronger; it is selected for Ollama. Only the ignored root environment's Ollama URL/model fields were changed to use localhost:11435 and llama3.2:3b. Naveed must run Ollama and the loopback-only reverse SSH tunnel before live generation can be verified. [TEAM_START.md](TEAM_START.md) gives the exact commands and pending personal-machine steps. No models were downloaded and no service or database changes were made.

## Developer-agent playbook follow-up

PR #1 is merged, and origin/main contains the shared contract baseline at `cb0c20b`. The [Phase 1 guide](PHASE_1_TEAM_GUIDE.md) is now the agent execution brief: role/branch checks, read order, H01-H07 backend tasks, N01-N06 generation tasks, Z01-Z06 frontend tasks, owned paths, dependency gates, verification requirements and copyable agent prompts. The local member-branch upstreams were found pointing at origin/main and restored to their matching origin/dev-* branches; each personal clone must inspect its own tracking configuration. Naveed still has write access and Zaid still has no active write access at this follow-up; his previously observed invitation needs acceptance. No Phase 1 feature implementation is claimed by this documentation change.

## Recommended implementation order

1. Fix health/readiness/error handling, configuration consistency, and dependency reproducibility; establish basic test/CI coverage.
2. Implement identity, tenant ownership constraints, least-privilege database access, and negative authorization tests alongside initial ingestion.
3. Deliver one PDF/DOCX ingestion -> indexed chunks -> authorized retrieval -> cited answer/abstention path, with a small labeled corpus.
4. Add one sandbox action with atomic single-use approval, idempotent execution, verification, and audit records.
5. Build the UI against generated contracts, expand held-out evaluation, and update academic artifacts with measured results and verified submission details.

## Phase 0 publication readiness follow-up - 19 October 2026

The shared dependency environment, Compose configuration and standalone contract checker pass. PostgreSQL is running healthy. The server inference tunnel on 127.0.0.1:11435 is offline, personal laptop environments are unverified, and Zaid's write-access invitation remains pending. These observations permit independent scaffold/fixture work after each member completes access and branch setup; they do not establish live integration readiness.

[PHASE_0_SETUP_GUIDE.md](PHASE_0_SETUP_GUIDE.md) records per-owner setup commands, safe clone/branch synchronization, current versus future checks, SSH access prerequisites, the Ollama generation gate and handoff evidence. It accompanies the Phase 1 agent playbook in PR #2. No application features are implemented by this documentation change.
