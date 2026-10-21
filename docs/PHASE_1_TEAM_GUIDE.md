# Phase 1 developer-agent playbook

This is the execution brief for the three KNEXUS developers and their coding agents. Read the common rules, then work through the section for your assigned member. Inspect the actual files before coding: a planned directory or an unchecked task below does not prove what exists today.

See [current status and next actions](PROJECT_STATUS.md) before starting; it records verified progress, pending setup and the current shared-server API port.

**Phase 1 outcome:** upload a small synthetic PDF/DOCX, store its text/chunks/embeddings, retrieve permitted evidence for a question, generate a cited answer or abstain, and show the result through the frontend.

Before starting, complete the access/branch/environment checks in [PHASE_0_SETUP_GUIDE.md](PHASE_0_SETUP_GUIDE.md). Model connectivity is required for live integration; independent fixture/fake-provider work can begin after the common setup gates.

## 1. Identify your role and read the baseline

| Member | Name | Required branch | Primary scope |
|---|---|---|---|
| 1 | Hassan | `dev-hassan` | Backend/API, database/migrations, ingestion/embeddings/retrieval, data/runtime and integration |
| 2 | Naveed | `dev-naveed` | Prompt/context, generation/result validation, Ollama adapter and answer evaluation |
| 3 | Zaid | `dev-zaid` | Entire frontend, typed API mocks/client, upload/chat/citations, UI states and verification |

Read these in order:

1. The user's instructions and any applicable `AGENTS.md` files. For the shared workspace used here, workspace commands run over SSH to `hassan@192.168.1.92`; local commands are only for managing that connection. A member's own clone follows its actual environment instructions.
2. [TEAM_RESPONSIBILITIES.md](TEAM_RESPONSIBILITIES.md) for ownership and [TEAM_START.md](TEAM_START.md) for access, branches and the laptop-hosted Ollama connection.
3. [PHASE_1_CONTRACT.md](PHASE_1_CONTRACT.md) for the initial implementation baseline.
4. [Reference types](../contracts/phase1/models.py), [fixture manifest](../contracts/phase1/examples/manifest.json), [schema](../contracts/phase1/schema.json) and [contract checker](../contracts/phase1/README.md).
5. [CONTRIBUTING.md](../CONTRIBUTING.md), the existing application code and the files relevant to your first task.

PR #1 is merged and the contract reference is available on main at `cb0c20b`. Member branches must synchronize from current main before implementing against it. The broader API/database designs and archived OpsPilot blueprint include later features; the Phase 1 contract narrows the first slice. Later contract changes require a reviewed update, not independent field renaming by each agent.

At this playbook's update, the application still exposes only root and health routes. There are no application models/migrations, ingestion/query routes, generator or frontend application. The files under `contracts/phase1/` are reference types/examples/checks, not implemented features. Recheck this snapshot when starting a task.

## 2. Common operating rules

- Use your own clone/working directory. Do not switch a directory another member or agent is using.
- Confirm the assigned branch and upstream before editing. Each member branch tracks its same-named `origin/dev-*` branch, not `origin/main`.
- Preserve existing work. If the tree is dirty or the branch is wrong, inspect and coordinate rather than resetting files, force-switching or force-pushing.
- Work in small task slices. Read first, state the intended change, implement, run relevant checks, then report evidence and the next handoff.
- Keep shared contract changes in one coordinated PR. The owner is Hassan; Naveed and Zaid review consumer effects. The generated schema does not express all Python semantic validators.
- Do not claim a fixture is live data, a fake provider is Ollama, a role badge is authorization or a valid citation ID proves claim support.
- Use local synthetic data until the authentication/authorization gate is satisfied. Never trust client-supplied actor, organization or role identity.
- No Phase 1 expansion into streaming, approval/admin screens, external connectors, a workflow engine, model training or production deployment. Those need separate scope/contract review.
- Respect the user's authorization for commits, pushes and PRs. Do not merge a PR or send messages/reviewer notifications without authorization.

