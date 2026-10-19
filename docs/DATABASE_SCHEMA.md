# Database Schema Design

> **Implementation status - 19 October 2026:** This document describes the target design and acceptance criteria. Only the backend scaffold, dependency health route, and PostgreSQL/pgvector bootstrap are implemented. See [REPOSITORY_REVIEW.md](REPOSITORY_REVIEW.md) for current behavior and known gaps. Code examples, proposed directories, tests, and migrations below are not evidence of completed work.

> **Delivery ownership:** Hassan owns all database models, Alembic migrations, tenant constraints, vector storage and data/runtime integration. Zaid owns frontend data presentation rather than database implementation. Follow [TEAM_RESPONSIBILITIES.md](TEAM_RESPONSIBILITIES.md) for member and file ownership.

## KNEXUS: Knowledge Network for EXploration and Unified Services
**Version:** 1.0 | **Engine:** PostgreSQL 16 + pgvector | **Last Updated:** October 2026

---

## Current database bootstrap

`docker/init.sql` only runs `CREATE EXTENSION IF NOT EXISTS vector;` on first initialization of an empty PostgreSQL volume. No application models/tables, HNSW indexes, Alembic configuration, or revisions are committed. All SQL below is a draft, not an applied migration.

Before implementing this schema:

- Separate the migration owner from a least-privilege runtime role. Compose's `POSTGRES_USER` is the bootstrap administrator; it cannot provide immutable audit guarantees for the application.
- Add composite tenant foreign keys/unique constraints so uploaders, documents, chunks, embeddings, proposers, and approvers cannot reference parents from another organization. Independent UUID foreign keys plus duplicated `org_id` do not enforce this.
- Synchronize denormalized embedding permissions transactionally with document permissions; re-check parent document authorization during retrieval to avoid stale-access leakage.
- Add unique chunk positions per document, embedding uniqueness/version rules, non-null lifecycle fields, execution timestamps, idempotency, and verification state before approval workflows are built.
- The proposal has one role/org per user and no persisted refresh sessions, conversation history, or sandbox task table. These need explicit schema decisions.

## 1. Overview (target)

The KNEXUS database is the single source of truth for all data: users, documents, vector embeddings, audit logs, and tool execution records. It uses **PostgreSQL 16** with the **pgvector** extension for vector storage and similarity search.

---

## 2. Schema Design Principles

1. **UUIDs as primary keys** — All tables use UUID v4 PKs for distributed compatibility.
2. **Multi-tenancy by `org_id`** — Every data table includes `org_id` as a filter column; all queries MUST include this filter.
3. **Append-only audit logs** — The `audit_logs` table must deny UPDATE/DELETE to the runtime database role as well as enforcing append-only application behavior.
4. **Soft deletes** — Documents use an `is_deleted` flag rather than hard deletion to preserve audit trail integrity.
5. **JSONB for flexible metadata** — Document metadata, chunk metadata, and action payloads use JSONB for schema-less extensibility.

---

## 3. Tables

### 3.1 `organizations`

```sql
CREATE TABLE organizations (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        VARCHAR(255) NOT NULL,
    slug        VARCHAR(100) NOT NULL UNIQUE,
    is_active   BOOLEAN DEFAULT TRUE,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);
```

| Column | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `name` | VARCHAR(255) | Display name |
| `slug` | VARCHAR(100) | URL-safe unique identifier |
| `is_active` | BOOLEAN | Soft disable without deletion |

---

### 3.2 `users`

```sql
CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    email           VARCHAR(320) NOT NULL UNIQUE,
    password_hash   VARCHAR(255) NOT NULL,
    full_name       VARCHAR(255),
    role            VARCHAR(50) NOT NULL CHECK (
                        role IN ('superadmin', 'orgadmin', 'manager', 'employee')
                    ),
    is_active       BOOLEAN DEFAULT TRUE,
    last_login_at   TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_users_org_id ON users(org_id);
CREATE INDEX idx_users_email ON users(email);
```

| Column | Type | Notes |
|---|---|---|
| `role` | VARCHAR(50) | Enforced by CHECK constraint |
| `is_active` | BOOLEAN | Deactivate without deleting user data |

---

### 3.3 `documents`

