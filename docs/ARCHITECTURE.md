# Architecture Document

> **Implementation status - 18 October 2026:** This document describes the target design and acceptance criteria. Only the backend scaffold, dependency health route, and PostgreSQL/pgvector bootstrap are implemented. See [REPOSITORY_REVIEW.md](REPOSITORY_REVIEW.md) for current behavior and known gaps. Code examples, proposed directories, tests, and migrations below are not evidence of completed work.

## KNEXUS: Knowledge Network for EXploration and Unified Services
**Version:** 1.0 | **Status:** Active | **Last Updated:** October 2026

---

## 1. System Overview

KNEXUS is a multi-layered AI knowledge platform. Its architecture is designed around three core principles:

1. **Privacy-first:** All AI inference runs locally via Ollama — document content is intended to stay within the configured local deployment. Initial package/model downloads require network access; provider URLs and network exposure must be reviewed.
2. **Security-by-design:** RBAC and multi-tenancy are enforced at the database layer, not the UI.
3. **Separation of concerns:** Each subsystem (Ingestion, Retrieval, Generation, Governance) is independently testable and replaceable.

---

## Current runtime

The implemented path is client -> FastAPI -> health handler -> PostgreSQL probes and Ollama `/api/tags`. CORS and cached settings are configured; no JWT middleware, RAG services, model loading, or schema creation runs on startup. Startup logs a message and shutdown disposes the database engine. Compose starts PostgreSQL only.

The diagrams and expanded directory tree below are **proposed**. Actual tracked source files are listed in [REPOSITORY_REVIEW.md](REPOSITORY_REVIEW.md).

## 2. High-Level Architecture (target)

```mermaid
graph TB
    subgraph Client["Client Layer"]
        UI["React + TypeScript SPA"]
    end

    subgraph Gateway["API Gateway"]
        API["FastAPI\n/api/v1/"]
        MW["JWT + RBAC Middleware"]
    end

    subgraph Services["Service Layer"]
        ING["Ingestion Service\n(PDF/DOCX → Chunks → Embeddings)"]
        RET["Retrieval Service\n(Query → Embed → pgvector ANN Search)"]
        GEN["Generation Service\n(Context + Prompt → Ollama → Answer)"]
        TOOL["Tool Execution Service\n(Registry + Approval + Audit)"]
    end

    subgraph Data["Data Layer"]
        PG["PostgreSQL 16\n+ pgvector"]
    end

    subgraph AI["AI Layer"]
        OLL["Ollama\n(Llama 3.2 / Mistral 7B)"]
        EMB["Embedding Model\n(all-MiniLM-L6-v2)"]
    end

    UI -->|HTTP / SSE| API
    API --> MW
    MW --> ING
    MW --> RET
    MW --> GEN
    MW --> TOOL
    ING -->|Store chunks + vectors| PG
    ING -->|Generate embeddings| EMB
    RET -->|ANN cosine search| PG
    RET -->|Query embedding| EMB
    GEN -->|Generate answer| OLL
    TOOL -->|Log execution| PG
```

---

## 3. Component Architecture

### 3.1 Document Ingestion Pipeline

```mermaid
sequenceDiagram
    actor User
    participant API as FastAPI
    participant ING as Ingestion Service
    participant PARSE as Document Parser
    participant CHUNK as Text Chunker
    participant EMBED as Embedding Model
    participant DB as PostgreSQL+pgvector

    User->>API: POST /api/v1/documents/upload (file, role_tags)
    API->>ING: Trigger background ingestion task
    API-->>User: 202 Accepted {task_id}
    ING->>PARSE: Extract text + metadata (pdfplumber / python-docx)
    PARSE-->>ING: Raw text + metadata
    ING->>CHUNK: Recursive character split (240 tokens, 32 overlap)
    CHUNK-->>ING: List of chunk objects
    ING->>EMBED: Encode chunks → vectors (all-MiniLM-L6-v2)
    EMBED-->>ING: Embedding vectors [384-dim]
    ING->>DB: INSERT INTO documents, document_chunks, embeddings
    ING->>DB: UPDATE ingestion_status = 'complete'
```

### 3.2 RAG Query Pipeline

