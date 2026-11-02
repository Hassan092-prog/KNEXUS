# Backend testing

## Hosted migration verification

The revised target is hosted generation and embeddings; ordinary offline checks use mocked HTTP and fake vectors. Existing MiniLM/Ollama tests and archived runs describe historical implementation, not instructions to start inference.

Add hosted tests for secure configuration/authentication errors, deadlines/cancellation, rate limits, structured results, token policy and finite vectors of the agreed dimension. No downloads or billable calls in ordinary pytest. Use approved disposable tests for storage/index changes, never the shared DB. Hosted synthetic end-to-end and browser gates require separately authorized access. [TRD](../../docs/TRD.md) owns provider/model and embedding decisions.

## Offline checks

The full offline suite uses synthetic fixtures, fake tokenizers/embedders, mocked HTTP and in-memory route sessions. It must not connect to any database, require Ollama or download models. Tests cover parser/storage/chunking, ingestion transitions, tenant/role SQL construction, API response/error mapping, and harness error inspection regressions. Dated pass/skip counts belong in project status. CONTRIBUTING.md owns check commands. [Project status](../../docs/PROJECT_STATUS.md) owns recorded results and historical run evidence.

Processor recovery is an explicit operator action. Call it only after confirming the prior process has restarted and no ingestion workers remain active; it marks queued and processing attempts failed, after which the normal explicit retry helper can create a new attempt. It is never called automatically at startup.

Offline metadata/migration parity, generated SQL and fake-session route checks do not prove PostgreSQL enforcement or end-to-end persistence. Generation mocks do not prove model quality. Run the canonical checker separately.

## Disposable database checks

Reusable integration tests live directly in the repository:
- `backend/tests/test_persistence_postgres.py` (5 database cases, 1 offline error-unwrapping regression)
- `backend/tests/test_h03_h06_postgres.py` (H03-H06 integration and offline regressions; historical local MiniLM inference remains an explicit legacy opt-in)

Database tests are strictly opt-in and automatically skip during normal offline pytest runs. To execute them against an isolated disposable target, set `KNEXUS_ENABLE_DISPOSABLE_PG_TESTS=1` alongside target environment credentials:

```bash
KNEXUS_ENABLE_DISPOSABLE_PG_TESTS=1 pytest backend/tests/test_persistence_postgres.py backend/tests/test_h03_h06_postgres.py
```

The guarded harness enforces loopback target identity (`127.0.0.1`), synthetic credentials, and explicitly rejects any target pointing to the shared development database.

Historical verification harnesses and run logs are preserved in durable storage outside Git at `/home/hassan/verification_archive/` (and `/tmp/knexus-h03-h06-verification-20261101-ppbpi3wh/`):
- Runner: `verify_h03_h06.sh`
- Recovery script: `manual_recovery.sh`
- Successful run log: `run_20261102_005900.log` (21 passed: 17 database integration cases + 4 offline cases).
- Historical Run 1 log: `run_20261102_004144.log`
