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
cp .env.example .env
python3.12 -m venv backend/venv
backend/venv/bin/python -m pip install --upgrade pip
backend/venv/bin/python -m pip install -r backend/requirements.txt
docker compose up -d postgres
backend/venv/bin/python -m uvicorn app.main:app --app-dir backend --reload --host 127.0.0.1 --port 8000
```

### Windows PowerShell

```powershell
Copy-Item .env.example .env
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

## Contribution workflow

Use short-lived `feat/<member>-<feature>`, `fix/<member>-<bug>`, or `docs/<member>-<topic>` branches and pull requests into `main`. Persistent member branches are optional coordination branches, described in the [workflow guide](docs/KNEXUS_Team_Git_Workflow_Guide.md).

```bash
git switch main
git pull --ff-only origin main
git switch -c feat/yourname-feature
# Make changes, inspect git diff, and run applicable checks.
git add path/to/changed-file
git commit -m "feat(rag): add document chunking"
git push -u origin feat/yourname-feature
```

Review staged changes for secrets and generated data. `.gitignore` is a convenience, not secret detection. Do not commit `.env`, virtual environments, model downloads, database files, or full datasets. No automated test suite or CI pipeline is committed yet; describe manual checks honestly and add relevant tests with new application behavior. Ruff is planned but is not installed by `requirements.txt`.

See the [project plan](docs/KNEXUS_Project_Plan.md) for ownership and the [documentation index](docs/INDEX.md) for design references.