```mermaid
sequenceDiagram
    actor User
    participant API as FastAPI
    participant AUTH as RBAC Middleware
    participant RET as Retrieval Service
    participant EMBED as Embedding Model
    participant DB as PostgreSQL+pgvector
    participant GEN as Generation Service
    participant OLL as Ollama

    User->>API: POST /api/v1/query {question}
    API->>AUTH: Verify JWT + extract user_id, org_id, role
    AUTH-->>API: Authorized context
    API->>RET: Retrieve(question, user_context)
    RET->>EMBED: Encode query → vector [384-dim]
    EMBED-->>RET: Query vector
    RET->>DB: ANN cosine search WHERE org_id=? AND role IN (allowed_roles) LIMIT 5
    DB-->>RET: Top-K chunks + similarity scores
    RET->>RET: Check max(similarity) < 0.35 → abstain
    RET-->>API: Retrieved chunks or ABSTAIN signal
    API->>GEN: Generate(question, chunks)
    GEN->>GEN: Assemble context-aware prompt with chunks
    GEN->>OLL: POST /api/generate (stream=true)
    OLL-->>GEN: Token stream
    GEN-->>User: SSE token stream with citations
    GEN->>DB: INSERT INTO audit_logs (query, answer, user_id, chunks_used)
```

### 3.3 Tool Execution & Approval Workflow

```mermaid
sequenceDiagram
    actor Employee
    actor Manager
    participant API as FastAPI
    participant REG as Tool Registry
    participant APPR as Approval Engine
    participant DB as PostgreSQL

    Employee->>API: POST /api/v1/actions/propose {tool: "create_task", payload: {...}}
    API->>REG: Validate tool exists in registry
    API->>REG: Validate employee has permission for tool
    REG-->>API: Authorized
    API->>APPR: Create proposal (payload_hash = SHA256(payload))
    APPR->>DB: INSERT INTO tool_proposals (payload, hash, proposed_by, expires_at)
    API-->>Employee: 202 Accepted {proposal_id}

    Manager->>API: GET /api/v1/actions/proposals (pending)
    API-->>Manager: List of pending proposals with diff view

    Manager->>API: POST /api/v1/actions/{proposal_id}/approve
    APPR->>APPR: Verify current_hash == stored_hash (tamper check)
    APPR->>APPR: Verify proposal not expired
    APPR->>REG: Execute tool(payload)
    REG-->>APPR: Execution result + post-condition verification
    APPR->>DB: INSERT INTO audit_logs (tool, proposed_by, approved_by, result)
    API-->>Manager: 200 OK {result}
```

---

## 4. Database Architecture

```mermaid
erDiagram
    ORGANIZATIONS {
        uuid id PK
        string name
        string slug
        timestamp created_at
    }

    USERS {
        uuid id PK
        uuid org_id FK
        string email
        string password_hash
        string role
        bool is_active
        timestamp created_at
    }

    DOCUMENTS {
        uuid id PK
        uuid org_id FK
        uuid uploaded_by FK
        string title
        string source_type
        string file_path
        jsonb allowed_roles
        string status
        timestamp created_at
    }

    DOCUMENT_CHUNKS {
        uuid id PK
        uuid document_id FK
        integer chunk_index
        text content
        integer token_count
        jsonb metadata
    }

    EMBEDDINGS {
        uuid id PK
        uuid chunk_id FK
        vector_384 embedding
    }

    AUDIT_LOGS {
        uuid id PK
        uuid user_id FK
        string action_type
        jsonb action_data
        timestamp created_at
    }

    TOOL_PROPOSALS {
        uuid id PK
        uuid proposed_by FK
        uuid approved_by FK
        string tool_name
        jsonb payload
        string payload_hash
        string status
        timestamp expires_at
        timestamp updated_at
    }

    ORGANIZATIONS ||--o{ USERS : "has"
    ORGANIZATIONS ||--o{ DOCUMENTS : "owns"
    USERS ||--o{ DOCUMENTS : "uploads"
    DOCUMENTS ||--o{ DOCUMENT_CHUNKS : "split into"
    DOCUMENT_CHUNKS ||--|| EMBEDDINGS : "has"
    USERS ||--o{ AUDIT_LOGS : "generates"
    USERS ||--o{ TOOL_PROPOSALS : "proposes/approves"
```

---

## 5. Proposed Directory Structure