```sql
CREATE TABLE documents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    uploaded_by     UUID NOT NULL REFERENCES users(id),
    title           VARCHAR(512) NOT NULL,
    source_type     VARCHAR(20) NOT NULL CHECK (source_type IN ('pdf', 'docx', 'txt')),
    original_filename VARCHAR(512),
    file_path       TEXT,
    allowed_roles   JSONB NOT NULL DEFAULT '["employee"]',
    status          VARCHAR(20) NOT NULL DEFAULT 'queued'
                        CHECK (status IN ('queued', 'processing', 'complete', 'failed')),
    chunk_count     INTEGER DEFAULT 0,
    description     TEXT,
    metadata        JSONB DEFAULT '{}',
    is_deleted      BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_documents_org_id ON documents(org_id);
CREATE INDEX idx_documents_status ON documents(status);
CREATE INDEX idx_documents_allowed_roles ON documents USING GIN(allowed_roles);
```

| Column | Type | Notes |
|---|---|---|
| `allowed_roles` | JSONB | e.g. `["manager", "orgadmin"]` |
| `status` | VARCHAR | Ingestion lifecycle state |
| `metadata` | JSONB | Author, page count, extracted dates, etc. |
| `is_deleted` | BOOLEAN | Soft delete flag |

---

### 3.4 `document_chunks`

```sql
CREATE TABLE document_chunks (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id     UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    org_id          UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    chunk_index     INTEGER NOT NULL,
    content         TEXT NOT NULL,
    token_count     INTEGER,
    char_count      INTEGER,
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_chunks_document_id ON document_chunks(document_id);
CREATE INDEX idx_chunks_org_id ON document_chunks(org_id);
```

| Column | Type | Notes |
|---|---|---|
| `chunk_index` | INTEGER | Zero-based position in document |
| `content` | TEXT | Raw chunk text |
| `metadata` | JSONB | Page number, section title, source location |

---

### 3.5 `embeddings`

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE embeddings (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chunk_id        UUID NOT NULL REFERENCES document_chunks(id) ON DELETE CASCADE,
    org_id          UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    document_id     UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    allowed_roles   JSONB NOT NULL DEFAULT '["employee"]',
    embedding       vector(384) NOT NULL,
    model_name      VARCHAR(100) NOT NULL DEFAULT 'all-MiniLM-L6-v2',
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- HNSW vector index for fast approximate nearest neighbor search
CREATE INDEX idx_embeddings_hnsw
    ON embeddings
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- Index for multi-tenant + role filtering
CREATE INDEX idx_embeddings_org_id ON embeddings(org_id);
CREATE INDEX idx_embeddings_roles ON embeddings USING GIN(allowed_roles);
```

> [!IMPORTANT]
> The `allowed_roles` and `org_id` columns on the `embeddings` table are **denormalized from the parent document** intentionally. This allows a single SQL query to filter by tenant + role + vector similarity without expensive JOINs during retrieval — critical for latency.

| Column | Type | Notes |
|---|---|---|
| `embedding` | `vector(384)` | 384-dim float vector (MiniLM) |
| `model_name` | VARCHAR | Enables future re-embedding with a different model |

---

### 3.6 `audit_logs`

```sql
CREATE TABLE audit_logs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID NOT NULL REFERENCES organizations(id),
    user_id         UUID REFERENCES users(id),
    action_type     VARCHAR(50) NOT NULL,
    -- action_type: 'query', 'document_upload', 'tool_propose', 'tool_execute',
    --              'tool_reject', 'user_login', 'user_role_change'
    action_data     JSONB NOT NULL DEFAULT '{}',
    ip_address      INET,
    user_agent      TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
    -- NO updated_at — audit logs are immutable
);

CREATE INDEX idx_audit_logs_org_id ON audit_logs(org_id);
CREATE INDEX idx_audit_logs_user_id ON audit_logs(user_id);
CREATE INDEX idx_audit_logs_action_type ON audit_logs(action_type);
CREATE INDEX idx_audit_logs_created_at ON audit_logs(created_at DESC);
```

> [!CAUTION]
> **Never grant UPDATE or DELETE on `audit_logs` to the application database user.** Use a separate runtime role with only `INSERT` and `SELECT` on this table; `knexus_admin` is the development bootstrap administrator.

**`action_data` structure per `action_type`:**

```jsonc
// action_type: "query"
{
  "question": "What is the leave policy?",
  "answer_preview": "According to HR Policy...",
  "abstained": false,
  "chunks_used": ["chunk-uuid-1", "chunk-uuid-2"],
  "similarity_scores": [0.87, 0.76],
  "model": "llama3.2",
  "generation_time_ms": 2340
}

