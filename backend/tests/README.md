# Backend verification

## Offline checks

The full offline suite uses synthetic fixtures, fake tokenizers/embedders, mocked HTTP and in-memory route sessions. It must not connect to any database, require Ollama or download models. In Hassan's isolated draft, tests cover parser/storage/chunking, ingestion transitions, tenant/role SQL construction and API response/error mapping. CONTRIBUTING.md owns check commands. [Project status](../../docs/PROJECT_STATUS.md) owns recorded results and the attempt-5 source-fingerprint limitation.

Processor recovery is an explicit operator action. Call it only after confirming the prior process has restarted and no ingestion workers remain active; it marks queued and processing attempts failed, after which the normal explicit retry helper can create a new attempt. It is never called automatically at startup.

Offline metadata/migration parity, generated SQL and fake-session route checks do not prove PostgreSQL enforcement or end-to-end persistence. Generation mocks do not prove model quality. Run the canonical checker separately.

## Disposable database checks

The integration test harnesses and logs reside outside Git:

1. **H03-H06 integration artifacts** at `/tmp/knexus-h03-h06-verification-20261101-ppbpi3wh/`:
   - Runner: `verify_h03_h06.sh`
   - Recovery script: `manual_recovery.sh`
   - Test module: `test_h03_h06_postgres.py`
   - Snapshot manifest: `tested-source-20261101_h03h06_1a6c360d.sha256` (SHA-256: `709c91bf43b14b6bc43dd2879f0f3b82c529dc8231be0245a49425e3c096626f`)
   - Successful run log: `run_20261102_005900.log` (21 passed: 17 database integration cases + 4 offline cases).
   - Historical Run 1 log: `run_20261102_004144.log` (19 passed, 1 failed due to harness exception-hook unwrapping defect).

2. **Historical H02 persistence artifacts** at `/tmp/knexus-pgverify-review-20261101/`:
   - `verify_disposable_pg.sh`, `test_persistence_postgres.py`, `manual_recovery.sh` and `run-attempt-5.log`.

These are local artifacts, not a portable committed integration suite or permission to rerun. Check their existence before reuse. The shared database remains unmigrated.

Each new database run requires approval for an isolated target:
- Exact preloaded image with pulls disabled; fresh uniquely named/labeled container, network and volume; synthetic credentials.
- Verify image/ownership, exactly the expected data-volume mount and actual loopback-only port publication.
- One bounded startup deadline and TCP probes against the exact synthetic DB/user. The entrypoint's socket-only temporary server must not satisfy readiness.
- Guard URL, host, database and user and check `current_database()`/`current_user` before migrations/tests.
- Require exact SQLSTATE and constraint names; inspect adapter/native exception links, never arbitrary exceptions or message parsing.
- Check catalog type `vector(384)`. Insert a wrong-length value using `CAST(:vector AS vector)` and require native asyncpg `DataError` plus SQLSTATE `22000`.
- Verify downgrade state before re-upgrade. Clean only this run's owned resources on success/failure and verify absence.

The dedicated non-internal test bridge enabled Docker port publication and permitted outbound traffic; it held synthetic data only and was removed. Protected `knexus-postgres` and `knexus_postgres_data` are never disposable test targets. Do not use prune commands or `docker compose down -v`.

Offline Alembic `--sql` rendering does not connect. Autogeneration, online migration and seed execution do. Use synthetic settings or a sanitized source copy without environment files. Never rewrite old logs or invent missing provenance.
