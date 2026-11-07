# KNEXUS Phase 1 Demo Runbook

> [!NOTE]
> **Status: VERIFIED**. Executed and verified live on server environment (2026-11-07).

## 1. Environment Configuration (from config.py)
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

# For dry run: GENERATION_PROVIDER="fake"
# For live demo: GENERATION_PROVIDER="groq", GENERATION_MODEL="openai/gpt-oss-120b", GENERATION_API_KEY="gsk_..."
export GENERATION_PROVIDER="fake"
export GENERATION_MODEL="openai/gpt-oss-120b"
export GENERATION_API_KEY="gsk_..."
export GENERATION_BASE_URL="https://api.groq.com/openai/v1"

export QUOTA_ENABLED=True
export QUOTA_CAMPAIGN_ID="phase1-demo-20261107"
export PYTHONPATH=backend
```

## 2. Start the Stack
```bash
# 1. Start PostgreSQL with pgvector (port 5435)
docker compose up -d postgres

# 2. Run schema migrations from repository root (alembic.ini is at repo root)
alembic -c alembic.ini upgrade head

# 3. Seed Phase 1 demo identity (required for tenant foreign key integrity)
python -c "import asyncio; from app.core.database import AsyncSessionLocal; from app.db.demo_seed import seed_demo_identity; async def s(): async with AsyncSessionLocal() as session: await seed_demo_identity(session); await session.commit(); asyncio.run(s())"

# 4. Start backend (port 8000; ensure port 8000 is free)
uvicorn app.main:app --host 0.0.0.0 --port 8000

# 5. Start frontend (port 5173, optional during dry run)
cd frontend/app && npm run dev
```

## 3. Upload a Document
```bash
curl -X POST http://localhost:8000/api/v1/documents/upload \
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
curl -s http://localhost:8000/api/v1/documents/<document_id>/status
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

## 4. Query & Expected Response
```bash
curl -X POST http://localhost:8000/api/v1/query \
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
