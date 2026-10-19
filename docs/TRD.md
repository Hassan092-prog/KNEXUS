# TRD — Technical Requirements Document

> **Implementation status - 19 October 2026:** This document describes the target design and acceptance criteria. Only the backend scaffold, dependency health route, and PostgreSQL/pgvector bootstrap are implemented. See [REPOSITORY_REVIEW.md](REPOSITORY_REVIEW.md) for current behavior and known gaps. Code examples, proposed directories, tests, and migrations below are not evidence of completed work.

## KNEXUS: Knowledge Network for EXploration and Unified Services
**Version:** 1.0 | **Status:** Active | **Last Updated:** October 2026

---

## 1. Overview

This document specifies all technical requirements, technology choices, dependency constraints, and implementation standards for the KNEXUS system. It serves as the authoritative reference for the engineering team during implementation.

---

## 2. Technology Stack

### 2.1 Backend

| Component | Technology | Version | Justification |
|---|---|---|---|
| Language | Python | 3.12 (team baseline) | Ecosystem maturity for AI/ML, async support |
| Web Framework | FastAPI | ≥0.111 | Native async, automatic OpenAPI docs, Pydantic v2 |
| ASGI Server | Uvicorn + uvloop | ≥0.30 | High performance event loop |
| ORM | SQLAlchemy 2 (async) | ≥2.0.30 | Modern async ORM, Alembic migration support |
| Async DB Driver | asyncpg | ≥0.29 | PostgreSQL async driver, fastest available |
| Data Validation | Pydantic v2 | ≥2.7 | Settings management, request/response models |
| Task Queue | Background tasks (FastAPI) / Celery (P2) | — | Async document ingestion |

### 2.2 AI & Embeddings

| Component | Technology | Version | Justification |
|---|---|---|---|
| LLM Inference | Ollama | Latest | Local, private, no API cost |
| Default LLM Model | Llama 3.2 (`llama3.2`, 3B default) | — | Strong reasoning, low hardware requirements |
| Embedding Model | `all-MiniLM-L6-v2` (default) | — | 384-dim, fast, high quality for semantic search |
| Alt Embedding | `nomic-embed-text` via Ollama | — | Keeps entire stack local |
| Text Splitting | `langchain-text-splitters` | ≥0.2 | Battle-tested recursive character splitter |
| ML Library | `sentence-transformers` | ≥3.0 | HuggingFace embeddings, easy to swap models |

### 2.3 Database & Vector Store

| Component | Technology | Version | Justification |
|---|---|---|---|
| Primary DB | PostgreSQL | 16 | Stability, full SQL, pgvector support |
| Vector Extension | pgvector | ≥0.7 | Native vector storage and ANN search in Postgres |
| Vector Index | HNSW | — | Faster approximate search vs IVFFlat for small corpora |
| DB Migrations | Alembic | ≥1.13 | Schema evolution tracking |
| Container | `pgvector/pgvector:pg16` | Docker | pgvector pre-compiled, no manual setup |

### 2.4 Document Processing

| Component | Technology | Justification |
|---|---|---|
| PDF Extraction | `pdfplumber` | High accuracy, handles tables, preserves layout metadata |
| DOCX Extraction | `python-docx` | Native DOCX parser |
| Text Chunking | Recursive Character Splitter | Preserves sentence/paragraph boundaries |

### 2.5 Security & Auth

| Component | Technology | Justification |
|---|---|---|
| Auth Mechanism | JWT (access + refresh tokens) | Stateless, scalable, standard |
| Password Hashing | bcrypt via `passlib` | Industry-standard slow hash |
| Token Library | `python-jose[cryptography]` | JWT sign/verify |
| RBAC Enforcement | SQLAlchemy query filters | Server-side, unforgeable |

### 2.6 Frontend

| Component | Technology | Version | Justification |
|---|---|---|---|
| Framework | React | 18+ | Mature, component-based, large ecosystem |
| Language | TypeScript | 5+ | Type safety, refactoring confidence |
| Build Tool | Vite | Latest | Fast HMR, optimized builds |
| Styling | Vanilla CSS / CSS Modules | — | No external framework dependency |
| API Client | `axios` / `fetch` | — | REST API consumption |
| Streaming | Server-Sent Events (SSE) | — | Real-time LLM token streaming |

### 2.7 Infrastructure & DevOps

| Component | Technology | Justification |
|---|---|---|
| Container Runtime | Docker + Docker Compose | Single-command local stack setup |
| CI/CD | GitHub Actions | Native GitHub integration, free for academic use |
| Code Quality | Ruff (linter + formatter) | Fast, replaces flake8 + isort + black |
| Testing | pytest + pytest-asyncio | Async test support for FastAPI endpoints |
| API Testing | httpx (async test client) | FastAPI's recommended test client |