```text
KNEXUS/
├── backend/
│   ├── app/
│   │   ├── main.py                   # FastAPI application entry point
│   │   ├── api/
│   │   │   └── v1/
│   │   │       ├── router.py         # Route aggregator
│   │   │       └── endpoints/
│   │   │           ├── health.py
│   │   │           ├── auth.py       # Login, refresh, logout
│   │   │           ├── documents.py  # Upload, list, delete
│   │   │           ├── query.py      # RAG query endpoint
│   │   │           └── actions.py    # Tool proposals & approvals
│   │   ├── core/
│   │   │   ├── config.py             # Pydantic settings
│   │   │   ├── database.py           # Async SQLAlchemy engine
│   │   │   └── security.py           # JWT, bcrypt utilities
│   │   ├── models/
│   │   │   ├── user.py
│   │   │   ├── document.py
│   │   │   ├── chunk.py
│   │   │   ├── embedding.py
│   │   │   ├── audit_log.py
│   │   │   └── tool_proposal.py
│   │   ├── schemas/                  # Pydantic request/response schemas
│   │   ├── services/
│   │   │   ├── ingestion/
│   │   │   │   ├── parser.py         # PDF/DOCX text extraction
│   │   │   │   ├── chunker.py        # Recursive character splitter
│   │   │   │   └── embedder.py       # Embedding generation
│   │   │   ├── retrieval/
│   │   │   │   ├── searcher.py       # pgvector ANN search
│   │   │   │   └── reranker.py       # Optional: cross-encoder rerank
│   │   │   ├── generation/
│   │   │   │   ├── ollama_client.py  # Ollama API wrapper
│   │   │   │   ├── prompt_builder.py # Context assembly + prompt templates
│   │   │   │   └── citation.py       # Citation extraction & formatting
│   │   │   └── tools/
│   │   │       ├── registry.py       # Tool registry
│   │   │       └── approval.py       # Approval workflow engine
│   │   ├── middleware/
│   │   │   └── rbac.py               # RBAC FastAPI dependency
│   │   └── utils/
│   │       └── logging.py
│   ├── alembic/                      # DB migration scripts
│   ├── tests/
│   │   ├── unit/
│   │   ├── integration/
│   │   └── evaluation/               # RAG benchmark harness
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── components/               # Reusable UI components
│   │   ├── pages/                    # Login, Chat, Admin, Approvals
│   │   ├── hooks/                    # Custom React hooks
│   │   ├── services/                 # API client functions
│   │   ├── context/                  # Auth context, role context
│   │   └── types/                    # TypeScript type definitions
│   ├── public/
│   ├── index.html
│   ├── vite.config.ts
│   └── package.json
│
├── data/
│   ├── samples/                      # Curated dataset samples
│   ├── evaluation/                   # 500-question QA benchmark
│   └── fixtures/                     # RBAC security test fixtures
│
├── docker/
│   └── init.sql                      # pgvector extension init
│
├── docs/                             # ← All documentation lives here
├── .env.example
├── .gitignore
├── docker-compose.yml
├── CONTRIBUTING.md
└── README.md
```

---

## 6. Planned Integration Points

### 6.1 Frontend ↔ Backend

| Flow | Method | Auth |
|---|---|---|
| Login | `POST /api/v1/auth/login` | None |
| Upload document | `POST /api/v1/documents/upload` | JWT + OrgAdmin role |
| Ask a question | `POST /api/v1/query` | JWT + any role |
| Stream answer | `GET /api/v1/query/stream/{session_id}` | JWT (SSE) |
| Propose action | `POST /api/v1/actions/propose` | JWT + Employee role |
| List pending approvals | `GET /api/v1/actions/proposals` | JWT + Manager role |
| Approve action | `POST /api/v1/actions/{id}/approve` | JWT + Manager role |

### 6.2 Backend ↔ Ollama

- Communication via HTTP REST (`httpx` async client)
- Endpoint: `POST http://localhost:11434/api/generate`
- Streaming: `stream: true` with chunk-by-chunk SSE relay
- Model config set via `OLLAMA_MODEL` environment variable

### 6.3 Backend ↔ Embedding Model

- Sentence Transformers loaded once at application startup
- Cached in memory for the process lifetime
- Alternatively: use Ollama's `/api/embeddings` endpoint for fully local operation

---

## 7. Target Deployment Architecture (Local/Development)

```mermaid
graph LR
    subgraph Docker["Docker (docker-compose)"]
        PG["knexus-postgres:5432\nPostgreSQL 16 + pgvector"]
    end

    subgraph Local["Local Machine"]
        BE["FastAPI Backend\nuvicorn :8000"]
        FE["React Dev Server\nvite :5173"]
        OLL["Ollama Service\n:11434"]
    end

    FE -->|"localhost:8000"| BE
    BE -->|"localhost:5435"| PG
    BE -->|"localhost:11434"| OLL
```

---

*KNEXUS Architecture v1.0 | MJCET CSE (AI&ML) | Team 3 | 2026–2027*
