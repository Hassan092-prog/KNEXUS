# Setup and contribution guide

Read [project status](docs/PROJECT_STATUS.md) for the shared revision and [team responsibilities](docs/TEAM_RESPONSIBILITIES.md) for ownership. Hassan's shared-workspace commands run over SSH to `hassan@192.168.1.92`. Each laptop clone uses its own environment.

## Model policy and live-call gate

All real AI usage goes through hosted APIs, called by the backend with server-held keys:
- embeddings: Google gemini-embedding-001 at 384 dimensions via outputDimensionality, in backend/app/services/ingestion/embedding.py;
- generation: Groq openai/gpt-oss-120b.
- The browser only calls the KNEXUS backend, never a provider, and holds no keys.
- Local models (MiniLM sentence-transformers/all-MiniLM-L6-v2) and the fake generator are for tests, CI and local development only. They are not the demo or production path.
- No automatic retries or fallback between providers. No paid usage without Hassan's approval.

Keep mocks explicit; missing application configuration fails clearly, never silently selects fake. No paid calls, billing activation, fallback or automatic retries are authorized without Hassan's approval.

## 1. Choose a safe checkout

Each member uses a separate clone or agreed worktree. Inspect changes before switching or synchronizing:

```bash
git status --short --branch
git branch --show-current
git remote -v
git fetch origin --no-tags
```

### Branch policy
- The only remote branches are `main`, `dev-hassan`, `dev-naveed`, and `dev-zaid`.
- Members open PRs from their own branch; only Hassan merges into `main` and teammate branches.
- Create temporary branches only if strictly necessary, and delete them before finishing. The 4 branches above are permanent.

For a new clone, after verifying the agreed starting point:

```bash
git clone https://github.com/Hassan092-prog/KNEXUS.git
cd KNEXUS
git switch --track origin/dev-hassan
```

Naveed uses `origin/dev-naveed`; Zaid uses `origin/dev-zaid`. If the local branch exists, switch without `--track`. Confirm `git config user.name` and `git config user.email`; use your own account and actual authorship.

## 2. Prepare the backend

Python 3.12 is the team baseline. Installation commands below are for an approved new personal environment. Reuse the working server environment. Run from the repository root.

Linux/macOS:

```bash
if [ ! -f .env ]; then cp .env.example .env; fi
python3.12 -m venv backend/venv
backend/venv/bin/python -m pip install -r backend/requirements.txt
```

Windows PowerShell:

```powershell
if (-not (Test-Path -LiteralPath .env)) {
    Copy-Item -LiteralPath .env.example -Destination .env
}
py -3.12 -m venv backend/venv
.\backend\venv\Scripts\python.exe -m pip install -r backend/requirements.txt
```

`Settings` resolves `.env` relative to the repository root, independently of the working directory. Exported variables override it. Restart after changes because settings are cached. Development defaults are unsuitable for public deployment.

`DATABASE_URL` is independent of `POSTGRES_*` fields; changing them does not rebuild it. Compose's default host port is 5435, container port 5432. Existing volumes retain initialization data when environment values change.

## 3. Run offline checks

Linux/macOS, from the root:

```bash
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 PYTHONPATH=backend backend/venv/bin/python -B -m pytest backend/tests -q -p no:cacheprovider
backend/venv/bin/python -B contracts/phase1/check.py
```

PowerShell:

```powershell
$env:HF_HUB_OFFLINE = "1"
$env:TRANSFORMERS_OFFLINE = "1"
$env:PYTHONPATH = "backend"
.\backend\venv\Scripts\python.exe -B -m pytest backend/tests -q -p no:cacheprovider
.\backend\venv\Scripts\python.exe -B contracts/phase1/check.py
```

These need no database, model service or downloads. The separate canonical checker proves contract invariants, not working APIs or model quality. See [backend tests](backend/tests/README.md) for database safeguards and recorded evidence.

## 4. Start a local API when needed

For an approved local PostgreSQL service:

```bash
docker compose up -d postgres
alembic -c alembic.ini upgrade head
python -c "import asyncio; from app.core.database import AsyncSessionLocal; from app.db.demo_seed import seed_demo_identity; async def s(): async with AsyncSessionLocal() as session: await seed_demo_identity(session); await session.commit(); asyncio.run(s())"
```

Start the backend:

```bash
PYTHONPATH=backend backend/venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

While the API is running:

```bash
curl --fail --max-time 10 http://127.0.0.1:8000/
curl --fail --max-time 10 http://127.0.0.1:8000/api/v1/health
```

## 5. Configure hosted APIs

Only the backend holds provider credentials and calls hosted APIs. Credentials stay in approved backend secret configuration or private `.env` on the server, never browser variables, Git, chat or logs.

The merged generation adapter recognizes `GENERATION_API_KEY`, `GENERATION_BASE_URL`, `GENERATION_MODEL`, and `GENERATION_TIMEOUT`, while hosted embedding recognizes `EMBEDDING_API_KEY`, `EMBEDDING_BASE_URL`, `EMBEDDING_MODEL_NAME`, and `EMBEDDING_DIMENSIONS`.

## 6. Frontend development

Zaid owns the frontend. The application lives in `frontend/app` (Vite + React 19).

To run the frontend:

```bash
cd frontend/app
npm ci
npm run dev
```

The frontend API base is `http://127.0.0.1:8000/api/v1`. The browser calls the backend, never hosted model APIs directly. Support `VITE_DATA_MODE=mock` and `VITE_DATA_MODE=live`. Keep mock mode visible; never substitute fixtures for live errors.

## 7. Review and integrate

Main contains the accepted baseline. Synchronize a clean member branch with `git fetch origin --no-tags` and a reviewed normal merge from `origin/main`.

Work in small owned slices. Inspect and stage named files. Commits, pushes, PRs and merges follow the branch policy: each member opens PRs from their own branch to `main`; only Hassan merges.

Inspect the staged diff and `git diff --cached --check`. Exclude secrets, uploads, large corpora, model weights, environments and caches. Never force-push persistent branches.

## Troubleshooting

| Symptom | Action |
|---|---|
| Environment changes ignored | Restart; exported variables override root `.env` |
| DB cannot connect | Verify explicit URL/host/port without printing credentials; ensure docker compose postgres is running |
| Application tables missing | Run `alembic -c alembic.ini upgrade head` from repository root |
| Foreign key error on upload | Seed demo identity with `seed_demo_identity` |
| Hosted access unavailable | Use mocks; agree provider/model, secure credentials and live-call approval |
| Upload/query returns 404 | Routes exist in main; check checkout, configured prefix and running process |
