"""Offline regressions for hardened disposable PostgreSQL test guard.

Tests safety checks, port protections, ownership evidence, and runtime inspection
without establishing real database connections.
"""

import pytest
from tests.postgres_guard import (
    APPROVED_IMAGE_ID,
    APPROVED_IMAGE_TAG,
    DatabaseGuardError,
    guard_disposable_database_url,
    PROTECTED_SHARED_PORT,
)


def _valid_container_inspect(
    run_id: str = "testrun123",
    port: int = 34567,
    owner: str = "hassan-phase1-verification",
    image_tag: str = APPROVED_IMAGE_TAG,
    image_id: str = APPROVED_IMAGE_ID,
    container_name: str | None = None,
    volume: str | None = None,
    network: str | None = None,
    running: bool = True,
    binds: list | None = None,
    cfg_ports: dict | None = None,
    rt_ports: dict | None = None,
):
    c_name = container_name if container_name is not None else f"knx-db-{run_id}"
    v_name = volume if volume is not None else f"knx-vol-{run_id}"
    n_name = network if network is not None else f"knx-net-{run_id}"

    if cfg_ports is None:
        cfg_ports = {"5432/tcp": [{"HostIp": "127.0.0.1", "HostPort": str(port)}]}
    if rt_ports is None:
        rt_ports = {"5432/tcp": [{"HostIp": "127.0.0.1", "HostPort": str(port)}]}

    return {
        "Name": f"/{c_name}",
        "State": {"Running": running},
        "Image": image_id,
        "Config": {
            "Image": image_tag,
            "Labels": {
                "com.knexus.pgverify.owner": owner,
                "com.knexus.pgverify.run": run_id,
            },
        },
        "HostConfig": {
            "Binds": binds or [],
            "PortBindings": cfg_ports,
        },
        "Mounts": [
            {
                "Type": "volume",
                "Name": v_name,
                "Destination": "/var/lib/postgresql/data",
                "RW": True,
            }
        ],
        "NetworkSettings": {
            "Networks": {n_name: {}},
            "Ports": rt_ports,
        },
    }


def _valid_volume_inspect(
    volume_name: str | None = None,
    run_id: str = "testrun123",
    owner: str = "hassan-phase1-verification",
    driver: str = "local",
):
    v_name = volume_name if volume_name is not None else f"knx-vol-{run_id}"
    return {
        "Name": v_name,
        "Driver": driver,
        "Labels": {
            "com.knexus.pgverify.owner": owner,
            "com.knexus.pgverify.run": run_id,
        },
    }


def _valid_network_inspect(
    network_name: str | None = None,
    run_id: str = "testrun123",
    owner: str = "hassan-phase1-verification",
    driver: str = "bridge",
):
    n_name = network_name if network_name is not None else f"knx-net-{run_id}"
    return {
        "Name": n_name,
        "Driver": driver,
        "Labels": {
            "com.knexus.pgverify.owner": owner,
            "com.knexus.pgverify.run": run_id,
        },
    }


def _make_inspect_fn(c_data, v_data, n_data):
    def inspect_fn(kind: str, name: str):
        if kind == "container":
            return c_data
        elif kind == "volume":
            return v_data
        elif kind == "network":
            return n_data
        raise ValueError(f"Unknown kind: {kind}")
    return inspect_fn


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
    run_id = "run456"
    port = 39999
    env = _valid_env(run_id, port)
    c_data = _valid_container_inspect(run_id=run_id, port=port)
    v_data = _valid_volume_inspect(run_id=run_id)
    n_data = _valid_network_inspect(run_id=run_id)

    url = guard_disposable_database_url(
        env=env,
        inspect_fn=_make_inspect_fn(c_data, v_data, n_data),
    )
    assert url == env["DATABASE_URL"]


# === Reviewer Confirmed Defect 1: JSON Bypass Attempt ===
def test_guard_rejects_env_json_bypass_attempt():
    env = _valid_env("bypass123", 31234)
    # Injecting KNEXUS_DISPOSABLE_INSPECT_JSON must be completely ignored.
    # Without an inspect_fn, the guard must attempt live docker inspect and fail closed.
    env["KNEXUS_DISPOSABLE_INSPECT_JSON"] = '{"fake": "proof"}'
    with pytest.raises(DatabaseGuardError):
        # We don't provide inspect_fn, and docker command will fail or raise guard error
        guard_disposable_database_url(env=env, inspect_timeout=0.001)


