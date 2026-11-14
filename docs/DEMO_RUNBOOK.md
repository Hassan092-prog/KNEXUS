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

> [!NOTE]
> **Status: Verified 2026-11-14 (server rehearsal: 12/12 demo questions, browser UI, upload of a 45-page PDF)**.

### 1. Environment Configuration (from config.py)
> [!IMPORTANT]
> API keys must be set only in the server environment or private `.env`. Keys come from a private env file (`chmod 600`) that is never committed or printed. Never commit API keys to version control.
```bash
# Database settings (from docker-compose.yml)
export POSTGRES_HOST="localhost"
export POSTGRES_PORT=5435
export POSTGRES_DB="knexus_demo"
export POSTGRES_USER="knexus_admin"
export POSTGRES_PASSWORD="knexus_password"
export DATABASE_URL="postgresql+asyncpg://knexus_admin:knexus_password@localhost:5435/knexus_demo"

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

# Live Provider Dispatch Opt-In
export LIVE_DISPATCH_ENABLED=true

# Generation pacing, budget and rate-limit cooldown (recommended free-tier values)
# Groq free tier enforces 8000 TPM; queries average ~2910 tokens (~2699 prompt + 211 completion).
# 60 / floor(8000 / avg_total_tokens) = 60 / 2 = 30s minimum interval to avoid 429 rate limit errors.
export GENERATION_MIN_INTERVAL_SECONDS=30.0
export GENERATION_MAX_PROMPT_CHARS=12000
export GENERATION_MAX_TOKENS=400
export QUOTA_RATE_LIMIT_COOLDOWN_SECONDS=60.0

# Ingestion token-counting and deadline optimization for large documents
# Bypasses remote countTokens when chunk UTF-8 bytes + overhead <= token ceiling; 45-page PDF drops from timing out at 30s to 11s
export TOKEN_COUNT_BYTE_BOUND_SKIP=true
# Extends per-document token validation deadline for large multi-page uploads
export EMBEDDING_VALIDATION_DEADLINE_SECONDS=180
# Preserves required >5s safety margin over longest provider deadline (180s) to prevent concurrent dispatches
export QUOTA_IN_FLIGHT_TIMEOUT_SECONDS=200

# CORS settings for browser LAN access
export BACKEND_CORS_ORIGINS='["http://localhost:5173", "http://127.0.0.1:5173", "http://192.168.1.92:5173", "http://192.168.1.92:5174", "http://localhost:5174", "http://127.0.0.1:5174"]'

# Demo Actor Role, Quota, Campaign and Module Resolution
export DEMO_ACTOR_ROLE="orgadmin"
export QUOTA_ENABLED=True
export QUOTA_CAMPAIGN_ID="phase1-demo-final-20261114b"
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

# 5. In a separate shell, start the frontend (port 5174 on this server)
cd frontend/app && VITE_API_BASE_URL=http://192.168.1.92:8002 VITE_DATA_MODE=live VITE_API_TIMEOUT_MS=90000 npx vite --host 0.0.0.0 --port 5174
```

### 3. Verification Queries
Upload demo documents and query through the frontend or via `POST /api/v1/query`. Verify that citations link to the real chunk and document UUIDs, and that ungrounded questions result in structured abstentions.

### 4. Known Phase 1 Limits
- **Scanned/image PDFs**: Scanned and image-only PDFs are rejected at upload with `400 Bad Request` / `INVALID_FILE` ("The document contains no extractable text"); no OCR in Phase 1; recommend saving from the authoring app as a text-searchable PDF or DOCX.
- **Provider rate limits**: ~30s minimum interval between questions on the Groq free tier to respect the 8,000 TPM limit.
- **Processing error detail**: Background document processing failures display a safe generic message in the UI; specific error causes are written only to backend server logs.
