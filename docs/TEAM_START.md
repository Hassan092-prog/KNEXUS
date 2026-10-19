# Team start: shared baseline and personal setup

**Status: 19 October 2026.** The documentation baseline is published on main at commit `1a258e6`. All three persistent member branches are published. The Phase 1 contract reference and examples are published on dev-hassan in [Draft PR #1](https://github.com/Hassan092-prog/KNEXUS/pull/1); they are not accepted or implemented endpoints yet.

## GitHub accounts and access

| Member | GitHub account | Branch | Access observed |
|---|---|---|---|
| Hassan | Hassan092-prog | dev-hassan | Repository admin/write access |
| Naveed | MrMax3757 | dev-naveed | Write access already active |
| Zaid | MohammedZaid1946 | dev-zaid | Write-access invitation already pending; accept it in GitHub notifications/email |

No new invitations were sent. Zaid must accept the existing invitation before cloning this private repository with his own account. Do not share Hassan's credentials. Merge commits are enabled. The API returned 403 for branch-protection/ruleset inspection; review those settings manually in GitHub rather than assuming protection exists.

## Personal clones and branches

Each person uses their own clone, even if sharing a server. The shared workspace is currently on Hassan's branch; another person must not switch that same directory to their branch.

From a terminal in your own projects folder:

```powershell
git clone https://github.com/Hassan092-prog/KNEXUS.git
Set-Location KNEXUS
git config user.name "Your Name"
git config user.email "Your GitHub commit email"
git fetch origin
```

Run only your branch command in the fresh clone.

**Hassan:**

```powershell
git switch --track origin/dev-hassan
```

**Naveed:**

```powershell
git switch --track origin/dev-naveed
```

**Zaid:**

```powershell
git switch --track origin/dev-zaid
```

If that local branch already exists, use `git switch dev-hassan` (or your branch), not `--track` again. Check `git status --short --branch` before editing. Since upstream tracking is set, `git push` sends your commits to your own branch.

After the contract PR is reviewed and merged with a merge commit, synchronize on your own branch from a clean tree:

```powershell
git fetch origin
git merge --no-edit origin/main
git push
```

Do not self-merge a draft contract without the team's review. Use one active PR per persistent branch.

## Contract baseline and first tasks

Review [PHASE_1_CONTRACT.md](PHASE_1_CONTRACT.md), the [reference types/examples](../contracts/phase1/README.md), and [responsibilities](TEAM_RESPONSIBILITIES.md). The generated JSON Schema expresses shapes; Python checks add semantic invariants. The files do not wire routes, models or frontend components into the scaffold.

After installing the backend environment from CONTRIBUTING, run:

```powershell
./backend/venv/Scripts/python.exe contracts/phase1/check.py
```

On the shared Linux server, use `backend/venv/bin/python contracts/phase1/check.py` from the repository root. The checker needs no database or Ollama. All three owners review field names and fixture states before live integration.

| Member | First implementation PR |
|---|---|
| Hassan | Adopt agreed data/service contracts, initial Alembic/models/storage, tenant-consistency checks; then ingestion/retrieval/API orchestration |
| Naveed | Prompt/context/result validation using supplied generation fixtures and a fake provider; then Ollama adapter and answer cases |
| Zaid | React/TypeScript scaffold and typed frontend API mocks using supplied upload/document/status/query/error fixtures; then upload/chat/citation UI |

Use the scaffold precautions in frontend/README.md to preserve existing files. Live endpoints are still Phase 1 work. Missing provider/DB/UI implementation must produce explicit unavailable/loading/error states rather than fake success.

## Ollama runs on Naveed's computer

This is the selected inference host. The shared server has an i3-7100U, about 8 GB total RAM, Intel HD 620 graphics, roughly 4 GB available RAM and about 13 GB free disk at inspection. Keep its capacity for PostgreSQL/API. Naveed confirmed his computer is substantially stronger; exact RAM/GPU and live model performance are still to be measured.

Install the official Ollama desktop/runtime on Naveed's computer and verify that it is running. [Official download](https://ollama.com/download) and [runtime configuration](https://docs.ollama.com/faq).

In Naveed's terminal:

```powershell
ollama --version
ollama pull llama3.2:3b
ollama list
ollama run llama3.2:3b "Reply with READY."
ollama ps
```

If no background Ollama service is running, start `ollama serve` in a separate terminal. Do not start a second service if port 11434 is already occupied by Ollama. Use an explicit model tag and record its model digest/version for experiments. Download and runtime memory requirements are different; Ollama also allocates context memory, which grows with context/concurrency. Start with one request at a time and measure before increasing concurrency. [Ollama concurrency guidance](https://docs.ollama.com/faq#how-does-ollama-handle-concurrent-requests).

### Shared API server reaches the laptop through SSH

Keep Ollama on its default laptop loopback address. From Naveed's computer, run this and leave the terminal open while using shared-server generation:

```powershell
ssh -N -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 -o ServerAliveCountMax=3 -R 127.0.0.1:11435:127.0.0.1:11434 hassan@192.168.1.92
```

The tunnel maps server localhost:11435 to Naveed's localhost:11434. It does not bind Ollama to every network interface. Use an authorized SSH account/key for the server; GitHub access and SSH access are separate. Server-side TCP forwarding must be allowed and port 11435 must be free; ExitOnForwardFailure reports a conflict. Do not send anyone a password or private key in chat or commit it to Git.

The shared server's ignored root `.env` is configured for:

```dotenv
OLLAMA_BASE_URL=http://127.0.0.1:11435
OLLAMA_MODEL=llama3.2:3b
```

Restart the backend process after changing settings because they are cached. Keep `.env` out of commits. Other members running their own local backend retain localhost:11434 when their own Ollama is local; the example file remains a local-development default.

From a server terminal, after Naveed's model service and SSH tunnel are active:

```bash
curl --fail http://127.0.0.1:11435/api/tags
```

The configured model must appear in tags. To verify actual generation, use the future adapter or a bounded test request rather than relying on the scaffold's aggregate health flag. When Naveed sleeps/shuts down or closes the tunnel, shared-server generation becomes unavailable; fake-provider/UI-mock work can continue. The SSH tunnel and model response cannot be verified until Naveed starts them on his computer.

## Finish the handoff

- [x] Published existing documentation baseline.
- [x] Published dev-hassan, dev-naveed and dev-zaid and set upstream tracking in the shared clone.
- [x] Verified Naveed's write access and Zaid's pending invitation.
- [x] Prepared draft contract types, synthetic examples and independent validation.
- [x] Chosen Naveed's computer as inference host and configured the shared backend's tunnel URL/model tag.
- [ ] Zaid accepts the invitation; both members verify their own clones and runtime setup.
- [ ] Team reviews and merges the contract PR, then members synchronize from main.
- [ ] Naveed installs/loads Ollama and starts the tunnel; verify actual generation from the shared server.
- [ ] Start the three implementation PRs above.