---

## 3. Architecture Requirements

### 3.1 Layered Architecture

```
┌─────────────────────────────────────────────────────┐
│                 Presentation Layer                   │
│         React + TypeScript (Vite SPA)               │
└───────────────────────┬─────────────────────────────┘
                        │ HTTP / SSE
┌───────────────────────▼─────────────────────────────┐
│                   API Gateway Layer                  │
│      FastAPI + CORS + JWT Middleware + RBAC          │
└────────────┬──────────────────────────┬─────────────┘
             │                          │
┌────────────▼────────┐   ┌─────────────▼─────────────┐
│  RAG Service Layer  │   │  Tool Execution Layer      │
│  - Ingestion        │   │  - Tool Registry           │
│  - Embedding        │   │  - Approval Engine         │
│  - Retrieval        │   │  - Post-condition Verify   │
│  - Generation       │   │  - Execution Audit         │
└────────────┬────────┘   └─────────────┬─────────────┘
             │                          │
┌────────────▼──────────────────────────▼─────────────┐
│                  Data Layer                          │
│  PostgreSQL 16 + pgvector                            │
│  Tables: organizations, users, documents, chunks,      │
│          embeddings, audit_logs, tool_proposals     │
└─────────────────────────────────────────────────────┘
             │
┌────────────▼────────────────┐
│  Local LLM Layer (Ollama)   │
│  Llama 3.2 / Mistral 7B     │
└─────────────────────────────┘
```

### 3.2 API Design Standards

- All REST endpoints versioned under `/api/v1/`
- Request and response bodies use **Pydantic v2 models**
- Proposed endpoint-specific responses follow [API_SPEC.md](API_SPEC.md), including list pagination. The following generic envelope is an optional future proposal, not the current or agreed wire contract:
  ```json
  {
    "data": { "example": "value" },
    "meta": { "request_id": "uuid", "timestamp": "iso8601" },
    "error": null
  }
  ```
- Authentication via `Authorization: Bearer <jwt>` header
- Pagination via `?limit=<N>&offset=<N>` query params
- Planned errors follow the `detail`, `code`, `request_id` shape in API_SPEC.md; the scaffold uses FastAPI defaults. RFC 7807 is not the selected contract.

### 3.3 Asynchronous Processing

- Document ingestion MUST be async — upload returns immediately with a `task_id`
- Embedding generation runs in the background via FastAPI BackgroundTasks (Phase 1) or Celery (Phase 2)
- LLM streaming responses use SSE (`text/event-stream`)
- All database calls MUST use async SQLAlchemy sessions

---

## 4. Data Requirements

### 4.1 Chunk Configuration

| Parameter | Value | Rationale |
|---|---|---|
| Chunk size | Up to 240 model tokens | Leaves room under the default MiniLM 256-wordpiece limit; count with its tokenizer |
| Chunk overlap | 32 model tokens | Preserves sentence continuity across chunk boundaries |
| Splitter type | Recursive character splitter | Respects paragraph → sentence → word hierarchy |
| Embedding dimensions | 384 (MiniLM) / 768 (nomic) | Model-dependent; stored as pgvector `vector(384)` |

The [default embedding model card](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2) specifies truncation above 256 wordpieces. The proposed 240-token chunk budget and 32-token overlap replace the earlier 512/50 proposal to fit this limit. The chunker must count with the embedding tokenizer, including special tokens, and test against the runtime model limit. Whitespace counts and character splitter sizes are not token counts. Larger chunks require a suitable model. Switching to 768-dimensional embeddings requires a schema/index migration and re-embedding; `model_name` alone does not make `vector(384)` compatible.

### 4.2 Vector Index

| Parameter | Value | Rationale |
|---|---|---|
| Index type | HNSW | Faster query time vs IVFFlat for ≤100k vectors |
| Distance metric | Cosine similarity | Standard for semantic search |
| `ef_construction` | 64 (default) | Build-time accuracy/speed tradeoff |
| `m` | 16 (default) | Graph connectivity parameter |

### 4.3 Retrieval Configuration

| Parameter | Value |
|---|---|
| Top-K chunks retrieved | 5 (default, configurable) |
| Abstention threshold | Cosine similarity < 0.35 |
| Max context tokens | 3,072 (configurable per model) |

---

## 5. Security Requirements

### 5.1 Authentication

