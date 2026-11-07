# KNEXUS Project Status

**Updated: 7 November 2026**

## What Works Now
- **Contracts & Validation**: Canonical Pydantic contracts (contracts/phase1/models.py), schema export, and negative contract test suite.
- **Persistence**: PostgreSQL 16 + pgvector schema (6 tables, Alembic migrations, 384-dimensional HNSW cosine index).
- **Ingestion & Retrieval**: PDF/DOCX parsing, tokenizer-bounded chunking, source tracking, and tenant/role-filtered similarity retrieval with fail-closed model isolation.
- **Embeddings**: Local MiniLM (sentence-transformers/all-MiniLM-L6-v2, 384-d) fully operational for ingestion and query vectors.
- **Generation & Safety**: Async GenerationService supporting Groq hosted generation (openai/gpt-oss-120b) and offline fake provider; fail-closed BlockedLiveDispatchPolicy and cross-process atomic QuotaLedger.
- **API Endpoints**: Document upload, listing, status polling, and non-streaming query endpoints with UTC timestamps and canonical error envelopes.
- **Frontend**: Vite + React 19 UI in rontend/app merged on origin/main (PR #23) with overview, documents, and chat views.
- **Verification**: Offline test suite (358 passed, 18 skipped); contract checker passes.

## Phase 1 Demo Architecture Decision
- **Embeddings**: Local MiniLM (sentence-transformers/all-MiniLM-L6-v2, vector(384)).
- **Generation**: Groq hosted provider (openai/gpt-oss-120b).
- **Google Embedder**: Present in codebase (pp/services/ingestion/google_embedder.py), verified offline, but disabled (EMBEDDING_PROVIDER="local") for the Phase 1 demo to preserve existing 384-d vectors and zero-cost operation.

## 4-Step Plan to Phase 1 Demo
1. **Merge PR #15**: Integrate Naveed's generation harness and adapter corrections into main.
2. **Merge PR #21**: Fast-forward and merge Hassan's generation wiring, quota ledger, and UTC normalization into main.
3. **Frontend Endpoint Wiring**: Connect Zaid's frontend (rontend/app) to backend upload and query REST endpoints.
4. **Live Smoke Acceptance**: Execute docs/DEMO_RUNBOOK.md with synthetic document upload, query verification, and citation check.

## Open Items & Ownership
- **Hassan**: PR #21 merge readiness, stack startup, and live runbook verification.
- **Naveed**: PR #15 merge readiness and generation handoff sign-off.
- **Zaid**: Frontend API integration and browser citation display against live backend.
