# Phase 0: team setup before Phase 1

Use this checklist before starting the [Phase 1 agent playbook](PHASE_1_TEAM_GUIDE.md). Finish access and the shared contract check first, then start the independent implementation tasks. Complete the live inference gate before claiming an integrated RAG demo.

See [current status and next actions](PROJECT_STATUS.md) for observed progress and the next task for each member.

## Readiness at the 21 October 2026 check

| Item | Evidence / status | Owner and next action |
|---|---|---|
| Shared backend environment | Python 3.12; dependency consistency check passes | Hassan maintains runtime |
| Database configuration | Compose valid; PostgreSQL healthy; actual connection/vector verified | Hassan maintains runtime |
| API address | Expected routes on port 8000 return 404; port 8001 also occupied; temporary HTTP check on 8002 passes | Use free port 8002 for shared development, verifying availability first |
| Shared contract reference | 17 synthetic examples and 24 negative cases pass; schema freshness/evidence membership checked | All members rerun in their own environment |
| GitHub access | Hassan admin; Naveed and Zaid active write; no invitations pending | Everyone verifies their own clone/fetch/push |
| Personal clones/tooling | Not verified from members' computers | Each member completes steps 1-3 |
| Inference | Naveed's computer selected; server tunnel port 11435 is offline | Naveed completes step 5 with Hassan |
| Application features | Backend scaffold only; frontend, migrations and RAG APIs are unimplemented | These are Phase 1 deliverables |

**Decision:** ready for independent work after each member passes access/branch/contract setup; not ready for live end-to-end integration. An offline model does not block fixture-based backend, generation or frontend work. The scaffold's HTTP-200 health response alone is not readiness evidence.

These are dated observations, not a continuously updated monitoring dashboard. Record new checks in the task/PR handoff. Academic submission gaps in [REPOSITORY_REVIEW.md](REPOSITORY_REVIEW.md) remain separate prerequisites.

## 1. Accept access and create personal clones - everyone

Sign in to GitHub using your own account. Zaid's invitation has been accepted; both MohammedZaid1946 and MrMax3757 have active write access, verified 21 October 2026. Everyone still needs to verify their own clone and push credentials. Never share GitHub tokens or passwords.

| Developer | GitHub login | Personal branch |
|---|---|---|
| Hassan | Hassan092-prog | dev-hassan |
| Naveed | MrMax3757 | dev-naveed |
| Zaid | MohammedZaid1946 | dev-zaid |

Install Git. In your own projects folder, run:

```powershell
git clone https://github.com/Hassan092-prog/KNEXUS.git
Set-Location KNEXUS
git config user.name "Your Name"
git config user.email "Your GitHub commit email"
git fetch origin
```

Choose exactly one command for your identity in a fresh clone:

```powershell
# Hassan
git switch --track origin/dev-hassan
# Naveed
git switch --track origin/dev-naveed
# Zaid
git switch --track origin/dev-zaid
```

For an existing clone use `git switch dev-yourname` with your actual branch name instead. Inspect changes before switching; do not reset or discard another person's work. Each member needs a separate working directory, even on a shared server.

On your member branch, with a clean tree:

```powershell
git status --short --branch
git fetch origin
git pull --ff-only
git merge --no-edit origin/main
git branch -vv
git push
```

The upstream must be your matching origin/dev-* branch. If pull reports divergence, inspect both histories and coordinate a normal merge; do not force-push. A successful clone, fetch and push proves your own account can use the repository. Synchronizing the server's branches does not update an already-cloned laptop.

## 2. Read and agree the boundaries - everyone

Read [TEAM_RESPONSIBILITIES.md](TEAM_RESPONSIBILITIES.md), [PHASE_1_CONTRACT.md](PHASE_1_CONTRACT.md), and [contract reference](../contracts/phase1/README.md), then your task section in the Phase 1 playbook.

- Hassan owns runtime schemas/API/database/ingestion/retrieval and integration.
- Naveed owns prompt/context/generation/citation validation and Ollama.
- Zaid owns the entire frontend and its API mocks/client.

Agree the async generation callable/import boundary before backend and generator implementations depend on it. Use the supplied wire fields and synthetic examples. Treat directories and endpoints described in designs as proposed until actual code exists.

## 3. Prepare only the environment your role needs

**Hassan:** use Python 3.12 and Docker Compose. The shared server already has the backend environment/database; preserve the existing root .env and database volume. Run workspace commands over SSH to hassan@192.168.1.92, following the user's workspace instructions. Start a server terminal with:

```powershell
ssh hassan@192.168.1.92
```

Then, on the Linux server:

```bash
cd '/home/hassan/Documents/Hassan/coding_projects/Major Project/KNEXUS'
backend/venv/bin/python --version
backend/venv/bin/python -m pip check
docker compose config --quiet
docker compose ps
backend/venv/bin/python contracts/phase1/check.py
```

For a genuinely new environment, follow [CONTRIBUTING.md](../CONTRIBUTING.md) for venv/dependency/.env/Compose setup. Do not reinstall or recreate the working shared environment merely to tick a checklist.

**Naveed:** install Python 3.12 on your computer and create your own backend environment using CONTRIBUTING. You can run generation fixture/fake-provider checks without Docker, PostgreSQL or the frontend. Do not start local database services unless you need a local backend.

**Zaid:** install a supported Node.js LTS release and npm; confirm `node --version` and `npm --version`. Follow [frontend/README.md](../frontend/README.md) when starting Z01; preserve its existing README while scaffolding. There is no package.json yet, so npm install/build is not a Phase 0 check. Build/lint/test commands become available only after the frontend is initialized. To run the Python contract checker locally, use the Python environment from CONTRIBUTING, or review its output with Hassan until your own is installed.

