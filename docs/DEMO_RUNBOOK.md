# KNEXUS Phase 1 Demo Runbook

> [!WARNING]
> **Status: UNVERIFIED**. This runbook remains unverified until executed live.

## 1. Environment Configuration (from config.py)
`ash
export POSTGRES_HOST="localhost" POSTGRES_PORT=5435
export POSTGRES_DB="knexus" POSTGRES_USER="knexus_admin" POSTGRES_PASSWORD="knexus_password"
export DATABASE_URL="postgresql+asyncpg://knexus_admin:knexus_password@localhost:5435/knexus"
export EMBEDDING_PROVIDER="local" EMBEDDING_MODEL_NAME="sentence-transformers/all-MiniLM-L6-v2"
export EMBEDDING_DIMENSIONS=384
export GENERATION_PROVIDER="groq" GENERATION_MODEL="llama-3.3-70b-versatile"
export GENERATION_API_KEY="gsk_..." GENERATION_BASE_URL="https://api.groq.com/openai/v1"
export QUOTA_ENABLED=True QUOTA_CAMPAIGN_ID="phase1-demo-20261107"
`

## 2. Start the Stack
`ash
docker compose up -d db                              # 1. Start PostgreSQL (port 5435)
cd backend && alembic upgrade head                   # 2. Run migrations
uvicorn app.main:app --host 0.0.0.0 --port 8000      # 3. Start backend (port 8000)
cd frontend/app && npm run dev                       # 4. Start frontend (port 5173)
`

## 3. Upload a Document
`ash
curl -X POST http://localhost:8000/api/v1/documents/upload \
  -F "file=@sample.pdf" -F "allowed_roles=employee"
# Returns HTTP 202 with document_id and job_id. Poll status until completed:
curl -s http://localhost:8000/api/v1/documents/<document_id>/status
`

## 4. Query & Expected Response
`ash
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the warranty period?", "top_k": 3}'
`
Correct response contains inline bracketed citations matching citation objects:
`json
{
  "answer": "The warranty period is 12 months from delivery [1].",
  "citations": [{"citation_id": 1, "document_id": "...", "chunk_id": "...", "snippet": "..."}],
  "abstained": false, "abstention_reason": null
}
`
