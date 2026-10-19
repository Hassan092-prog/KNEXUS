# Phase 1: three-member execution guide

**Goal:** deliver one repeatable local vertical slice: load a small permitted/synthetic corpus, parse and chunk documents, store 384-dimensional embeddings in PostgreSQL/pgvector, retrieve authorized evidence, and produce an answer that cites retrieved source IDs or abstains.

The current repository only has the backend scaffold and PostgreSQL/vector bootstrap. These are task assignments and proposed interfaces, not implemented features. Use the same persistent personal branches and PR process in [the Git workflow](KNEXUS_Team_Git_Workflow_Guide.md).

## Member responsibilities

Follow [TEAM_RESPONSIBILITIES.md](TEAM_RESPONSIBILITIES.md): Hassan / Member 1 owns backend, database/migrations and data/runtime integration; Naveed / Member 2 owns generation and prompt work; Zaid / Member 3 owns the entire frontend.

## Start-of-Phase-1 checklist

Use [TEAM_START.md](TEAM_START.md) for the current handoff status and exact personal-branch/Ollama commands.

- [x] Existing documentation baseline is published on main (`1a258e6`).
- [x] Published `dev-hassan`, `dev-naveed` and `dev-zaid` from that baseline.
- [x] Verified Naveed/MrMax3757 has write access. Zaid/MohammedZaid1946 has a pending write invitation.
- [x] Prepared [the draft contract baseline](PHASE_1_CONTRACT.md), Pydantic reference models, generated JSON Schema and synthetic mocks on Hassan's branch.
- [x] Chosen Naveed's computer for Ollama and configured the shared backend for a loopback SSH tunnel.
- [ ] Zaid accepts the existing invitation and each member verifies their own clone/environment.
- [ ] Review and merge the contract PR before relying on its fields for live integration; sync member branches from main after the merge.
- [ ] Naveed installs/loads the selected model and starts the tunnel; verify a real bounded generation request from the shared server.
- [ ] Zaid initializes the frontend, preserves its README and commits its package manifest/lockfile.

Application migrations, ingestion/query routes, the real generator, frontend source and feature test suites remain Phase 1 implementation work. Contract reference checks run independently of those services. Keep the pre-authentication demo local and synthetic. Academic submission follow-ups remain in the repository review.

## First agree on the interfaces

A concrete proposal is prepared in [PHASE_1_CONTRACT.md](PHASE_1_CONTRACT.md) and [contracts/phase1](../contracts/phase1/README.md). Review its examples together in the contract PR before live integration:

1. **API:** Keep the proposed `POST /api/v1/documents/upload` and `POST /api/v1/query` paths in `API_SPEC.md`, or explicitly agree on changed paths. Define upload type/size limits, queued/processing/complete/failed states, question/top-k input, answer/abstention, and citation fields. Treat the existing API spec as a proposal; these routes do not yet exist.
2. **Data ownership:** Agree on stable IDs and ownership fields before migration work starts. Documents, chunks, and embeddings need organization IDs from the start. Define uploader, source type, filename/storage reference, lifecycle, chunk index/content/page metadata, embedding model, and vector dimension. Parent/child tenant consistency must be enforced by constraints or validated transactionally.
3. **Service boundary:** Hassan owns the API, data models/migrations, ingestion/retrieval and authorization contracts. Naveed's generator accepts a question plus ranked authorized evidence and returns an answer plus validated evidence IDs; it does not fetch documents or choose permissions. Zaid's frontend consumes accepted API contracts and uses clearly labeled typed mocks while endpoints are incomplete.
4. **Privacy boundary:** Run only on a small dataset whose use is permitted, or synthetic examples. Until authentication/RBAC is implemented and tested, keep ingestion and query limited to local synthetic demo data. Retrieval filters must include the current demo tenant and allowed roles before evidence reaches the model; do not claim user authentication exists.
5. **Evaluation scope:** A 1,000-2,000-record subset may not contain gold evidence for all 500 benchmark questions. Start with 20-50 labeled development questions and a small held-out set; record source IDs, dataset revision, model/prompt versions, and known coverage.

Record agreed fields and response examples before code depends on them. Merge the contract PR, then ask each owner to sync their own branch from `origin/main`.

## Divide ownership to reduce conflicts

