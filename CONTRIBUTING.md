# KNEXUS contribution and local setup guide

## Scope and prerequisites

The current application is a backend scaffold. Read [README.md](README.md) and the [repository review](docs/REPOSITORY_REVIEW.md) before using the target designs as implementation instructions.

Use **Python 3.12** as the team baseline, Git, and Docker with Docker Compose. Node.js is only needed when the frontend is initialized. Ollama is optional for dependency diagnostics and will be required for future answer generation.

## Start from the repository root

```bash
git clone https://github.com/Hassan092-prog/KNEXUS.git
cd KNEXUS
```

Keep the process working directory here when starting the backend. `Settings` reads `.env` from the working directory, not from the Python module location. Do not overwrite an existing `.env` when repeating setup.

### Linux/macOS (POSIX shell)

```bash
if [ ! -f .env ]; then
    cp .env.example .env
fi
python3.12 -m venv backend/venv
backend/venv/bin/python -m pip install --upgrade pip
backend/venv/bin/python -m pip install -r backend/requirements.txt
docker compose up -d postgres
backend/venv/bin/python -m uvicorn app.main:app --app-dir backend --reload --host 127.0.0.1 --port 8000
```

### Windows PowerShell

```powershell
if (-not (Test-Path -LiteralPath .env)) {
    Copy-Item -LiteralPath .env.example -Destination .env
}
py -3.12 -m venv backend/venv
.\backend\venv\Scripts\python.exe -m pip install --upgrade pip
.\backend\venv\Scripts\python.exe -m pip install -r backend/requirements.txt
docker compose up -d postgres
.\backend\venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --reload --host 127.0.0.1 --port 8000
```

## Verify the scaffold

In another terminal at the repository root:

```bash
docker compose ps
curl http://localhost:8000/
curl http://localhost:8000/api/v1/health
```

In PowerShell use `Invoke-RestMethod http://localhost:8000/api/v1/health` if `curl` resolves to a PowerShell alias.

Open [Swagger](http://localhost:8000/docs), [ReDoc](http://localhost:8000/redoc), or [OpenAPI JSON](http://localhost:8000/api/v1/openapi.json). The application routes are `GET /` and `GET /api/v1/health`; document/query/auth/action endpoints do not exist yet.

The health response reports database connectivity, vector-extension presence, and Ollama `/api/tags` reachability. It always returns HTTP 200. Database exceptions set `status=degraded`; missing vector or unavailable Ollama currently do not. An online Ollama response does not prove the configured model is installed or can generate answers.

## Configuration and services

- Root `.env` defaults match Compose's host PostgreSQL port **5435**. The container listens on **5432**.
- Change `DATABASE_URL` explicitly when changing database credentials, host, port, or database name. The individual `POSTGRES_*` values do not construct this URL in the backend. `DATABASE_SYNC_URL` is reserved for future synchronous tooling.
- `BACKEND_CORS_ORIGINS` can be set as a JSON array in `.env`. The default includes local ports 3000 and 5173.
- Security/model settings are placeholders for planned features; changing `SECRET_KEY` does not enable authentication.
- Compose starts PostgreSQL only. Ollama's service block is commented out; API and frontend containers are absent.
- `docker/init.sql` runs only when PostgreSQL initializes an empty data volume. It enables `vector` and creates no application tables. No Alembic setup is committed.
- Existing volumes retain their users/passwords/database settings. Editing `.env` does not reinitialize a populated database.

Optional Ollama setup, in another terminal:

```bash
ollama serve
# In another terminal, if the model is wanted for future development:
ollama pull llama3.2
ollama list
```

Do not start a second Ollama server if a desktop/background service already owns port 11434. The health probe works without downloading a model.

To stop PostgreSQL while retaining its data:

```bash
docker compose stop postgres
```

## Troubleshooting

| Symptom | Check |
|---|---|
| Changes in `.env` have no effect | Launch from the repository root and restart the backend; settings are cached per process |
| Database connection error | Check `docker compose ps`, host port 5435, and `DATABASE_URL`; startup does not wait for readiness |
| Vector not installed | Inspect the existing database/volume and `docker/init.sql`; initialization scripts do not rerun on populated volumes |
| Ollama offline | Check its separate service and `OLLAMA_BASE_URL`; the rest of the scaffold still runs |
| `/query` or `/auth/login` returns 404 | These are planned API contracts, not implemented routes |

## Team ownership

Follow [TEAM_RESPONSIBILITIES.md](docs/TEAM_RESPONSIBILITIES.md): Hassan (Member 1) owns backend, database/migrations, data/runtime, security and integration. Naveed (Member 2) owns LLM/prompt/citation, typed tools and answer-quality work. Zaid (Member 3) owns the entire frontend, UI verification and user-facing documentation.

Hassan owns backend/Compose setup and database changes. Naveed sets up Ollama for generation work. Zaid sets up Node.js and frontend tooling when initializing the agreed React/TypeScript/Vite app; a frontend manifest/build command is not yet committed. Shared API changes are agreed before parallel implementation.

## Contribution workflow

Each member keeps one persistent branch and commits/pushes their work there: Hassan (Member 1) uses `dev-hassan`, Naveed (Member 2) uses `dev-naveed`, and Zaid (Member 3) uses `dev-zaid`. Each person should have their own clone. Do not commit directly to `main`.

**Hassan (Member 1):**

```powershell
git switch main
git pull --ff-only origin main
git switch -c dev-hassan
git push -u origin dev-hassan
```

**Naveed (Member 2):** run the same first two commands, then:

```powershell
git switch -c dev-naveed
git push -u origin dev-naveed
```

**Zaid (Member 3):** run the same first two commands, then:

```powershell
git switch -c dev-zaid
git push -u origin dev-zaid
```

Run your branch setup once, from your own clone. At the start of each work session, check the branch and sync merged work:

```bash
git status --short --branch
git branch --show-current
git fetch origin
git merge --no-edit origin/main
```

After a reviewable task, inspect and push named files:

```bash
git diff
git add path/to/changed-file
git diff --cached
git commit -m "feat(rag): add document chunking"
git push
```

Open one pull request at a time from your persistent branch into `main`. Use a merge commit (not squash/rebase) to preserve branch history for later PRs. Never force-push shared branches. Ignored files can still be force-added or tracked from earlier commits, so check staged changes for secrets, `.env`, model downloads, database files, and large datasets. Ask the repository admin to require PR review for `main`; do not require CI checks before a real workflow exists.

See [the team Git guide](docs/KNEXUS_Team_Git_Workflow_Guide.md) for setup and conflict commands and [the Phase 1 guide](docs/PHASE_1_TEAM_GUIDE.md) for member ownership, integration gates, and collaborative coding/prompt templates.