From the repository root, inspect Git before every work session:

```bash
git status --short --branch
git branch --show-current
git branch -vv
```

On your assigned branch and with a clean tree, synchronize merged work:

```bash
git fetch origin
git merge --no-edit origin/main
```

Run the contract baseline check after setting up the backend environment:

```bash
backend/venv/bin/python contracts/phase1/check.py
```

PowerShell equivalent:

```powershell
./backend/venv/Scripts/python.exe contracts/phase1/check.py
```

Do not regenerate schema.json merely to hide a failing check. Review the model/schema diff and fix the real mismatch. Do not execute these commands against another member's working directory.

## 3. Shared interfaces and file boundaries

| Owner | Own these areas | Coordinate rather than independently changing |
|---|---|---|
| Hassan | `backend/app/api/`, `core/`, `models/`, `schemas/`, ingestion/retrieval services, migrations, backend/API tests, dataset importer/provenance, Docker/configuration and integration docs | Generation implementation owned by Naveed; frontend implementation owned by Zaid |
| Naveed | `backend/app/services/generation/`, its prompt/provider/result modules, generation-focused tests and answer-quality cases | Routes, database models, migrations, shared settings/dependencies and public response fields |
| Zaid | Entire `frontend/`, frontend dependencies/build configuration, API types/client/mocks, components/pages/styles and UI tests | Backend routes, database/runtime configuration, generator modules and shared contract definitions |

The service paths above are proposed until created. Use them consistently rather than creating competing `rag/`, `llm/` and `chains/` trees for the same responsibility.

Hassan and Naveed must agree the public generation callable/import path before connecting it. Its input is GenerationRequest and its output is GenerationResult; it is async, receives already-authorized evidence and performs no database reads or tool execution. Hassan can use a clearly injected fake implementation while Naveed builds the real adapter. Preserve the agreed input/output shapes regardless of internal class design.

Hassan and Zaid agree HTTP paths/fields from the contract. Frontend mocks come from the shared examples. Keep the fixture source/revision documented; do not silently invent camelCase wire fields or duplicate contracts that drift. A live-mode failure must not silently fall back to mock success.

## 4. Hassan / Member 1 / dev-hassan

Work through H01-H07 in order. Generation and frontend integration can use explicit fakes/mocks until the respective owners hand off live implementations.

### H01 - Runtime schema and service boundaries

- [ ] Inspect the accepted reference models, existing Settings/database/session code and planned API/error behavior.
- [ ] Establish one reviewed runtime schema import boundary for requests, documents, evidence, generation results and errors. If canonical definitions move into the application, update the reference checker/export/imports in the same coordinated change; do not maintain unchecked copies.
- [ ] Agree the generation callable/import boundary with Naveed and wire an injected fake for backend tests.
- [ ] Define a server-owned synthetic demo actor and effective-role expansion. Reject actor/tenant/role fields in public requests. Clearly identify this as demo identity, not JWT authentication.
- [ ] Establish test import/configuration and a disposable database strategy. Keep shared settings/dependency changes in this owner's PR.

**Done when:** the contract checker passes, schema validation has meaningful negative cases, generation can be substituted without a model service, and the other two agents know the stable import/HTTP fields.

### H02 - Database models and migrations

- [ ] Implement organizations/users for the demo actor, documents, chunks, embeddings and ingestion_jobs as specified in the Phase 1 contract.
- [ ] Use UUIDs, tenant-consistent parent/child constraints, unique chunk positions, the 384-dimensional vector type and a compatible cosine index.
- [ ] Configure Alembic to read the root environment and application metadata. Create the initial reviewed revision; extension bootstrap alone is not a migration.
- [ ] Persist upload task IDs and queued/processing/complete/failed lifecycle with safe failure fields and timestamps.
- [ ] Add storage/seed helpers using small synthetic records and stable source IDs.
- [ ] Verify fresh migration/seed behavior and migration round trips only on a disposable database. Never downgrade, drop or reset the shared knexus database for a test.

