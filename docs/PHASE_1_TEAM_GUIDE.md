# Phase 1 developer and agent playbook

**Outcome:** one synthetic PDF/DOCX travels through upload, persisted processing, parsing/chunking/embedding, permitted retrieval, cited answer or abstention, and frontend display.

Read [status](PROJECT_STATUS.md) for completion, [CONTRIBUTING](../CONTRIBUTING.md) for setup/branches and [ownership](TEAM_RESPONSIBILITIES.md) before selecting work. [Canonical contracts](PHASE_1_CONTRACT.md) and [models](../contracts/phase1/models.py) define interfaces.

## Common rules

- Follow current user instructions and AGENTS.md. Hassan's server workspace uses SSH.
- Inspect branch, revision, tracking and all pending files first. Agree a published baseline; preserve existing work and other checkouts.
- Do not reset, force-switch, clean or force-push. Work in small owned slices and coordinate shared interfaces/settings/dependencies.
- Use synthetic data and server-owned demo identity. Never trust caller actor/organization/role.
- Keep fake/mock and live evidence explicit. Valid citation IDs do not prove factual support; tenant foreign keys do not implement retrieval authorization.
- Commits, pushes, PRs, merges, installation, services and database access require user authorization covering that action.
- Streaming, authentication, governed actions and broader platform modules are beyond the first RAG slice.

Do not restart implemented H01/H02 or N01 because an old member branch lacks them. Reuse the reviewed baseline; finish remaining behavior and live/integration evidence.

## Hassan: H01-H07

| Task | Behavior and completion gate |
|---|---|
| H01 - Boundary | Implemented: `app.schemas` re-exports canonical types, `build_demo_actor()` is synthetic and `run_generation` validates an injected async result. Preserve these interfaces. |
| H02 - Persistence | Implemented and merged in PR #4: six tables, tenant ownership, lifecycle constraints, UUIDs, 384-dimensional vectors, Alembic and explicit seed helper. Offline/disposable checks passed; shared DB is unmigrated. |
| H03 - Upload/parse/chunk | Validate one PDF/DOCX up to 10 MiB and repeated multipart roles. Commit document/job before 202. Use private ignored storage and safe keys. Preserve page/source metadata. Count embedding-tokenizer tokens with the initial 240/32-overlap policy and actual special-token limits. Move blocking work off the event loop; persist safe failures/interruptions. Background tasks are not a durable queue. |
| H04 - Embed/index | Reuse all-MiniLM-L6-v2 at 384 dimensions, deterministic fake embeddings offline, explicit model/revision and duplicate/retry policy. Mark complete only after indexing succeeds; exclude partial failures. |
| H05 - Authorized retrieval | Apply organization, effective roles, current parent permissions, active embedding model, completion and deletion filters before generation. Use stable source UUIDs and query-scoped citation IDs. Empty/weak evidence abstains before inference. Prove restricted nearest neighbors and other tenants do not leak. |
| H06 - API | Implement canonical document/query routes and safe errors. Build public citations from backend metadata; keep provider failure distinct from abstention. Verify CORS, polling and OpenAPI using fakes. Correlation IDs do not imply chat history. |
| H07 - Integration | Tiny corpus/labels, Naveed's live adapter and Zaid's UI. Verify real browser upload -> status -> retrieval -> citations/abstention, permissions/failures and fresh-setup procedure. Record versions and gaps. |

Hassan's next task is H03. New database runs and shared migration require separate approval for the exact target.

## Naveed: N01-N06