- JWT access tokens expire in **120 minutes**
- Refresh tokens expire in **7 days**
- All tokens signed with HMAC-SHA256 (`SECRET_KEY` in `.env`)
- Passwords hashed with **bcrypt** (work factor ≥ 12)

### 5.2 RBAC Enforcement

- Role hierarchy: `SuperAdmin > OrgAdmin > Manager > Employee`
- RBAC enforced at the **SQLAlchemy query layer** using `org_id` and `allowed_roles` filters
- The frontend NEVER controls access logic — it is purely cosmetic
- Tenant isolation: all queries include `WHERE org_id = :current_user_org_id`

### 5.3 Tool Execution Safety

- All tools must be explicitly registered in the `ToolRegistry` before they can be invoked
- Action payloads are SHA-256 hashed at proposal time; execution is blocked if hash doesn't match
- Approval expiry enforced server-side (default: 1 hour)

### 5.4 Prompt Injection Mitigation

- System prompt is constructed server-side; user input is never interpolated directly into the instruction portion
- Retrieved context is clearly delimited from the user query using structural markers
- LLM is instructed to only answer from provided context

---

## 6. Testing Requirements

| Test Type | Scope | Tooling | Target Coverage |
|---|---|---|---|
| Unit Tests | Individual service functions | pytest | ≥ 80% on service layer |
| Async API Tests | FastAPI endpoint contracts | pytest + httpx | All P0 endpoints |
| Integration Tests | DB → Service → API | pytest with real DB | Core user journeys |
| RBAC Tests | Access control enforcement | Custom fixture suite | 100% — all role combinations |
| RAG Evaluation | Retrieval + citation quality | Custom eval harness | 500-question benchmark |
| Security Tests | Injection, tenant leakage | Custom synthetic fixtures | All 6 security scenarios |
| Load Tests | Concurrent user handling | Locust | 20 concurrent users |

---

## 7. Performance Budgets

| Operation | P50 Latency | P95 Latency | Measurement Method |
|---|---|---|---|
| Document ingestion (PDF, 10 pages) | < 3s | < 8s | Timed ingestion jobs |
| Semantic search (cosine, top-5) | < 100ms | < 300ms | DB query timing |
| Query-to-first-token (including retrieval) | <= 5s | <= 8s | Client to first SSE token |
| End-to-end query | < 6s | < 12s | Client-measured |
| Auth (login) | < 200ms | < 500ms | API response time |

---

## 8. Code Quality Standards

```toml
# Proposed pyproject.toml configuration (not committed)
[tool.ruff]
line-length = 100
target-version = "py312"
[tool.ruff.lint]
select = ["E", "F", "I", "UP", "S"]  # pycodestyle, pyflakes, isort, pyupgrade, bandit
```

- All Python files formatted with `ruff format`
- Imports sorted with `ruff check --select I`
- Type annotations required on all function signatures
- Docstrings required on all public modules, classes, and functions
- No `print()` statements in production code — use `logging`

---

## 9. Environment Variables Reference

All current settings have development defaults, so none is syntactically required to import the scaffold. `DATABASE_URL` and `OLLAMA_BASE_URL` drive health checks. `POSTGRES_*` values configure Compose but do not rebuild the backend URL. Auth, embedding, and generation values are reserved for unimplemented services. Root `.env` resolves from the working directory; use CONTRIBUTING.md's root-based launch command. The Required column below describes target deployment policy.

`APP_NAME`, `API_V1_PREFIX`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `DATABASE_SYNC_URL`, `ALGORITHM`, and `BACKEND_CORS_ORIGINS` are also declared in `backend/app/core/config.py`. CORS overrides use a JSON array. That file and `.env.example` define current settings.

| Variable | Required | Default | Description |
|---|---|---|---|
| `APP_ENV` | Yes | `development` | Environment mode |
| `DEBUG` | No | `True` | SQLAlchemy echo, verbose logging |
| `DATABASE_URL` | Yes | — | Async PostgreSQL connection string |
| `POSTGRES_PORT` | No | `5435` | Exposed DB port (avoids conflicts) |
| `SECRET_KEY` | Yes | (dev key) | JWT signing secret |
| `OLLAMA_BASE_URL` | Yes | `http://localhost:11434` | Ollama API endpoint |
| `OLLAMA_MODEL` | No | `llama3.2` | Default generation model |
| `EMBEDDING_MODEL_NAME` | No | `all-MiniLM-L6-v2` | HuggingFace embedding model ID |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | No | `120` | JWT expiry in minutes |

---

*KNEXUS TRD v1.0 | MJCET CSE (AI&ML) | Team 3 | 2026–2027*