**Done when:** a clean test database can be created from migrations, storage can round-trip a synthetic document/chunk/vector/job, and cross-tenant parent references are rejected.

### H03 - Upload, parsing and chunking

- [ ] Implement one-file PDF/DOCX validation, the 10 MiB limit and repeated multipart allowed_roles fields. Do not use an uploaded filename as an unchecked filesystem path.
- [ ] Store original files in an explicitly ignored/private development location. Do not commit uploads, full corpora, model caches or secrets.
- [ ] Extract text and page/section metadata. Reject obvious bad requests before acceptance; parsing failures after 202 must update the job/status to failed.
- [ ] Split using the embedding tokenizer, starting at 240 tokens with 32 overlap and respecting the actual model limit including special tokens.
- [ ] Run blocking parsing/embedding work outside the async request event loop. Persist job state; mark interrupted attempts explicitly instead of promising a durable queue.

**Done when:** valid small PDF/DOCX files produce ordered chunks, oversized/unsupported inputs are handled correctly, empty/corrupt content has a visible safe failure, and source/page metadata survives.

### H04 - Embeddings and indexing

- [ ] Integrate all-MiniLM-L6-v2 at 384 dimensions, loading/reusing it deliberately rather than downloading/loading it per request.
- [ ] Keep tests deterministic with a fake embedder; real model downloads are a separate integration check.
- [ ] Persist chunk/vector/model metadata consistently and define the duplicate/retry policy before relying on it.
- [ ] Mark documents complete only after successful indexing. Exclude partial/failed documents from retrieval and keep retries from creating inconsistent active vectors.

**Done when:** a completed document has the expected chunks/vectors and model metadata, indexing failure does not expose a partial document, and a retry follows the documented policy.

### H05 - Authorized retrieval and abstention

- [ ] Embed the question with the same embedding model and retrieve top_k within the agreed 1-20 range.
- [ ] Apply organization, effective-role, current parent-document permission, complete-state and deletion filters before evidence reaches generation.
- [ ] Return ranked unique EvidenceChunk objects with query-scoped citation IDs and stable document/chunk UUIDs.
- [ ] Handle absent/weak evidence with a valid public abstention before a provider call. Treat the initial similarity cutoff as a development setting to calibrate.
- [ ] Test a highly similar restricted document and a same-role document from another tenant; neither may appear in evidence or citations.

**Done when:** known evidence is retrieved and forbidden/failed/deleted evidence never reaches the generator, including when it is the closest vector match.

### H06 - API orchestration and failure behavior

- [ ] Implement upload, document list/detail/status and non-streaming query routes with the accepted schema, status codes and safe errors.
- [ ] Return 202 only after document/job persistence, and make status polling reflect real lifecycle transitions.
- [ ] Connect the agreed generator boundary. Validate its result against the supplied evidence and construct public citation metadata from backend retrieval objects.
- [ ] Keep no-evidence abstention distinct from provider failure, timeout and invalid citations. Do not return fabricated success when a dependency is unavailable.
- [ ] Keep session_id as Phase 1 correlation only; do not imply conversation history or streaming is implemented.
- [ ] Verify the intended UI origin/CORS behavior and record known health/readiness limitations. Fix directly related startup/error-handling defects in a focused change.

**Done when:** route-level checks cover successful upload/query, validation, permission denial, status failure, abstention, provider failure and invalid citations with a fake provider. Generated OpenAPI reflects only implemented routes.

### H07 - Integrated demo and reproducibility

- [ ] Add a tiny reproducible synthetic corpus and labeled question/source manifest before expanding corpus size.
- [ ] Integrate Naveed's live generator and Zaid's frontend after their handoffs. Reuse the selected laptop/server connection in TEAM_START.md.
- [ ] Verify upload -> status -> retrieval -> cited answer/abstention from the browser, not only service calls.
- [ ] Document exact setup/migration/seed/run commands, environment differences, observed results and known failures.
- [ ] Keep a held-out question subset and record versions/settings. Do not claim full-benchmark results from a partial corpus.

