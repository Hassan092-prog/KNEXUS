# Backend test database strategy

The normal `pytest` suite uses contract fixtures and fake services. It must not connect to the shared development database, require Ollama, or make network/model downloads.

Database integration tests use a dedicated temporary PostgreSQL/pgvector container on the same developer machine or CI worker that runs pytest. Do not point tests at the shared KNEXUS server, the normal Compose service, the production-like `.env`, or a persistent volume. Create a unique database and test-only role inside a container with no volume mount and bind its port to loopback. Give each concurrent run a unique container name and free host port.

Pass the temporary container's connection URL only to the integration-test process through `DATABASE_URL` (and `DATABASE_SYNC_URL` if a synchronous migration tool needs it). Never write test credentials into `.env`. Before a test fixture creates, drops or migrates anything, it must verify all of these conditions and abort before connecting if any check fails:

- Host is loopback (`127.0.0.1` or `localhost`).
- Database name begins with `knexus_test_` and the role is the dedicated test role.
- The test was explicitly selected with the `integration` marker.

Use a unique database/container per run. Apply migrations to an empty test database, run the checks, then stop the container. The suggested container uses `--rm`, no bind mounts and no named volumes, so stopping it discards its data. If a run is interrupted, stop only the uniquely named test container. Never use `docker compose down -v`, drop schemas or clear data on the shared development Compose project.

No database integration fixture or migration command is implemented by H01. H02 must add the guarded fixture and migration tests before treating this procedure as executable. Until then, keep tests database-free and use this document as the required safety design.
