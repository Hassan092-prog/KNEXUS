# Backend verification

## Offline checks

Ordinary pytest uses synthetic contracts, fake services and mocked HTTP. It must not connect to the shared database, require Ollama or download models. [CONTRIBUTING](../../CONTRIBUTING.md) owns check commands. [Project status](../../docs/PROJECT_STATUS.md) owns recorded results and the attempt-5 source-fingerprint limitation.

Offline metadata/migration parity and fake-session checks do not prove PostgreSQL enforcement. Generation mocks do not prove model quality. Run the canonical checker separately.

## Disposable database checks

The one-off reviewed artifacts are outside Git at `/tmp/knexus-pgverify-review-20261101/`: `verify_disposable_pg.sh`, `test_persistence_postgres.py`, `manual_recovery.sh` and successful `run-attempt-5.log`.

These are local artifacts, not a portable committed integration suite or permission to rerun. Check their existence before reuse. The module contains five database tests and one offline wrapped-exception regression.

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