**Hassan's phase handoff:** working backend endpoints and migrations, stable source IDs, filtered evidence, integration-check output and a fresh-setup demo procedure.

## 5. Naveed / Member 2 / dev-naveed

Work through N01-N06. Start without a database, frontend or real LLM by using the generation fixtures and a fake provider.

### N01 - Generation boundary and fake provider

- [ ] Read GenerationRequest, GenerationResult, the supplied examples and validate_generation_result.
- [ ] Agree the async callable/import interface with Hassan before either side codes a caller around a different design.
- [ ] Create provider-independent generation modules in `backend/app/services/generation/` with a fake provider and generation-focused tests.
- [ ] Keep database access, tenant selection, HTTP routes and actor authorization outside these modules.

**Done when:** Hassan can call the fake generator through the same boundary the real provider will use, and fixture inputs/outputs pass without Ollama.

### N02 - Prompt and bounded context

- [ ] Version the baseline prompt and provider parameters separately.
- [ ] Build context from already-authorized evidence objects, preserving citation IDs and source boundaries. Treat document instructions as untrusted text.
- [ ] Require answer/cited_ids/abstained/reason behavior matching the reference. Never ask the model to invent source metadata or access decisions.
- [ ] Define and document context/output token budgets for the selected model, preserving room for instructions and output.
- [ ] Test supported, conflicting, irrelevant, long and adversarial evidence. Empty retrieval is Hassan's pre-provider abstention path; do not bypass the request model's minimum evidence rule.

**Done when:** prompt assembly is deterministic for fixtures, evidence IDs are preserved, and oversized contexts are handled according to a tested policy.

### N03 - Ollama adapter on Naveed's computer

- [ ] Follow TEAM_START.md to install/run Ollama, load llama3.2:3b and connect the reverse SSH tunnel. Do not install the model on the shared low-memory server by default.
- [ ] Implement an injected/configurable async HTTP adapter with explicit timeout/output bounds and bounded retries, if retries are used.
- [ ] Parse model output as data through strict validation; never use eval or execute generated code/actions.
- [ ] Make offline/overloaded/timeout/malformed-output outcomes distinguishable for Hassan's HTTP mapping.
- [ ] Keep private prompts/document text out of ordinary logs; record safe model/version/request diagnostics.

**Done when:** fixture-driven adapter checks pass without the daemon, and a separately recorded live request succeeds using the exact configured model/URL.

### N04 - Citation and result validation

- [ ] Enforce answer/abstention invariants, inline-marker consistency and cited-ID membership in the supplied evidence using the shared validator.
- [ ] Return typed results/typed failures to the backend rather than HTTP responses or invented document titles/excerpts.
- [ ] Reject unknown IDs, missing citations, conflicting answer/abstention fields and malformed provider output. Do not disguise these failures as missing evidence.
- [ ] Evaluate whether cited passages support claims; structural ID validation alone does not establish factual support.

**Done when:** negative cases reject invented/invalid citations and Hassan receives a result or a clearly mapped failure, never silent fabricated success.

### N05 - Answer-quality cases and experiments

- [ ] Supply labels/source IDs for a small shared development set; keep held-out examples out of prompt tuning.
- [ ] Compare one changed factor at a time and record exact model tag/digest, prompt version, parameters, evidence IDs, observed output and latency.
- [ ] Record correct answers, abstentions, false abstentions, unsupported claims and representative failures. Do not copy illustrative fixture timings as measurements.
- [ ] Coordinate corpus/source provenance with Hassan and citation/abstention presentation with Zaid.

**Done when:** the team can reproduce the baseline experiment and inspect actual failure examples with traceable source IDs.

### N06 - Backend handoff