// action_type: "document_upload"
{
  "document_id": "uuid",
  "title": "Expense Policy 2026",
  "allowed_roles": ["employee", "manager"]
}

// action_type: "tool_execute"
{
  "proposal_id": "uuid",
  "tool_name": "create_task",
  "approved_by": "uuid",
  "result": { "task_id": "uuid", "status": "created" }
}
```

---

### 3.7 `tool_proposals`

```sql
CREATE TABLE tool_proposals (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID NOT NULL REFERENCES organizations(id),
    proposed_by     UUID NOT NULL REFERENCES users(id),
    approved_by     UUID REFERENCES users(id),
    tool_name       VARCHAR(100) NOT NULL,
    payload         JSONB NOT NULL,
    payload_hash    VARCHAR(64) NOT NULL,   -- SHA-256 hex
    status          VARCHAR(30) NOT NULL DEFAULT 'pending_approval'
                        CHECK (status IN (
                            'pending_approval', 'approved', 'rejected',
                            'executed', 'expired', 'tampered'
                        )),
    rejection_reason TEXT,
    execution_result JSONB,
    expires_at      TIMESTAMPTZ NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_proposals_org_id ON tool_proposals(org_id);
CREATE INDEX idx_proposals_status ON tool_proposals(status);
CREATE INDEX idx_proposals_proposed_by ON tool_proposals(proposed_by);
CREATE INDEX idx_proposals_expires_at ON tool_proposals(expires_at);
```

---

## 4. Alembic Migration Strategy

Future schema changes must use **Alembic migrations**. These commands are implementation tasks, not a working setup path: first configure the async migration environment, settings URL, and imported model metadata. Installing Alembic and running `init` alone does not enable autogeneration.

### Setup (run once):
```bash
# From backend/ directory
alembic init alembic
```

### Creating a new migration:
```bash
alembic revision --autogenerate -m "create_initial_schema"
```

### Applying migrations:
```bash
alembic upgrade head
```

### Rolling back:
```bash
alembic downgrade -1
```

---

## 5. Key SQL Queries

### Semantic Search with RBAC (the core retrieval query)
```sql
SELECT
    e.id AS embedding_id,
    dc.content AS chunk_content,
    dc.metadata AS chunk_metadata,
    d.title AS document_title,
    d.id AS document_id,
    1 - (e.embedding <=> :query_vector) AS similarity_score
FROM
    embeddings e
    JOIN document_chunks dc ON dc.id = e.chunk_id
    JOIN documents d ON d.id = e.document_id
WHERE
    e.org_id = :current_org_id
    AND e.allowed_roles ?| :user_roles_array       -- JSONB contains-any operator
    AND d.org_id = :current_org_id
    AND dc.org_id = :current_org_id
    AND d.allowed_roles ?| :user_roles_array
    AND d.status = 'complete'
    AND d.is_deleted = FALSE
ORDER BY
    e.embedding <=> :query_vector ASC              -- cosine distance ascending
LIMIT :top_k;
```

### Check pgvector Extension Status
```sql
SELECT extname, extversion
FROM pg_extension
WHERE extname = 'vector';
```

### Count chunks per document
```sql
SELECT d.title, COUNT(dc.id) AS chunk_count
FROM documents d
LEFT JOIN document_chunks dc ON dc.document_id = d.id
WHERE d.org_id = :org_id
GROUP BY d.id, d.title;
```

---

## 6. Performance Considerations

| Concern | Solution |
|---|---|
| Slow vector search as corpus grows | HNSW index with `m=16, ef_construction=64` (proposed; not yet created) |
| Cross-tenant data leakage | `org_id` index + mandatory WHERE clause in all queries |
| Role filter on large embedding table | GIN index on `allowed_roles` JSONB column |
| Repeated identical queries | Query-level result cache (Redis/in-memory, Phase 2) |
| Embedding model switch | `model_name` column on `embeddings` enables selective re-embedding |

---

*KNEXUS Database Schema v1.0 | MJCET CSE (AI&ML) | Team 3 | 2026–2027*
