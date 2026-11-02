# Security model

This document separates implemented controls from required protections. [Project status](PROJECT_STATUS.md) records evidence; [Phase 1 contract](PHASE_1_CONTRACT.md) owns role vocabulary, identity boundaries and safe public errors.

## Current boundary

Implemented:
- Canonical public metadata rejects caller-supplied identity; the server demo actor expands effective roles.
- Composite foreign keys constrain same-tenant storage relationships.
- Generation accepts authorized evidence only, validates structured output/citation membership, sends evidence as untrusted data and preserves typed failures.
- Demo seeding rejects conflicting/inactive reserved records without automatic reactivation.

Not implemented in published main:
- Login/session/JWT authentication or PostgreSQL row-level security.
- Approval/execution controls, audit tables or append-only runtime permissions.
- Production readiness, rate limiting or a dependency lock/CI security workflow.

The Phase 1 backend implements server-demo-actor route checks and SQL-filtered retrieval. Covered tenant/role filtering and API scenarios passed against disposable PostgreSQL/pgvector with synthetic fixtures. This does not establish production authentication or live-model safety.

Root/health have no authentication. Health returns HTTP 200 with generic availability fields, so it is diagnostic rather than readiness. DEBUG enables SQL echo. Compose's current PostgreSQL mapping does not restrict the host interface, and its bootstrap admin is not a least-privilege application role.

Use local synthetic data only until these gaps are resolved. CORS, UI badges, valid foreign keys and a public health response do not establish access control.

## Retrieval and document access

Resolve active identity server-side; a demo actor is not a login substitute. Expand the canonical effective role hierarchy on the server; superadmin remains tenant-scoped unless an explicit audited cross-organization operation is authorized.

All reads/mutations must enforce current organization and permissions. Retrieval must join/check current parent-document access, completed/nondeleted state and active model before generation, including when a forbidden vector is the nearest neighbor. Do not rely on stale denormalized permissions.

A cross-tenant or absent document is 404; same-tenant role denial is 403 where the canonical resource contract requires it. Lists filter before pagination and counts. Upload/status access needs an eligible uploader/admin context. Files use private storage, validated type/signature/size, safe keys and parser/resource bounds.

## Authentication and sessions: Phase 2

Choose and implement the reviewed credential/session policy before promising login. Expiry defaults in Settings do not implement tokens. A client-only logout cannot revoke a stolen valid token; immediate revocation requires persisted session/rotation or an explicit denylist decision.

Reject inactive users/organizations, forged identity fields and unauthorized membership. Password hashing, token verification/claims, refresh/revocation policy, safe browser storage and abuse controls require focused tests and coordinated API/UI contracts.

## Prompt and output threats

Question/evidence are data. Preserve structured source boundaries; do not execute model-generated commands/SQL or accept model-provided tenant/access decisions. Keyword filters such as deleting evidence containing 'user input:' and generic numeric comparisons are not valid defenses or conflict reasoning.

Require strict answer/abstention schema, inline markers and evidence membership. Provider errors and malformed output remain failures. Prompt separation and structural validation cannot prove instruction-injection resistance or factual support; evaluate adversarial evidence and unsupported claims separately.

## Governed actions: Phase 2

Only server-registered typed sandbox handlers are allowed. Before execution:
1. Validate requester, tenant, tool/version, target and arguments.
2. Persist one canonical immutable envelope and reviewed integrity binding.
3. Authorize the approver and recheck expiry, current policy and exact envelope.
4. Atomically claim the proposal once using transactional/conditional state changes.
5. Execute only the claimed payload with idempotency protection.
6. Verify the resulting state and record success, failure or inconclusive outcome.
7. Preserve safe append-only audit events.

A bare hash does not prevent changes to both payload/hash, replay or a race. Test tampering, expired/rejected/missing approvals, concurrent claims, duplicate retries, authorization changes and partial execution/audit failures. Do not add arbitrary external handlers to the first workflow.

## Audit and operational policy

Separate migration administration from least-privilege runtime credentials. Append-only audit needs database permissions as well as application rules; a table name alone is not immutability. Minimize/redact private queries, evidence, credentials and provider diagnostics.

Database verification uses only approved disposable resources; [testing guidance](../backend/tests/README.md) owns the isolation/cleanup rules. Secrets, real uploads and full corpora stay out of Git.

## Required negative evidence

Verify cross-tenant parent rejection and request isolation independently; restricted direct reads/lists/retrieval; permissions changed after indexing; failed/deleted/partial documents excluded; prompt injection; unavailable/timeout/malformed generation; inactive identity; and governed-action tamper/expiry/replay/concurrency cases.

The backend baseline has persistence constraint and offline generation-boundary evidence. Covered tenant/role SQL filters and API scenarios are verified against disposable PostgreSQL/pgvector with synthetic fixtures; live provider behavior and production authentication remain unverified. No general security guarantee follows from these tests.