- [ ] Demonstrate a live answer and valid abstention through Hassan's integration; use fakes to verify provider-error behavior safely.
- [ ] Confirm the shared server can reach the laptop only while the authorized tunnel/service is active, and that disconnection becomes an explicit unavailable state.
- [ ] Document how to start/stop the local service/tunnel, identify the loaded model and rerun generation-focused checks.

**Naveed's phase handoff:** stable async generation interface, versioned prompt, tested result validation, configured adapter, reproducible answer cases and live-connection evidence.

## 6. Zaid / Member 3 / dev-zaid

Work through Z01-Z06. Begin with frontend-owned mocks copied/generated from the shared fixtures; do not wait for all backend routes to exist.

### Z01 - Frontend foundation

- [ ] Inspect frontend/README.md before running a generator. Generate in an empty temporary directory and bring the scaffold into frontend without deleting the existing README.
- [ ] Use the agreed React/TypeScript/Vite stack, a small component structure and consistent design tokens/styles. Avoid unrelated libraries or a new product architecture.
- [ ] Record the selected Node requirement, commit package.json and its lockfile, and document install/dev/build/typecheck/test scripts.
- [ ] Keep node_modules, build output and local environment files out of Git. Browser-exposed VITE_* variables must contain no secrets.

**Done when:** another member can install from the lockfile and start/build the frontend using documented commands.

### Z02 - Typed API client and mocks

- [ ] Derive or check frontend request/response types against the approved schema and fixture examples, including null fields and every processing state.
- [ ] Implement one API client boundary with configurable API base URL. Send only allowed request fields; never send a forged actor/tenant identity.
- [ ] Keep mock/live mode explicit and visible during development. Preserve fixture source/revision when generating local mock data.
- [ ] Add error parsing for accepted public error fields. No silent fallback to mock answers in live mode.
- [ ] Consume the backend API only; do not call Ollama directly from the browser.

**Done when:** upload/document/status/query/error fixture responses drive the UI with consistent types and clear mock labeling.

### Z03 - Upload and document status

- [ ] Build file selection/upload with helpful client-side file/size guidance; backend validation remains authoritative.
- [ ] Submit FormData with one file and repeated allowed_roles fields as agreed. Do not JSON-encode the multipart role array differently from the contract.
- [ ] Show document list/detail and queued/processing/complete/failed states, including safe failure messages.
- [ ] Poll status with bounded intervals/retries; stop on completion/failure and cancel work when the view unmounts.
- [ ] Provide loading/empty/error/retry states without repeatedly creating duplicate uploads in an automatic retry loop.

**Done when:** all upload/status fixture states are usable and a real accepted upload can later replace the mock without changing field names.

### Z04 - Chat, citations and abstention

- [ ] Submit question/top_k/stream=false through the typed client.
- [ ] Render the answer and returned citation cards with document title, excerpt and available page/chunk metadata. Use returned IDs; do not invent source paths or citations.
- [ ] Keep content rendering safe as text/approved components rather than unsanitized HTML.
- [ ] Give abstention its own clear state. Provider errors/timeouts/invalid results must appear as errors, not pretend answers or evidence abstentions.
- [ ] Cover keyboard use, focus, readable error/status announcements and basic responsive behavior.

**Done when:** answered, abstained and failed fixtures produce distinct accessible states and citation details match the response.

### Z05 - Live API integration

- [ ] Agree the API URL with Hassan and change only the client configuration when switching from mocks.
- [ ] For a localhost-only API on the shared server, use an authorized SSH local-forward from Zaid's machine instead of exposing the API publicly. See the connection example below.
- [ ] Confirm browser requests reach the real API and upload/status/query/citation behavior works without mock fallback.
- [ ] Surface contract mismatches in a coordinated PR; do not patch backend routes or silently rename fields in the client.

For the current shared-server setup, start KNEXUS on server localhost:8002 as described in PROJECT_STATUS.md. This tunnel runs on Zaid's computer while he uses that API:

```powershell
ssh -N -o ExitOnForwardFailure=yes -L 127.0.0.1:8000:127.0.0.1:8002 hassan@192.168.1.92
```

An authorized SSH account/key is required. With the tunnel active, the frontend's API base URL can be `http://127.0.0.1:8000/api/v1`. If local port 8000 is occupied, coordinate another local port and update the client URL. This API tunnel is separate from Naveed's reverse Ollama tunnel.

**Done when:** live upload and chat work from the browser, and a disconnected backend produces a visible error rather than a fixture response.

### Z06 - UI verification and handoff

- [ ] Add meaningful component/state checks for upload failure, processing completion, cited answer, abstention and provider failure.
- [ ] Run the documented typecheck, test and production-build scripts after they exist; fix actual failures.
- [ ] Review small/large-screen layout and keyboard operation. Capture synthetic demo screenshots if useful.
- [ ] Update frontend/README.md with actual commands, environment variables, mock/live switching and known gaps.

**Zaid's phase handoff:** reproducible frontend build, typed client/mocks, usable upload/chat/citation states, live API evidence and UI-check output. Login, admin and approval screens remain later-phase work.

## 7. Integration order and dependencies

| Milestone | Hassan | Naveed | Zaid | Gate to continue |
|---|---|---|---|---|
| Baseline | H01 and H02 | N01 and N02 with fake provider | Z01 and Z02 with mocks | Same contracts, working foundation and explicit fakes |
| Document path | H03 and H04 | N03 and N04 | Z03 and Z04 | Upload/index lifecycle plus structurally valid answer/UI states |
| Retrieval/answer | H05 and H06 | N05; live provider handoff | Z05 | Permitted evidence -> validated answer/abstention -> browser |
| Phase close | H07 | N06 | Z06 | Reproducible end-to-end demo and recorded checks |

If a dependency is missing, continue an independent task using an explicit fake/mock. Report the blocked task ID, required owner/input and contract question. Do not implement the other member's entire module or invent an undocumented interface to appear unblocked.

## 8. Checks to run and what they prove

The shared contract check works now and needs no services. It checks reference payloads/invariants, not product functionality:

```bash
backend/venv/bin/python contracts/phase1/check.py
```

Backend tests should be added under separate owned scopes, for example backend/tests/phase1/backend and backend/tests/phase1/generation. After those files exist, run the relevant scope from the root. A POSIX example is:

```bash
PYTHONPATH=backend backend/venv/bin/python -m pytest backend/tests/phase1 -q
```

PowerShell:

```powershell
$env:PYTHONPATH = "backend"
./backend/venv/Scripts/python.exe -m pytest backend/tests/phase1 -q
```

Do not run a nonexistent test path and report success. Database checks use a separately configured disposable database; fake-provider unit checks must not require a model download or live Ollama. Keep live-service checks separately identified.

After Z01 adds the corresponding scripts and lockfile, frontend checks can be:

```bash
npm --prefix frontend ci
npm --prefix frontend run typecheck
npm --prefix frontend run test
npm --prefix frontend run build
```

Use the scripts actually committed in package.json. Record which checks ran, their outcomes and what remains unverified. Passing mocks cannot replace the final live browser/backend/generator check.

## 9. Phase 1 completion checklist

- [ ] Fresh setup can create the application schema, seed a small synthetic corpus and start the required processes using documented commands.
- [ ] PDF/DOCX upload and every job state are real and visible; bad/oversized/empty content fails safely.
- [ ] Stored chunks/vectors have stable IDs, source metadata and consistent model dimensions.
- [ ] Tenant/role/deletion/status filtering is proven with negative cases before evidence reaches generation.
- [ ] A supported question produces an answer with valid, traceable citations; missing evidence produces a valid abstention.
- [ ] Offline/timeout/invalid-output cases produce explicit errors without fabricated success.
- [ ] The frontend completes the real upload -> status -> question -> citation/abstention flow and handles errors accessibly.
- [ ] Contract checks and the relevant backend/generation/UI checks pass; actual integration evidence and known limitations are recorded.
- [ ] Each member's work is reviewed and merged with merge commits; setup/docs match the final implementation.