On Windows, after creating the backend venv, run from your own repo root:

```powershell
./backend/venv/Scripts/python.exe -m pip check
./backend/venv/Scripts/python.exe contracts/phase1/check.py
```

No database or model service is needed for this contract check. Do not regenerate schema.json to conceal a mismatch. Never commit .env, tokens, uploaded documents, model downloads or database files.

## 4. Verify the scaffold - Hassan

The expected KNEXUS routes on server port 8000 currently return 404 and port 8001 is also occupied. Use port 8002 if still free; do not stop an unidentified service. A temporary check on 8002 passed and was stopped afterward. From the server repo root, start the API in a dedicated terminal when needed:

```bash
backend/venv/bin/python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8002
```

In a second server terminal:

```bash
curl --fail http://127.0.0.1:8002/
curl --fail http://127.0.0.1:8002/api/v1/health
curl --fail http://127.0.0.1:8002/api/v1/openapi.json
```

Expect database connected and pgvector_extension installed. Inspect individual fields: aggregate healthy can still accompany offline Ollama. Swagger is /docs. Root and health are the only application routes today; upload/query returning 404 is expected until Phase 1 implements them. Do not reset the shared database to test future migrations; use a disposable test database.

## 5. Enable inference - Naveed, then Hassan

On Naveed's computer, install [Ollama](https://ollama.com/download) and verify its background service is running. If no service is running, start ollama serve in another terminal. Keep the default loopback listener.

```powershell
ollama --version
ollama pull llama3.2:3b
ollama list
ollama run llama3.2:3b "Reply with READY."
ollama ps
```

Record model tag/digest, RAM/GPU and observed generation behavior. Use one request at a time initially. The stronger laptop is the inference host; the shared server remains the API/database host.

Hassan must arrange authorized server SSH access for Naveed before the tunnel can work. GitHub access does not grant server access. Use an approved SSH key/account arrangement; do not share private keys. From Naveed's computer, leave this terminal running:

```powershell
ssh -N -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 -o ServerAliveCountMax=3 -R 127.0.0.1:11435:127.0.0.1:11434 hassan@192.168.1.92
```

The shared server's ignored root .env already selects:

```dotenv
OLLAMA_BASE_URL=http://127.0.0.1:11435
OLLAMA_MODEL=llama3.2:3b
```

Restart any existing backend after configuration changes. From the server terminal, verify model availability and a bounded real generation request:

```bash
curl --fail --max-time 10 http://127.0.0.1:11435/api/tags
curl --fail --max-time 120 http://127.0.0.1:11435/api/generate -H 'Content-Type: application/json' -d '{"model":"llama3.2:3b","prompt":"Reply with READY.","stream":false,"options":{"num_predict":16}}'
```

Confirm the selected model appears in tags and generation returns a nonempty response with done=true, not an error. This proves connectivity/inference, not citation quality or the future application adapter. If generation is too slow or fails, record it and resolve the model/runtime configuration before live integration. Closing the tunnel or sleeping the laptop makes shared inference unavailable; fixture-based work can continue.

## 6. Connect frontend development - Zaid

Use typed contract fixtures first. When the server API is needed, obtain authorized SSH access and run from Zaid's computer:

```powershell
ssh -N -o ExitOnForwardFailure=yes -L 127.0.0.1:8000:127.0.0.1:8002 hassan@192.168.1.92
```

Keep the tunnel open and set the future frontend client's API base to http://127.0.0.1:8000/api/v1. The API must be running on the server. If local port 8000 is occupied, choose another local port and change the client base accordingly. The browser calls the backend, never Ollama. Until upload/query routes exist, mock mode must be explicit; live failures must remain visible.

## 7. Start, review and finish Phase 1

1. After access/branch/contracts, Hassan begins H01, Naveed N01 and Zaid Z01 in the [playbook](PHASE_1_TEAM_GUIDE.md). Start with fake providers and fixture payloads.
2. Complete the later tasks in each member's sequence, exchanging actual callable/schema/API handoffs. Finish the inference gate before the live generator handoff.
3. After each task, inspect the diff, stage named files, run relevant checks, commit and push to your own dev-* branch. Open one PR at a time from that branch to main.
4. Review shared-contract changes together. Merge using merge commits, then each member fetches and merges origin/main into their own branch. Never force-push member branches.
5. Finish Phase 1 only after the playbook's browser upload-to-cited-answer/abstention demo and failure checks pass. Record actual results and remaining gaps.

## Setup handoff checklist

- [x] Zaid accepted; Naveed and Zaid both have active write access.
- [ ] All members verify clone/fetch/push using their own account.
- [ ] Each personal clone is on the correct dev-* branch with matching upstream and current shared docs/contracts.
- [ ] Each member reviews the contract/checker evidence and agrees the service/wire boundaries.
- [x] Shared backend, PostgreSQL and vector verified on 21 October (temporary API check stopped afterward).
- [ ] Naveed verifies personal Python tooling; Zaid verifies Node/npm.
- [ ] Authorized SSH access is arranged for members who need server tunnels.
- [ ] Naveed starts Ollama/tunnel; Hassan verifies tags and a real bounded response from the server before live integration.
- [ ] Each owner starts the first incomplete task and records checks/handoff evidence in their PR.

Agents should report which host and branch they checked, commands and outcomes, files changed, unresolved dependencies and next task. Mark a check complete only after observing it; installing dependencies does not implement features.