# === Reviewer Confirmed Defect 2: Missing Volume or Network ===
def test_guard_rejects_missing_expected_volume():
    env = _valid_env("valid123", 31234)
    del env["KNEXUS_DISPOSABLE_VOLUME"]
    with pytest.raises(DatabaseGuardError, match="Missing required KNEXUS_DISPOSABLE_VOLUME"):
        guard_disposable_database_url(env=env)


def test_guard_rejects_missing_expected_network():
    env = _valid_env("valid123", 31234)
    del env["KNEXUS_DISPOSABLE_NETWORK"]
    with pytest.raises(DatabaseGuardError, match="Missing required KNEXUS_DISPOSABLE_NETWORK"):
        guard_disposable_database_url(env=env)


# === Reviewer Confirmed Defect 3: Protected Volume Name ===
def test_guard_rejects_protected_volume_name():
    env = _valid_env("valid123", 31234)
    env["KNEXUS_DISPOSABLE_VOLUME"] = "knexus_postgres_data"
    with pytest.raises(DatabaseGuardError, match="protected resource name"):
        guard_disposable_database_url(env=env)


def test_guard_rejects_protected_container_name():
    env = _valid_env("valid123", 31234)
    env["KNEXUS_DISPOSABLE_CONTAINER"] = "knexus-postgres"
    with pytest.raises(DatabaseGuardError, match="protected resource name"):
        guard_disposable_database_url(env=env)


# === Reviewer Confirmed Defect 4: Unapproved Tag and Image ID ===
def test_guard_rejects_unapproved_image_tag():
    run_id = "valid123"
    port = 31234
    env = _valid_env(run_id, port)
    c_data = _valid_container_inspect(run_id=run_id, port=port, image_tag="pgvector/pgvector:unapproved-tag")
    v_data = _valid_volume_inspect(run_id=run_id)
    n_data = _valid_network_inspect(run_id=run_id)
    with pytest.raises(DatabaseGuardError, match="does not match approved 'pgvector/pgvector:pg16'"):
        guard_disposable_database_url(env=env, inspect_fn=_make_inspect_fn(c_data, v_data, n_data))


def test_guard_rejects_unapproved_image_id():
    run_id = "valid123"
    port = 31234
    env = _valid_env(run_id, port)
    c_data = _valid_container_inspect(run_id=run_id, port=port, image_id="sha256:wronghash00000000000000000000000000000000000000000000000000000000")
    v_data = _valid_volume_inspect(run_id=run_id)
    n_data = _valid_network_inspect(run_id=run_id)
    with pytest.raises(DatabaseGuardError, match="does not match approved immutable ID"):
        guard_disposable_database_url(env=env, inspect_fn=_make_inspect_fn(c_data, v_data, n_data))


# === Protected Port Regressions ===
def test_guard_rejects_protected_port_regardless_of_user_or_database():
    env = _valid_env("safe123", PROTECTED_SHARED_PORT)
    with pytest.raises(DatabaseGuardError, match="protected port 5435"):
        guard_disposable_database_url(env=env)


def test_guard_rejects_protected_port_with_arbitrary_user_and_db():
    url = "postgresql+asyncpg://some_other_user:pass@127.0.0.1:5435/some_other_db"
    env = {
        "DATABASE_URL": url,
        "KNEXUS_VERIFY_EXPECTED_DATABASE_URL": url,
        "KNEXUS_DISPOSABLE_RUN_ID": "some_other_user",
        "KNEXUS_DISPOSABLE_CONTAINER": "some-container",
        "KNEXUS_DISPOSABLE_VOLUME": "some-vol",
        "KNEXUS_DISPOSABLE_NETWORK": "some-net",
    }
    with pytest.raises(DatabaseGuardError, match="protected port 5435"):
        guard_disposable_database_url(env=env)


# === Missing/Malformed Run Identity & Container Evidence ===
def test_guard_rejects_missing_or_mismatched_run_identity():
    env = _valid_env("valid123", 31234)
    del env["KNEXUS_DISPOSABLE_RUN_ID"]
    with pytest.raises(DatabaseGuardError, match="Missing or invalid unique run identity"):
        guard_disposable_database_url(env=env)

    env["KNEXUS_DISPOSABLE_RUN_ID"] = "bad id with spaces!"
    with pytest.raises(DatabaseGuardError, match="Missing or invalid unique run identity"):
        guard_disposable_database_url(env=env)