Do not mark Phase 1 complete merely because all branches have commits, the mock UI looks finished or the health endpoint says healthy.

## 10. Copyable prompts for each member's agent

### Hassan's agent

```text
You are working on KNEXUS as Hassan / Member 1, branch dev-hassan.
Read docs/PHASE_1_TEAM_GUIDE.md, docs/TEAM_RESPONSIBILITIES.md and the merged Phase 1 contract/reference files. Follow applicable user/AGENTS/environment instructions.
Inspect Git state and existing implementation first. Work through H01-H07 in dependency order, beginning with the first incomplete task. Start with a reviewable schema/storage foundation; do not implement the whole phase as one unreviewed patch.
Own backend/API, schema/migrations, ingestion/embedding/retrieval, data/runtime and integration. Coordinate the generation interface with Naveed and HTTP consumer fields with Zaid. Preserve their ownership.
Use disposable DB tests and explicit fake providers where appropriate. Never accept client actor/tenant identity or claim the synthetic demo actor is authentication.
For each completed task report changed files, actual check commands/results, handoff requirements and the next task ID. Follow the authorized commit/push/PR workflow; do not merge PRs automatically.
```

### Naveed's agent

```text
You are working on KNEXUS as Naveed / Member 2, branch dev-naveed.
Read docs/PHASE_1_TEAM_GUIDE.md, docs/TEAM_RESPONSIBILITIES.md, docs/TEAM_START.md and the merged Phase 1 contract/reference files. Follow applicable user/AGENTS/environment instructions.
Inspect Git state and existing implementation first. Work through N01-N06 in order, beginning with fake-provider prompt/result handling against the supplied generation fixtures.
Own generation/prompt/context/citation validation, the Ollama adapter and answer-quality cases. Do not edit backend routes, database/migrations or frontend code independently.
Ollama runs on Naveed's computer; use the documented authorized tunnel for shared-server integration. Keep provider failures distinct from missing evidence and validate source-ID membership/inline markers without claiming this proves factual support.
For each completed task report changed files, actual checks, fake versus live evidence, handoff requirements and the next task ID. Follow the authorized Git workflow; do not merge PRs automatically.
```

### Zaid's agent

```text
You are working on KNEXUS as Zaid / Member 3, branch dev-zaid.
Read docs/PHASE_1_TEAM_GUIDE.md, docs/TEAM_RESPONSIBILITIES.md, frontend/README.md and the merged Phase 1 contract/reference examples. Follow applicable user/AGENTS/environment instructions.
Inspect Git state and existing implementation first. Work through Z01-Z06 in order. Preserve the existing frontend README when scaffolding. Begin with a minimal React/TypeScript/Vite app, typed API boundary and clearly labeled fixtures.
Own the entire frontend. Build upload/status/document and chat/citation/abstention/error states, then integrate Hassan's accepted APIs. Do not call Ollama from the browser or independently change backend/schema contracts.
Keep mock/live modes explicit, avoid silent fixture fallback and render returned content safely. Defer login/admin/approval UI to its later-phase scope.
For each completed task report changed files, actual typecheck/test/build and UI observations, mock versus live evidence, handoff requirements and the next task ID. Follow the authorized Git workflow; do not merge PRs automatically.
```

## 11. End-of-task report template

```text
Role / branch:
Task IDs completed:
Current behavior delivered:
Files changed:
Contract fields or imports affected:
Checks actually run and results:
Mock/fake evidence versus live integration evidence:
Known gaps or blockers and the required owner/input:
Next task ID:
Commit/PR status, if authorized:
```

Keep task completion evidence in the PR or a short task note; do not invent checked boxes, measured scores or live-service success. For prompting experiments, version the prompt/model/settings and keep held-out questions separate from development tuning.