### Hassan (Member 1): backend, database, data and runtime

Work in `dev-hassan`. Own routes/request-response schemas, SQLAlchemy models and Alembic migrations, vector storage, PDF/DOCX parsing, tokenizer-aware chunking, embedding/indexing, tenant/role-filtered retrieval, corpus importer/provenance, backend fixtures, configuration/Compose, health/readiness and API integration.

**Phase 1 deliverables:** an agreed API/data/service contract; fresh-database migrations; one small indexed corpus with preserved source IDs; upload/query services with useful failure states; filtered retrieval before generation; backend integration evidence. Implement auth before any shared sensitive-data path; keep the pre-auth demo local and synthetic.

### Naveed (Member 2): generation and prompt evaluation

Work in `dev-naveed`. Own the Ollama adapter, versioned prompt, context formatting, output parsing, citation validation against retrieved IDs and answer-quality cases.

**Phase 1 deliverables:** deterministic prompt/response-validation checks using a fake model; bounded provider errors; a versioned grounded-answer prompt; supported/missing/conflicting/adversarial answer cases and gold labels. Start with non-streaming answers; coordinate SSE with Hassan only after the full path works.

Prompt instructions alone do not enforce authorization or guarantee factuality. Hassan filters evidence before generation; Naveed validates the returned source IDs and measures answer behavior. Keep the generator independent of FastAPI and database internals.

### Zaid (Member 3): entire frontend, upload and chat

Work in `dev-zaid`. Own React/TypeScript/Vite initialization, design tokens/components, frontend types/API client/mock payloads, document upload/status/list, chat/citation/source-detail/abstention views, responsive behavior and accessibility.

**Phase 1 deliverables:** usable upload and chat flows against clearly labeled mocks first, then Hassan's accepted APIs; visible loading/empty/error/retry/provider-offline states; citations linked to returned source metadata; initial UI checks and setup notes. Do not assign database migrations, dataset ETL, backend configuration or deployment to Zaid; those belong to Hassan. UI permission indicators consume backend decisions and cannot authorize access.

## Suggested order and integration gates

1. **Contract gate:** merge the API/data/service-interface decision. No parallel edits to the same model, route, settings, or Compose file.
2. **Storage gate:** Hassan proves migrations run up/down on a fresh disposable database and seed fixtures preserve source IDs.
3. **Ingestion gate:** Hassan connects PDF/DOCX parsing, chunking, embeddings, and persistence; verify empty/malformed files fail visibly and partially indexed documents do not look complete.
4. **Retrieval gate:** retrieve top-k chunks for the active demo tenant/allowed roles. Test an unauthorized high-similarity distractor never reaches generation.
5. **Answer gate:** Naveed generates a grounded answer from provided chunks, validates citations against the retrieved IDs, and abstains when evidence is absent or below a threshold selected on development data.
6. **Frontend gate:** Zaid connects upload/status and chat/citation/abstention screens to the accepted contracts; clearly distinguish mocks from live backend responses.
7. **End-to-end gate:** Hassan integrates the backend/runtime, Naveed verifies answer behavior and Zaid verifies the UI path. One clean setup can start PostgreSQL, apply migrations, load a fixture, upload/query and display citations or abstention. Record actual outcomes and known failures.

A practical four-week sequence is: week 1 contracts/database, a provider stub and frontend mocks in parallel; week 2 ingestion/seeded data and upload/chat components; week 3 retrieval/generation and live UI integration; week 4 end-to-end fixes, held-out evaluation and demo notes. Adjust dates to the review calendar.

## Branch commands for each member

The three branches are already published. Each person uses their own clone and tracks their branch. Replace `YOUR_BRANCH` with exactly one of `dev-hassan`, `dev-naveed`, or `dev-zaid`:

```powershell
git clone https://github.com/Hassan092-prog/KNEXUS.git
Set-Location KNEXUS
git config user.name "Your Name"
git config user.email "you@example.com"
git switch main
git pull --ff-only origin main
git switch --track origin/YOUR_BRANCH
```

Daily work and push:

```powershell
git status --short --branch
git branch --show-current
git add path/to/your/changed-file
git diff --cached
git commit -m "feat(retrieval): add top-k vector search"
git push
```

