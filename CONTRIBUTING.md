# Setup and contribution guide

Read [project status](docs/PROJECT_STATUS.md) for the shared revision and [team responsibilities](docs/TEAM_RESPONSIBILITIES.md) for ownership. Hassan's shared-workspace commands run over SSH to `hassan@192.168.1.92`. Each laptop clone uses its own environment.

## 1. Choose a safe checkout

Each member uses a separate clone or agreed worktree. Inspect changes before switching or synchronizing:

~~~bash
git status --short --branch
git branch --show-current
git remote -v
git fetch origin --no-tags
~~~

The four persistent branches are `main` and the three `dev-*` branches. Each member branch tracks its matching remote branch. The reviewed baseline is now on main; integration/review branches are retired. Do not merge the old dev-naveed generator over the reviewed foundation.

For a new clone, after verifying the agreed starting point:

~~~bash
git clone https://github.com/Hassan092-prog/KNEXUS.git
cd KNEXUS
git switch --track origin/dev-hassan
~~~

Naveed uses `origin/dev-naveed`; Zaid uses `origin/dev-zaid`. If the local branch exists, switch without `--track`. Confirm `git config user.name` and `git config user.email`; use your own account and actual authorship.

A stale member branch needs a reviewed baseline handoff first. Inspect ancestry and local edits; never reset, force-push or import the old generation checkpoint automatically.

## 2. Prepare the backend

Python 3.12 is the team baseline. Installation commands below are for an approved new personal environment. Reuse the working server environment. Run from the repository root.

Linux/macOS:

~~~bash
if [ ! -f .env ]; then cp .env.example .env; fi
python3.12 -m venv backend/venv
backend/venv/bin/python -m pip install -r backend/requirements.txt
~~~

Windows PowerShell:

~~~powershell
if (-not (Test-Path -LiteralPath .env)) {
    Copy-Item -LiteralPath .env.example -Destination .env
}
py -3.12 -m venv backend/venv
.\backend\venv\Scripts\python.exe -m pip install -r backend/requirements.txt
~~~

`Settings` resolves `.env` relative to the repository root, independently of the working directory. Exported variables override it. Restart after changes because settings are cached. Development defaults are unsuitable for public deployment.

`DATABASE_URL` is independent of `POSTGRES_*` fields; changing them does not rebuild it. Compose's default host port is 5435, container port 5432. Existing volumes retain initialization data when environment values change.

## 3. Run offline checks

Linux/macOS, from the root:

~~~bash
backend/venv/bin/python -B -m pytest backend/tests/test_h01_boundaries.py backend/tests/phase1/generation backend/tests/test_persistence_models.py -q -p no:cacheprovider
backend/venv/bin/python -B contracts/phase1/check.py
~~~

PowerShell:

~~~powershell
.\backend\venv\Scripts\python.exe -B -m pytest backend/tests/test_h01_boundaries.py backend/tests/phase1/generation backend/tests/test_persistence_models.py -q -p no:cacheprovider
.\backend\venv\Scripts\python.exe -B contracts/phase1/check.py
~~~

These need no database, model service or downloads. The separate canonical checker proves contract invariants, not working APIs or model quality. See [backend tests](backend/tests/README.md) for database safeguards and recorded evidence.

## 4. Start a local API when needed

For an approved new local PostgreSQL service:

~~~bash
docker compose up -d postgres
~~~

Do not use this as a shared-server reset. Initialization enables vector on a new volume only. Application tables require Alembic; online migrations and explicit seeding require approval for the exact database. See [database schema](docs/DATABASE_SCHEMA.md).

~~~bash
backend/venv/bin/python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
~~~

PowerShell uses `.\backend\venv\Scripts\python.exe` with the same arguments. Use an available port; an earlier server check used 8002 because 8000/8001 were occupied. Check availability again rather than assuming it.

While the API is intentionally running:

~~~bash
curl --fail --max-time 10 http://127.0.0.1:8000/
curl --fail --max-time 10 http://127.0.0.1:8000/api/v1/health
~~~

Health always returns HTTP 200 and checks Ollama tags, not generation. See [current API behavior](docs/API_SPEC.md).

## 5. Connect laptop inference

Naveed's laptop is the selected Ollama host; the shared Linux server hosts API/database services. Hassan can use the same adapter locally without transferring implementation ownership.

Use the existing installed model. Installations, downloads and service changes require approval. Do not start a second daemon if Ollama is running.

~~~bash
ollama --version
ollama list
ollama ps
~~~

The [generation README](backend/app/services/generation/README.md) owns provider configuration, injection and live-harness commands. Root `.env` does not automatically export settings to the standalone generator.

Naveed runs this authorized tunnel on his laptop while Ollama listens on loopback:

~~~powershell
ssh -N -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 -o ServerAliveCountMax=3 -R 127.0.0.1:11435:127.0.0.1:11434 hassan@192.168.1.92
~~~

API-side generation uses `http://127.0.0.1:11435`; laptop-local checks use `http://127.0.0.1:11434`. GitHub access does not grant SSH access. Use approved accounts/keys; never share secrets.

While that tunnel is intentionally active, server-side reachability can be checked with:

~~~bash
curl --fail --max-time 10 http://127.0.0.1:11435/api/tags
~~~

Tags prove reachability only. Use the opt-in generation harness for structured answers/abstentions. Sleeping the laptop or closing the tunnel makes shared inference unavailable.

## 6. Prepare frontend development

Zaid owns the frontend. Only its README is committed. Confirm the React/TypeScript framework and supported Node/npm versions first; Vite and Next.js were discussed, but neither has a committed application scaffold.

Generate into an empty temporary directory and adapt into `frontend/` without removing existing work. Document actual commands after adding a manifest and lockfile. Browser configuration contains no secrets.

When Hassan runs the API on server port 8002, Zaid can use this authorized tunnel:

~~~powershell
ssh -N -o ExitOnForwardFailure=yes -L 127.0.0.1:8000:127.0.0.1:8002 hassan@192.168.1.92
~~~

The frontend API base is then `http://127.0.0.1:8000/api/v1`. Choose another local port if occupied. The browser calls the API, never Ollama. Keep mock mode visible; never substitute fixtures for live errors.

## 7. Review and integrate

Main now contains the accepted baseline. Synchronize a clean member branch with `git fetch origin --no-tags` and a reviewed normal merge from `origin/main`. If your branch has divergent implementation or pending edits, inspect and coordinate rather than merging blindly.

Work in small owned slices. Inspect and stage named files. Commits, pushes, PRs and merges need the user's authorization; this guide is not automatic approval. Use one active PR per member branch targeting `main`.

Inspect the staged diff and `git diff --cached --check`. Exclude secrets, uploads, large corpora, model weights, environments and caches. Use merge commits to preserve member history; never force-push persistent branches.

Hassan reviews integration. Check repository protections and CI in GitHub rather than assuming they exist. Coordinate conflicts with the owner and preserve both intended changes.

Delete a temporary branch only when its commits are reachable from a retained branch, no active PR depends on it, owners have handed off work, and attached worktrees are preserved. Retain all three member branches.

## Troubleshooting

| Symptom | Action |
|---|---|
| Environment changes ignored | Restart; exported variables override root `.env` |
| DB cannot connect | Verify explicit URL/host/port without printing credentials; never reset the volume |
| Application tables missing | Obtain approval for the migration target; startup creates no tables |
| Tags work, generation fails | Check exact tag, provider configuration and typed failure |
| Upload/query returns 404 | Feature routes are not implemented |
| Old generator heuristics on a member branch | Preserve edits and coordinate a clean baseline handoff |
