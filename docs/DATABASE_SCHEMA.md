# Persistence schema

The reviewed persistence foundation and H03-H06 ingestion/retrieval models are merged into main (PR #4, PR #5, PR #7). Composite foreign key constraints, migration round trips (upgrade, repeat, downgrade to base, re-upgrade) and retrieval filtering are verified against disposable PostgreSQL/pgvector. [Project status](PROJECT_STATUS.md) owns exact revisions and evidence. The shared database has not been migrated. This document describes actual ORM/migration definitions, not a second executable DDL proposal.

Authoritative definitions:
- [Core models](../backend/app/models/core.py)
- [Document/chunk/embedding/job models](../backend/app/models/documents.py)
- [Initial revision](../backend/alembic/versions/0001_phase1_persistence.py)
- [Explicit demo seed](../backend/app/db/demo_seed.py)

## Embedding proposal status (6 November 2026)

Storage remains vector(384), with no hosted schema/profile change implemented by this update. Offline hosted embedding foundation (PR #16) and input token validation (PR #19) are merged in main; corpus activation, re-embedding, and any future dimensional migrations remain pending. Final free-tier embedding provider/model/dimension remains undecided. Preserve existing chunks/vectors and plan explicit activation, resumable re-embedding and safe downgrade; no external API calls inside migrations and no silent vector deletion/conversion.

## Hosted embedding transition

The revised target uses hosted embeddings; the schema remains vector(384) until a reviewed change. Provider/model/dimension selection is pending. Use identical model/revision for documents and queries; validate finite values and vector lengths. Re-embed for any model change, even at 384 dimensions; a new dimension additionally requires migration/index changes. Never mix MiniLM document vectors with hosted query vectors. This update performs no database migration. [TRD](TRD.md) owns the coordinated decision.

## Tables and integrity

| Table | Implemented rules |
|---|---|
| `organizations` | UUID key, unique nonblank slug, nonblank name, active flag |
| `users` | Tenant-owned UUID, unique email per organization, lowercase canonical role, active/demo flags; no password/session implementation |
| `documents` | Uploader must belong to the same organization; PDF/DOCX only; positive file size up to 10 MiB; nonempty valid-role JSON array; lifecycle and nonnegative chunk count; storage key, original filename, metadata and deletion flag |
| `document_chunks` | Same-tenant document; unique organization/document/chunk position; stable UUID, zero-based index, content 1-8000 characters, optional one-based page/token count and source metadata |
| `embeddings` | Same-tenant exact document/chunk tuple; `vector(384)`; model/revision metadata; unique chunk/model/revision and at most one active embedding per chunk |
| `ingestion_jobs` | Same-tenant document; positive unique attempt number per document; at most one queued/processing attempt; lifecycle/counters, safe failure fields and timestamps |

All timestamps are timezone-aware. `updated_at` uses ORM `onupdate` behavior, not a database trigger for arbitrary SQL updates. UUID defaults exist in Python and PostgreSQL.

Tenant-consistent composite foreign keys prevent invalid parent relationships; they do not implement user-facing authorization or PostgreSQL row-level security. Retrieval must still filter current organization, permissions, completed/nondeleted documents, and active intended model revision.

Document role-array checks enforce nonempty arrays containing valid roles. Unique role values are a canonical request/service requirement, not a separate database uniqueness guarantee.

Embedding permissions are not duplicated into the embedding table. Future retrieval must join/check the current parent document. The cosine HNSW index uses `vector_cosine_ops`, `m=16` and `ef_construction=64`. A dimension/model change needs explicit migration and re-embedding, not just another model name.

## Ingestion-job state rules

- `queued`: no start/finish timestamps and zero processed chunks.
- `processing`: start exists, finish absent, failure fields null.
- `complete`: start/finish exist, total known and all chunks processed; failure fields null.
- `failed`: finish and valid failure code/message required; start may be absent for an early failure.
- Every non-failed state requires both failure fields null.
- Failure codes are `INVALID_FILE`, `PROCESSING_FAILED` or `INTERRUPTED`.
- `failure_message ~ '[^[:space:]]'` requires at least one non-whitespace character. The policy covers space, tab, LF, vertical tab, form feed and CR; ORM/migration definitions match.
- Counters are nonnegative and processed cannot exceed a known total.

These checks validate stored row states. Services must implement allowed transitions, consistent document/job updates, interruption handling and retry semantics; the constraints alone are not a worker or durable queue. The accepted upload returns the persisted job UUID as task_id.

## Alembic

[alembic.ini](../alembic.ini) resolves scripts relative to its own location. The environment imports shared metadata and root-anchored Settings; exported variables override root `.env` independently of working directory.

The initial upgrade enables pgvector if needed and creates six tables plus indexes. Downgrade removes those tables while retaining vector because other objects may use it. Startup performs no schema creation or seed.

Offline rendering from the root, using an existing environment and synthetic settings:

~~~bash
backend/venv/bin/python -m alembic -c alembic.ini upgrade head --sql
~~~

Rendering does not connect. Online upgrade/downgrade and autogeneration connect to `DATABASE_URL` and require approval for the exact target. Do not copy speculative SQL into a shared database or run migration round trips there. [Backend testing guidance](../backend/tests/README.md) defines disposable safeguards.

## Explicit demo seeding

`seed_demo_identity(session)` creates fixed canonical demo organization/user UUIDs if absent and flushes only. The caller controls commit/rollback. Matching active records are reused across sessions; inactive or conflicting reserved records are rejected rather than reactivated or overwritten. Email/full name remain mutable profile fields.

The helper neither authenticates callers nor initializes documents or users generally. There is no automatic CLI/startup seed invocation.

## Later schema

Authentication credentials/sessions, history, append-only audit, governed action envelopes/approval/execution and sandbox tasks are future migrations. Do not present illustrative table names as implemented. Review least-privilege runtime roles, transactional integrity and concurrency before building those features.
