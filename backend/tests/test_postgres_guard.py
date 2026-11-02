"""Offline regressions for hardened disposable PostgreSQL test guard.

Tests safety checks, port protections, ownership evidence, and runtime inspection
without establishing real database connections.
"""

import pytest
from tests.postgres_guard import (
    DatabaseGuardError,
    guard_disposable_database_url,
    PROTECTED_SHARED_PORT,
)


def _valid_inspect_data(
    run_id: str = "testrun123",
    port: int = 34567,
    owner: str = "hassan-phase1-verification",
    image: str = "pgvector/pgvector:pg16",
    volume: str | None = None,
    network: str | None = None,
    running: bool = True,
    binds: list | None = None,
):
    vol_name = volume or f"knx-vol-{run_id}"
    net_name = network or f"knx-net-{run_id}"
    return {
        "State": {"Running": running},
        "Config": {
            "Image": image,
            "Labels": {
                "com.knexus.pgverify.owner": owner,
                "com.knexus.pgverify.run": run_id,
            },
        },
        "HostConfig": {
            "Binds": binds or [],
        },
        "Mounts": [
            {
                "Type": "volume",
                "Name": vol_name,
                "Destination": "/var/lib/postgresql/data",
                "RW": True,
            }
        ],
        "NetworkSettings": {
            "Networks": {net_name: {}},
            "Ports": {
                "5432/tcp": [
                    {
                        "HostIp": "127.0.0.1",
                        "HostPort": str(port),
                    }
                ]
            },
        },
    }


def _valid_env(run_id: str = "testrun123", port: int = 34567):
    db_user = f"knx_user_{run_id}"
    db_name = f"knx_test_{run_id}"
    url = f"postgresql+asyncpg://{db_user}:secret@127.0.0.1:{port}/{db_name}"
    return {
        "DATABASE_URL": url,
        "KNEXUS_VERIFY_EXPECTED_DATABASE_URL": url,
        "KNEXUS_DISPOSABLE_RUN_ID": run_id,
        "KNEXUS_DISPOSABLE_CONTAINER": f"knx-db-{run_id}",
        "KNEXUS_DISPOSABLE_VOLUME": f"knx-vol-{run_id}",
        "KNEXUS_DISPOSABLE_NETWORK": f"knx-net-{run_id}",
        "KNEXUS_DISPOSABLE_OWNER": "hassan-phase1-verification",
        "POSTGRES_USER": db_user,
        "POSTGRES_DB": db_name,
        "POSTGRES_PORT": str(port),
    }


def test_guard_accepts_valid_owned_disposable_target():
    env = _valid_env("run456", 39999)
    inspect_data = _valid_inspect_data(
        run_id="run456",
        port=39999,
        volume="knx-vol-run456",
        network="knx-net-run456",
    )
    url = guard_disposable_database_url(
        env=env,
        inspect_fn=lambda name: inspect_data,
    )
    assert url == env["DATABASE_URL"]


def test_guard_rejects_protected_port_regardless_of_user_or_database():
    env = _valid_env("safe123", PROTECTED_SHARED_PORT)
    inspect_data = _valid_inspect_data(run_id="safe123", port=PROTECTED_SHARED_PORT)
    with pytest.raises(DatabaseGuardError, match="protected port 5435"):
        guard_disposable_database_url(
            env=env,
            inspect_fn=lambda name: inspect_data,
        )


def test_guard_rejects_protected_port_with_arbitrary_user_and_db():
    url = "postgresql+asyncpg://some_other_user:pass@127.0.0.1:5435/some_other_db"
    env = {
        "DATABASE_URL": url,
        "KNEXUS_VERIFY_EXPECTED_DATABASE_URL": url,
        "KNEXUS_DISPOSABLE_RUN_ID": "some_other_user",
        "KNEXUS_DISPOSABLE_CONTAINER": "some-container",
    }
    with pytest.raises(DatabaseGuardError, match="protected port 5435"):
        guard_disposable_database_url(
            env=env,
            inspect_fn=lambda name: _valid_inspect_data(port=5435),
        )