def test_guard_rejects_missing_container_evidence():
    env = _valid_env("valid123", 31234)
    del env["KNEXUS_DISPOSABLE_CONTAINER"]
    with pytest.raises(DatabaseGuardError, match="Missing required KNEXUS_DISPOSABLE_CONTAINER"):
        guard_disposable_database_url(env=env)


# === Ownership Label Mismatches (Container, Volume, Network) ===
def test_guard_rejects_container_label_mismatch():
    run_id = "valid123"
    port = 31234
    env = _valid_env(run_id, port)
    c_data = _valid_container_inspect(
        container_name=env["KNEXUS_DISPOSABLE_CONTAINER"],
        volume=env["KNEXUS_DISPOSABLE_VOLUME"],
        network=env["KNEXUS_DISPOSABLE_NETWORK"],
        run_id="DIFFERENT_RUN",
        port=port,
    )
    v_data = _valid_volume_inspect(run_id=run_id)
    n_data = _valid_network_inspect(run_id=run_id)
    with pytest.raises(DatabaseGuardError, match="Container run label"):
        guard_disposable_database_url(env=env, inspect_fn=_make_inspect_fn(c_data, v_data, n_data))


def test_guard_rejects_volume_label_mismatch():
    run_id = "valid123"
    port = 31234
    env = _valid_env(run_id, port)
    c_data = _valid_container_inspect(run_id=run_id, port=port)
    v_data = _valid_volume_inspect(
        volume_name=env["KNEXUS_DISPOSABLE_VOLUME"],
        run_id="WRONG_RUN",
    )
    n_data = _valid_network_inspect(run_id=run_id)
    with pytest.raises(DatabaseGuardError, match="Volume run label"):
        guard_disposable_database_url(env=env, inspect_fn=_make_inspect_fn(c_data, v_data, n_data))


def test_guard_rejects_network_label_mismatch():
    run_id = "valid123"
    port = 31234
    env = _valid_env(run_id, port)
    c_data = _valid_container_inspect(run_id=run_id, port=port)
    v_data = _valid_volume_inspect(run_id=run_id)
    n_data = _valid_network_inspect(
        network_name=env["KNEXUS_DISPOSABLE_NETWORK"],
        run_id="WRONG_RUN",
    )
    with pytest.raises(DatabaseGuardError, match="Network run label"):
        guard_disposable_database_url(env=env, inspect_fn=_make_inspect_fn(c_data, v_data, n_data))


# === Runtime/Mount/Port Mismatches ===
def test_guard_rejects_runtime_port_mismatch():
    run_id = "valid123"
    port = 31234
    env = _valid_env(run_id, port)
    c_data = _valid_container_inspect(
        run_id=run_id,
        port=port,
        rt_ports={"5432/tcp": [{"HostIp": "127.0.0.1", "HostPort": "35555"}]},
    )
    v_data = _valid_volume_inspect(run_id=run_id)
    n_data = _valid_network_inspect(run_id=run_id)
    with pytest.raises(DatabaseGuardError, match="does not match DATABASE_URL port"):
        guard_disposable_database_url(env=env, inspect_fn=_make_inspect_fn(c_data, v_data, n_data))


def test_guard_rejects_bind_mounts():
    run_id = "valid123"
    port = 31234
    env = _valid_env(run_id, port)
    c_data = _valid_container_inspect(
        run_id=run_id,
        port=port,
        binds=["/host/path:/var/lib/postgresql/data"],
    )
    v_data = _valid_volume_inspect(run_id=run_id)
    n_data = _valid_network_inspect(run_id=run_id)
    with pytest.raises(DatabaseGuardError, match="must not have host bind mounts"):
        guard_disposable_database_url(env=env, inspect_fn=_make_inspect_fn(c_data, v_data, n_data))


def test_guard_rejects_stopped_container():
    run_id = "valid123"
    port = 31234
    env = _valid_env(run_id, port)
    c_data = _valid_container_inspect(run_id=run_id, port=port, running=False)
    v_data = _valid_volume_inspect(run_id=run_id)
    n_data = _valid_network_inspect(run_id=run_id)
    with pytest.raises(DatabaseGuardError, match="is not in running state"):
        guard_disposable_database_url(env=env, inspect_fn=_make_inspect_fn(c_data, v_data, n_data))
