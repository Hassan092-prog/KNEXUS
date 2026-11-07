# KNEXUS Phase 1 Demo Runbook

> [!NOTE]
> Switching `EMBEDDING_PROVIDER` requires a fresh demo database or re-ingesting all documents, because vectors are tagged by embedding model name and revision in `document_chunks`. Chunks produced by other models are never scored or mixed into similarity rankings.

> [!IMPORTANT]
> The backend port is configurable. The demo default on this server is **8002** (to avoid collisions with other host services on 8000). Set `VITE_API_BASE_URL=http://localhost:8002` for the frontend to match.

---

## Part 1: Local Test Mode (Verified)

> [!NOTE]
> **Status: VERIFIED**. Executed and verified live on server environment (2026-11-07).

### 1. Environment Configuration
```bash
export POSTGRES_HOST="localhost"
export POSTGRES_PORT=5435
export POSTGRES_DB="knexus"
export POSTGRES_USER="knexus_admin"
export POSTGRES_PASSWORD="knexus_password"
export DATABASE_URL="postgresql+asyncpg://knexus_admin:knexus_password@localhost:5435/knexus"

export EMBEDDING_PROVIDER="local"
export EMBEDDING_MODEL_NAME="sentence-transformers/all-MiniLM-L6-v2"
export EMBEDDING_DIMENSIONS=384

export GENERATION_PROVIDER="fake"

export DEMO_ACTOR_ROLE="orgadmin"
export QUOTA_ENABLED=True
export QUOTA_CAMPAIGN_ID="phase1-demo-20261107"
export PYTHONPATH=backend
```

### 2. Start the Stack
```bash
# 1. Start PostgreSQL with pgvector (port 5435)
docker compose up -d postgres

# 2. Run schema migrations from repository root (alembic.ini is at repo root)
alembic -c alembic.ini upgrade head

# 3. Seed Phase 1 demo identity (required for tenant foreign key integrity)
python -m app.db.demo_seed

# 4. Start backend (port 8002 default on this server)
uvicorn app.main:app --host 0.0.0.0 --port 8002

# 5. Start frontend (port 5173, optional during dry run)
cd frontend/app && VITE_API_BASE_URL=http://localhost:8002 npm run dev
```

### 3. Upload a Document
```bash
curl -X POST http://localhost:8002/api/v1/documents/upload \
  -F "file=@demo_security_policy.docx" \
  -F "allowed_roles=employee"
```
Returns HTTP 202 with `document_id` and `task_id`:
```json
{
  "document_id": "c1dc7ffc-f9e0-4d88-9093-9b268d0c6d8c",
  "task_id": "628129de-ee2d-49d8-a3a0-8fab582c9b6a",
  "status": "queued",
  "message": "Upload accepted for processing."
}
```

Poll status until `status` becomes `complete`:
```bash
curl -s http://localhost:8002/api/v1/documents/<document_id>/status
```
Expected completed response:
```json
{
  "document_id": "c1dc7ffc-f9e0-4d88-9093-9b268d0c6d8c",
  "status": "complete",
  "chunks_processed": 3,
  "total_chunks": 3,
  "progress_percent": 100,
  "failure_code": null,
  "failure_message": null
}
```

### 4. Query & Expected Response
```bash
curl -X POST http://localhost:8002/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"question": "How often is the security policy reviewed?", "top_k": 3}'
```
Response contains inline bracketed citations matching citation objects referencing the uploaded document:
```json
{
  "answer": "Fixture response for supplied evidence [1].",
  "citations": [
    {
      "id": 1,
      "chunk_id": "d94012c8-401b-5db0-9d30-8f108d851e6d",
      "document_id": "c1dc7ffc-f9e0-4d88-9093-9b268d0c6d8c",
      "document_title": "demo_security_policy",
      "chunk_index": 2,
      "page": null,
      "excerpt": "from the designated security authority...",
      "similarity_score": 0.534
    }
  ],
  "abstained": false,
  "abstention_reason": null,
  "session_id": "1e88e13f-2a43-41d7-baa6-0436a440b100",
  "meta": {
    "retrieval_time_ms": 177.7,
    "generation_time_ms": 0.25,
    "model": "fake"
  }
}
```

### 5. Role-Based Evaluation Runner
To run the automated demo test suite against the running backend:
```bash
# Run orgadmin questions (uploads demo corpus)
python backend/scripts/run_demo.py --base-url http://localhost:8002 --actor-role orgadmin --upload

# To run employee question group: restart backend with DEMO_ACTOR_ROLE=employee
export DEMO_ACTOR_ROLE="employee"
uvicorn app.main:app --host 0.0.0.0 --port 8002

# Run employee questions
python backend/scripts/run_demo.py --base-url http://localhost:8002 --actor-role employee
```

---

## Part 2: Live Demo Mode (Hosted Providers)

> [!WARNING]
> **Status: UNVERIFIED**. Live demo mode requires approved server-held API credentials and has not yet been executed end-to-end live.

### 1. Environment Configuration (from config.py)
> [!IMPORTANT]
> API keys must be set only in the server environment or private `.env`. Never commit API keys to version control.
```bash
# Database settings (from docker-compose.yml)
export POSTGRES_HOST="localhost"
export POSTGRES_PORT=5435
export POSTGRES_DB="knexus"
export POSTGRES_USER="knexus_admin"
export POSTGRES_PASSWORD="knexus_password"
export DATABASE_URL="postgresql+asyncpg://knexus_admin:knexus_password@localhost:5435/knexus"

# Google Hosted Embeddings (gemini-embedding-001 at 384 dimensions)
export EMBEDDING_PROVIDER="google"
export EMBEDDING_MODEL_NAME="gemini-embedding-001"
export EMBEDDING_DIMENSIONS=384
export EMBEDDING_API_KEY="AIza..."

# Groq Hosted Generation (openai/gpt-oss-120b)
export GENERATION_PROVIDER="groq"
export GENERATION_MODEL="openai/gpt-oss-120b"
export GENERATION_API_KEY="gsk_..."
export GENERATION_BASE_URL="https://api.groq.com/openai/v1"

# Demo Actor Role, Quota, Campaign and Module Resolution
export DEMO_ACTOR_ROLE="orgadmin"
export QUOTA_ENABLED=True
export QUOTA_CAMPAIGN_ID="phase1-live-demo-20261107"
export PYTHONPATH=backend
```

### 2. Execution Steps
```bash
# 1. Start PostgreSQL (port 5435)
docker compose up -d postgres

# 2. Run migrations
alembic -c alembic.ini upgrade head

# 3. Seed Phase 1 demo identity
python -m app.db.demo_seed

# 4. Start backend (port 8002)
uvicorn app.main:app --host 0.0.0.0 --port 8002

# 5. In a separate shell, start the frontend
cd frontend/app && VITE_API_BASE_URL=http://localhost:8002 VITE_DATA_MODE=live npm run dev
```

### 3. Verification Queries
Upload demo documents and query through the frontend or via `POST /api/v1/query`. Verify that citations link to the real chunk and document UUIDs, and that ungrounded questions result in structured abstentions.