Sync teammate changes already merged to main before starting another task:

```powershell
git fetch origin
git merge --no-edit origin/main
git push
```

Open one PR from your branch to `main` when the work is reviewable. Use a merge commit so later PRs from the same persistent branch remain clean. Never force-push a shared member branch or commit directly to `main`. Full initial setup and conflict instructions are in [KNEXUS_Team_Git_Workflow_Guide.md](KNEXUS_Team_Git_Workflow_Guide.md).

## Collaborative coding prompt template

Use one task, one owner, one branch, and explicit file/interface boundaries. Include current implementation facts, not only the aspirational project description.

```text
Project: KNEXUS. Current implementation: FastAPI scaffold; the requested route/service is not implemented yet.
Owner: <member>. Branch: <dev-member>.
Task: <one observable behavior>.
Read first: docs/TEAM_RESPONSIBILITIES.md and docs/PHASE_1_CONTRACT.md, then <specific implementation files>.
Own these files: <paths>. Shared files requiring coordination: <paths>.
Interface: <inputs, outputs, error/status behavior, tenant/evidence fields>.
Constraints: keep changes in scope; use only permitted/synthetic data; don't claim authentication/RBAC exists unless this task implements and tests it; don't invent citations; preserve existing behavior outside the task.
Acceptance: <observable outcomes and edge cases>.
Before editing: summarize the current relevant behavior and proposed changes. If the contract conflicts with code or another owner's files, explain the conflict and propose a narrow resolution.
After editing: summarize changed files, commands actually run and outcomes, remaining risks, and the exact commit/PR boundary. Do not claim checks that were not run.
```

Ask teammates to review a diff with a separate prompt:

```text
Review this PR against its stated acceptance criteria and current KNEXUS contracts. Prioritize correctness, tenant/permission leaks, migration compatibility, citation validity, failure states, and unintended scope. Inspect the diff and relevant callers. Return findings first with file/line and a concrete failure scenario. Don't rewrite the PR; label items blocking or follow-up. If no blocking findings, say what remains unverified.
```

## Prompt engineering collaboration loop

1. Put the baseline prompt in a versioned template file with a version ID. Keep provider parameters and prompt content separate.
2. Define inputs explicitly: question plus ordered evidence records with stable IDs, titles, excerpts, and page/chunk metadata. Delimit retrieved text as untrusted evidence. Never put secrets or permission decisions in the prompt.
3. Specify outputs in a schema the application can validate: answer/abstain state, cited evidence IDs, and a short abstention reason. Reject citations outside the retrieved-ID set.
4. Build a small shared development set with answerable, unanswerable, conflicting, irrelevant, long-question, and prompt-injection examples. Keep held-out examples out of prompt tuning.
5. Change one factor per experiment (prompt wording, model tag, temperature, context size, or retrieval setting). Log exact prompt version, Ollama model/version, parameters, retrieved IDs, output, latency, and manual labels. Do not compare outputs from runs with different evidence without recording that change.
6. Have Naveed own the baseline prompt, variant naming and answer labels; Hassan owns dataset/source provenance, backend fixtures and API/output compatibility; Zaid owns frontend API mocks and citation/abstention presentation. Discuss findings in the PR and keep experiments on the owner's persistent branch until review.
7. Promote a prompt only when the same regression set shows fewer unsupported claims without worse citations/abstention. Record failures and limitations instead of selecting examples that merely look impressive.

## Skills that may help

- **`skill-creator`**: create a reusable KNEXUS Phase 1 skill with the repo facts, member responsibilities, Zaid's frontend ownership, branch convention, API/schema contract, prompt template, and review checklist so all three members start coding tasks consistently.
- **`documents:documents`**: prepare and render the final project report or user manual, then inspect page layout.
- **`presentations:Presentations`**: revise review/final slides and check the rendered deck against college requirements.
- **`pdf:pdf`**: inspect or prepare PDF papers and submissions.
- **`visualize:visualize`**: explain the ingestion/retrieval and authorization flows with a diagram during design reviews.
- **`openai-docs`** is useful only if the project adds OpenAI APIs/models; for the current Ollama plan it is not needed.

For day-to-day implementation, the most useful shared asset would be a small repository-specific skill built with `skill-creator`; the other skills apply to the academic deliverables above.