def test_guard_rejects_arbitrary_unverified_loopback_target_without_evidence():
    url = "postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/postgres"
    env = {
        "DATABASE_URL": url,
        "KNEXUS_VERIFY_EXPECTED_DATABASE_URL": url,
    }
    # Missing run identity and container ownership evidence
    with pytest.raises(DatabaseGuardError, match="Missing or invalid unique run identity"):
        guard_disposable_database_url(env=env)


def test_guard_rejects_missing_or_mismatched_run_identity():
    env = _valid_env("valid123", 31234)
    # Remove run identity
    del env["KNEXUS_DISPOSABLE_RUN_ID"]
    with pytest.raises(DatabaseGuardError, match="Missing or invalid unique run identity"):
        guard_disposable_database_url(env=env)

    # Invalid run identity (characters outside permitted set)
    env["KNEXUS_DISPOSABLE_RUN_ID"] = "bad id with spaces!"
    with pytest.raises(DatabaseGuardError, match="Missing or invalid unique run identity"):
        guard_disposable_database_url(env=env)


def test_guard_rejects_missing_container_evidence():
    env = _valid_env("valid123", 31234)
    del env["KNEXUS_DISPOSABLE_CONTAINER"]
    with pytest.raises(DatabaseGuardError, match="Missing KNEXUS_DISPOSABLE_CONTAINER"):
        guard_disposable_database_url(env=env)


def test_guard_rejects_ownership_label_mismatch():
    env = _valid_env("valid123", 31234)
    # Label mismatch on run tag
    inspect_data = _valid_inspect_data(run_id="DIFFERENT_RUN", port=31234)
    with pytest.raises(DatabaseGuardError, match="Disposable container run label"):
        guard_disposable_database_url(env=env, inspect_fn=lambda n: inspect_data)

    # Label mismatch on owner
    inspect_data_owner = _valid_inspect_data(
        run_id="valid123", port=31234, owner="unauthorized-actor"
    )
    with pytest.raises(DatabaseGuardError, match="Disposable container ownership label"):
        guard_disposable_database_url(env=env, inspect_fn=lambda n: inspect_data_owner)


def test_guard_rejects_runtime_port_mismatch():
    env = _valid_env("valid123", 31234)
    # Inspect data reports host port 35555 instead of 31234
    inspect_data = _valid_inspect_data(run_id="valid123", port=35555)
    with pytest.raises(DatabaseGuardError, match="does not match DATABASE_URL port"):
        guard_disposable_database_url(env=env, inspect_fn=lambda n: inspect_data)


def test_guard_rejects_image_mismatch():
    env = _valid_env("valid123", 31234)
    inspect_data = _valid_inspect_data(run_id="valid123", port=31234, image="postgres:16-alpine")
    with pytest.raises(DatabaseGuardError, match="does not match expected"):
        guard_disposable_database_url(env=env, inspect_fn=lambda n: inspect_data)


def test_guard_rejects_bind_mounts():
    env = _valid_env("valid123", 31234)
    inspect_data = _valid_inspect_data(
        run_id="valid123",
        port=31234,
        binds=["/host/path:/var/lib/postgresql/data"],
    )
    with pytest.raises(DatabaseGuardError, match="must not have host bind mounts"):
        guard_disposable_database_url(env=env, inspect_fn=lambda n: inspect_data)


def test_guard_rejects_volume_mismatch():
    env = _valid_env("valid123", 31234)
    inspect_data = _valid_inspect_data(
        run_id="valid123",
        port=31234,
        volume="wrong-volume-name",
    )
    with pytest.raises(DatabaseGuardError, match="does not match expected"):
        guard_disposable_database_url(env=env, inspect_fn=lambda n: inspect_data)


def test_guard_rejects_network_mismatch():
    env = _valid_env("valid123", 31234)
    inspect_data = _valid_inspect_data(
        run_id="valid123",
        port=31234,
        network="wrong-network-name",
    )
    with pytest.raises(DatabaseGuardError, match="attached networks .* do not match"):
        guard_disposable_database_url(env=env, inspect_fn=lambda n: inspect_data)


def test_guard_rejects_stopped_container():
    env = _valid_env("valid123", 31234)
    inspect_data = _valid_inspect_data(run_id="valid123", port=31234, running=False)
    with pytest.raises(DatabaseGuardError, match="is not in running state"):
        guard_disposable_database_url(env=env, inspect_fn=lambda n: inspect_data)