| Task | Behavior and completion gate |
|---|---|
| N01 - Service | Baseline async fake/Ollama service is implemented and H01-compatible. Verify concrete injection and canonical types; never restore old heuristics. No DB reads, identity selection, routes or tools in generation. |
| N02 - Prompt/context | Preserve all authorized evidence and source IDs. Treat document instructions as untrusted. Version prompt/settings; test relevant conflict, irrelevant/adversarial content and oversized input without fixture-specific rules or request mutation. The character ceiling is not token counting; real context fit remains unresolved. |
| N03 - Adapter | Preserve explicit selection, propagated URL/model/limits, strict parsing, network/overall deadlines and cancellation. Offline HTTP coverage exists; record a bounded live laptop run separately. |
| N04 - Result | Preserve answer/abstention, inline-marker and evidence-membership validation. Keep malformed output as typed failure. Evaluate factual support separately; never drop invalid citations or disguise errors as abstention. |
| N05 - Evaluation | Labeled development/held-out cases. Record tag/digest, prompt hash/version, parameters, evidence, raw output and measured latency. Report failures, unsupported claims and false abstentions; no tuning against held-out cases. |
| N06 - Handoff | Give Hassan exact imports, construction/configuration, typed errors and H01 injection. Verify live answer/abstention through the integrated API after it exists and explicit unavailable state after approved disconnection. Document actual service/tunnel procedure. |

See [generation](../backend/app/services/generation/README.md) and [evaluation](EVALUATION_STRATEGY.md). Local evaluation can proceed now; endpoint/browser evidence depends on Hassan/Zaid. Do not create another query route.

## Zaid: Z01-Z06

| Task | Behavior and completion gate |
|---|---|
| Z01 - Scaffold | Confirm React/TypeScript framework first; neither Vite nor Next.js is committed. Generate outside the existing directory, preserve files, add compatible versions/lockfile and real scripts. |
| Z02 - Client/mocks | Canonical examples/schema including nullable fields and all states. One configurable API boundary; visible mock/live mode. No authoritative caller identity, silent renaming or fixture fallback after a live error. |
| Z03 - Upload/status | One file and repeated roles, document/status views, safe failure messages and bounded polling stopped on terminal state/unmount. Avoid duplicate uploads on retry; backend validation is authoritative. |
| Z04 - Chat | Send `stream=false`. Safely render answer/citations with real IDs/metadata, separate abstention/errors, keyboard/focus/responsive states and readable announcements. |
| Z05 - Live API | Agree URL with Hassan; authorized tunnel if needed. Real browser flow without mock fallback. Report mismatches rather than editing backend contracts independently. |
| Z06 - Handoff | Run actual typecheck/test/build scripts and meaningful UI checks. Review keyboard/mobile/desktop behavior; document real setup and gaps. |

Login/admin/approval UI and streaming are later-phase work. See [frontend](../frontend/README.md).

## Integration order

1. Agreed H01/H02 and generation foundation; Zaid develops typed mocks in parallel.
2. H03/H04, Naveed's live prompt/adapter evaluation, Zaid's upload/chat states.
3. H05/H06 consumes the concrete service; Zaid connects the API.
4. H07/N06/Z06 record the full browser flow and failure/permission evidence.

For blocked work, identify task, owner and exact missing input. Continue independent work with explicit fakes instead of implementing another owner's module.

## Completion gate

Use actual check commands in [CONTRIBUTING](../CONTRIBUTING.md) and [backend tests](../backend/tests/README.md); canonical checking is separate. Do not invent frontend scripts or run nonexistent test paths.

Phase 1 closes only when an approved fresh database can migrate/seed; real uploads/indexing show correct persisted states; tenant/role/deletion/status filters work; supported answers cite actual evidence and missing evidence abstains; dependency failures are visible; the browser completes the flow; and checks, versions, limitations and reviews are recorded.

## Agent start template

~~~text
Work on KNEXUS as [Hassan / Naveed / Zaid].
Read current user instructions, AGENTS.md, PROJECT_STATUS, CONTRIBUTING,
TEAM_RESPONSIBILITIES and the Phase 1 contract/playbook.
Inspect actual branch/revision and all pending files; preserve work.
Use the agreed published baseline and first incomplete owned task [ID].
Preserve canonical schemas and H01 generation compatibility.
Implement a reviewable slice with meaningful checks and report actual
results, limitations, source snapshot and dependent-owner handoffs.
Do not install, start services, access DBs, commit, push or merge without
authorization covering that action.
~~~

Hassan starts at H03, Naveed finishes N02-N06 evidence/gaps, and Zaid starts Z01. Report checkout/branch/HEAD, task IDs, behavior, all files, interface changes, exact checks/results, fake versus live evidence, blockers, next task and authorized Git/PR status. Retain raw evaluation results without secrets.
