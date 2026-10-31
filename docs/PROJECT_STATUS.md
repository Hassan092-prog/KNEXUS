# Current project status and next actions

**Current checkpoint: 31 October 2026 (Asia/Calcutta).** The isolated `integration/phase1` branch is based on H01 `074cb12b9552d5b72d95a7dda86252fbc564637f`. Its generation package is present locally with offline boundary and mock-provider coverage; 51 focused tests pass. The canonical contract checker passes separately with 17 examples and 24 negative cases. This foundation is available on `integration/phase1` and has not been merged into `main`.

The application feature routes, application migrations, document processing, retrieval APIs, authentication, action approval, and frontend application remain unimplemented. The branch adds no public feature route and does not establish live Ollama behavior or answer quality. The original `dev-hassan` checkout remains on H01 with its existing seven uncommitted document edits preserved. Older dated entries below are historical snapshots.

## What is complete

- Hassan has repository admin access. Naveed (MrMax3757) and Zaid (MohammedZaid1946) both have active write access. There are no pending repository invitations.
- Main and all three origin/dev-* branches contained the published setup/contract/playbook baseline fb9e889 before this status update. No later implementation commits or open PRs were found at that check.
- Shared backend dependency consistency and Docker Compose configuration pass. PostgreSQL is healthy; real database connectivity and the vector extension are verified.
- Contract checking passes 17 synthetic examples, 24 negative cases, evidence membership and schema freshness. All eight tracked Python files parse.
- In-process scaffold routes pass. A temporary real HTTP server on port 8002 also passed root, Swagger, OpenAPI and health checks; it was stopped after verification.

## What remains

| Area | Current evidence | Next owner/action |
|---|---|---|
| Personal clones and tooling | GitHub permission confirmed; laptop clone/push/runtime checks not observed | Each member verifies their own branch/upstream/environment |
| Running API address | Ports 8000 and 8001 occupied; expected KNEXUS routes on 8000 return 404 | Hassan starts KNEXUS on free port 8002 for development; verify again before use |
| Inference | Server localhost:11435 closed; live model/tag/generation not verified | Naveed starts local Ollama and reverse SSH tunnel; Hassan checks server-side inference |
| Backend features | Root and health only; no feature routes, application migrations or models | Hassan starts H01, then H02-H07 |
| Generation implementation | Contract examples exist; no generation service yet | Naveed starts N01, then N02-N06 |
| Frontend | README only; no app/package/build yet | Zaid starts Z01, then Z02-Z06 |

**Decision:** shared setup and repository access support starting Phase 1 after each person's local setup checks. Live end-to-end integration is not ready. No Phase 1 feature task is marked complete based on scaffolding, installed packages or fixture validation. Offline inference does not block the independent first tasks.

## What to do, in order

| When | Hassan / dev-hassan | Naveed / dev-naveed | Zaid / dev-zaid |
|---|---|---|---|
| First work session, before edits | Sync own branch; rerun contract check; start API only when needed | Sync own branch; verify Python environment and contract fixtures | Clone/sync own branch; verify Node/npm and fixture fields |
| Same session, after setup | H01: runtime schemas, server-owned demo actor, injected generation boundary/test setup | N01: agree async generation callable with Hassan; fake provider and focused checks | Z01: React/TypeScript/Vite scaffold, preserving existing README |
| Next reviewable slices | H02 models/migrations, then H03/H04 ingestion/indexing and H05/H06 retrieval/API | N02 prompt/context, then N03/N04 adapter/result validation; configure Ollama/tunnel alongside this | Z02 typed client/mocks, then Z03/Z04 upload/status/chat/citation views |
| At every completed slice | Push named changes to own branch, open/update its one active PR, report checks and handoff | Same | Same |
| Before live integration | Publish working endpoints; verify real model response and permissions/failure cases | Hand off working adapter and measured model/runtime details | Connect live client using the verified API address; keep mock/live modes explicit |
| Phase 1 completion gate | Together verify browser upload -> status -> stored/indexed chunks -> permitted retrieval -> cited answer or abstention; record results and remaining failures | Contribute generation/evaluation evidence | Contribute browser/UI/failure-state evidence |

These are task gates, not promised dates. Aim to finish the personal setup and first small task in the next work session; agree actual delivery dates after each developer reports availability and the first task's evidence. Do not wait for all backend features before beginning frontend mocks or generator checks. Follow the detailed done criteria in the [Phase 1 playbook](PHASE_1_TEAM_GUIDE.md).

## Commands for the next session

In each member's own clone, switch to their assigned branch and inspect for local changes. With a clean tree, synchronize:

```bash
git status --short --branch
git branch --show-current
git fetch origin
git pull --ff-only
git merge --no-edit origin/main
git branch -vv
```

The upstream must match your own origin/dev-* branch. If local commits cause divergence, inspect and coordinate a normal merge; never reset or force-push to conceal it. A new clone follows [TEAM_START.md](TEAM_START.md).

Hassan's server terminal (workspace commands run over SSH):

```bash
cd '/home/hassan/Documents/Hassan/coding_projects/Major Project/KNEXUS'
backend/venv/bin/python contracts/phase1/check.py
backend/venv/bin/python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8002
```

Keep the API terminal open. Verify in a second server terminal:

```bash
curl --fail --max-time 10 http://127.0.0.1:8002/api/v1/health
```

Port 8002 was free during this check; confirm before starting. Do not terminate an unidentified service occupying another port. Health HTTP 200/aggregate healthy is insufficient: inspect database, vector and Ollama fields individually.

For Zaid to reach this server instance, after authorized SSH access is arranged, run on Zaid's computer:

```powershell
ssh -N -o ExitOnForwardFailure=yes -L 127.0.0.1:8000:127.0.0.1:8002 hassan@192.168.1.92
```

The frontend client base remains http://127.0.0.1:8000/api/v1 on Zaid's machine. If his local port is occupied, choose another and update the client base. This is independent of the reverse Ollama tunnel on server port 11435. [Phase 0 step 5](PHASE_0_SETUP_GUIDE.md#5-enable-inference---naveed-then-hassan) gives Naveed's exact model/tunnel commands and Hassan's bounded real-generation check.

Use the [agent start prompts](PHASE_1_TEAM_GUIDE.md) for each developer's role. Ask the agent to inspect the current files, complete the first incomplete owned task, run meaningful checks and report the next handoff. Do not mark an implementation task done until its stated criteria pass.
