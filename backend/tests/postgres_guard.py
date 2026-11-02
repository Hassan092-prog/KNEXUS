"""Hardened isolation guard for disposable PostgreSQL integration test targets.

Ensures test runners never connect to unverified loopback databases or the
protected shared development database on port 5435.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from typing import Any, Callable
from urllib.parse import urlsplit

PROTECTED_SHARED_PORT = 5435
LOOPBACK_HOST = "127.0.0.1"
EXPECTED_SCHEME = "postgresql+asyncpg"
EXPECTED_IMAGE_TAG = "pgvector/pgvector:pg16"
DEFAULT_OWNER = "hassan-phase1-verification"
DATA_DESTINATION = "/var/lib/postgresql/data"


class DatabaseGuardError(RuntimeError):
    """Raised when a target database fails isolation or ownership validation."""
    pass


def _bounded_docker_inspect(container_name: str, timeout: float = 5.0) -> dict[str, Any]:
    """Inspect a Docker container with bounded execution timeout."""
    try:
        res = subprocess.run(
            ["docker", "container", "inspect", container_name],
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise DatabaseGuardError(
            f"Docker container inspection for '{container_name}' timed out after {timeout}s."
        ) from exc
    except Exception as exc:
        raise DatabaseGuardError(
            f"Failed to execute docker container inspect for '{container_name}': {exc}"
        ) from exc

    if res.returncode != 0:
        raise DatabaseGuardError(
            f"Docker container inspect failed for '{container_name}' (exit code {res.returncode}): {res.stderr.strip()}"
        )

    try:
        data = json.loads(res.stdout)
        if not isinstance(data, list) or len(data) != 1 or not isinstance(data[0], dict):
            raise ValueError("Expected single JSON object in list")
        return data[0]
    except Exception as exc:
        raise DatabaseGuardError(f"Invalid inspect JSON output for '{container_name}': {exc}") from exc


def guard_disposable_database_url(
    url: str | None = None,
    expected_url: str | None = None,
    env: dict[str, str] | None = None,
    inspect_fn: Callable[[str], dict[str, Any]] | None = None,
    inspect_timeout: float = 5.0,
) -> str:
    """Validate that a target database URL points strictly to an owned, disposable container.

    Args:
        url: The target database URL (defaults to os.environ["DATABASE_URL"]).
        expected_url: The expected database URL (defaults to os.environ["KNEXUS_VERIFY_EXPECTED_DATABASE_URL"]).
        env: Mapping of environment variables (defaults to os.environ).
        inspect_fn: Optional callable returning inspected container metadata dict
            (used for testing/regressions to avoid running docker commands).
        inspect_timeout: Bounded timeout in seconds for container inspection.

    Returns:
        The verified database URL string.

    Raises:
        DatabaseGuardError: If any safety gate, ownership proof, or inspection fails.
    """
    env_map = os.environ if env is None else env

    target_url = url or env_map.get("DATABASE_URL")
    target_expected = expected_url or env_map.get("KNEXUS_VERIFY_EXPECTED_DATABASE_URL")

    if not target_url:
        raise DatabaseGuardError("DATABASE_URL is not set or empty.")
    if not target_expected:
        raise DatabaseGuardError("KNEXUS_VERIFY_EXPECTED_DATABASE_URL is not set or empty.")
    if target_url != target_expected:
        raise DatabaseGuardError("DATABASE_URL does not match KNEXUS_VERIFY_EXPECTED_DATABASE_URL.")

    parsed = urlsplit(target_url)

    # Scheme check
    if parsed.scheme != EXPECTED_SCHEME:
        raise DatabaseGuardError(f"Target scheme must be '{EXPECTED_SCHEME}', got '{parsed.scheme}'.")

    # Host check
    if parsed.hostname != LOOPBACK_HOST:
        raise DatabaseGuardError(f"Target host must be loopback '{LOOPBACK_HOST}', got '{parsed.hostname}'.")

    # Port check: reject port 5435 regardless of user or database
    if parsed.port == PROTECTED_SHARED_PORT:
        raise DatabaseGuardError(
            f"Target points to protected port {PROTECTED_SHARED_PORT} (reserved for shared development database)."
        )

    if not parsed.port or not (1024 <= parsed.port <= 65535):
        raise DatabaseGuardError(f"Target port {parsed.port} is invalid or out of range.")

    # Unique run identity check
    run_id = env_map.get("KNEXUS_DISPOSABLE_RUN_ID") or env_map.get("KNEXUS_RUN_TAG")
    if not run_id or not re.fullmatch(r"[A-Za-z0-9_-]{4,64}", run_id):
        raise DatabaseGuardError(
            "Missing or invalid unique run identity (KNEXUS_DISPOSABLE_RUN_ID / KNEXUS_RUN_TAG)."
        )

    # Synthetic database and username naming
    db_name = (parsed.path or "").lstrip("/")
    if not db_name or db_name in ("knexus", "postgres", "admin"):
        raise DatabaseGuardError(f"Target database name '{db_name}' is forbidden or empty.")
    if not (
        db_name.startswith(("knx_test_", "test_knx_", "knexus_test_"))
        or db_name == "knexus_test"
    ):
        raise DatabaseGuardError(f"Target database name '{db_name}' does not follow synthetic naming conventions.")

    username = parsed.username or ""
    if not username or username in ("knexus_admin", "postgres", "admin", "root", "hassan"):
        raise DatabaseGuardError(f"Target database username '{username}' is forbidden or empty.")
    if not (
        username.startswith(("knx_user_", "test_knx_", "test_"))
        and (run_id in username or len(username) >= 8)
    ):
        raise DatabaseGuardError(f"Target database username '{username}' does not follow synthetic naming conventions.")

    # Match process env if set
    if env_map.get("POSTGRES_USER") and username != env_map["POSTGRES_USER"]:
        raise DatabaseGuardError(f"Username '{username}' does not match POSTGRES_USER '{env_map['POSTGRES_USER']}'.")
    if env_map.get("POSTGRES_DB") and db_name != env_map["POSTGRES_DB"]:
        raise DatabaseGuardError(f"Database '{db_name}' does not match POSTGRES_DB '{env_map['POSTGRES_DB']}'.")
    if env_map.get("POSTGRES_PORT") and str(parsed.port) != str(env_map["POSTGRES_PORT"]):
        raise DatabaseGuardError(f"Port {parsed.port} does not match POSTGRES_PORT '{env_map['POSTGRES_PORT']}'.")

    # Require container ownership evidence
    container_name = env_map.get("KNEXUS_DISPOSABLE_CONTAINER")
    if not container_name:
        raise DatabaseGuardError("Missing KNEXUS_DISPOSABLE_CONTAINER ownership evidence.")

    # Inspect container
    if inspect_fn is not None:
        inspect_data = inspect_fn(container_name)
    elif env_map.get("KNEXUS_DISPOSABLE_INSPECT_JSON"):
        try:
            raw = json.loads(env_map["KNEXUS_DISPOSABLE_INSPECT_JSON"])
            inspect_data = raw[0] if isinstance(raw, list) else raw
        except Exception as exc:
            raise DatabaseGuardError(f"Failed to parse KNEXUS_DISPOSABLE_INSPECT_JSON: {exc}") from exc
    else:
        inspect_data = _bounded_docker_inspect(container_name, timeout=inspect_timeout)

    # Verify container running state
    state = inspect_data.get("State", {})
    if state.get("Running") is not True:
        raise DatabaseGuardError(f"Disposable container '{container_name}' is not in running state.")

    # Verify image
    config = inspect_data.get("Config", {})
    cfg_image = config.get("Image", "")
    if cfg_image != EXPECTED_IMAGE_TAG and not cfg_image.startswith("pgvector/pgvector"):
        raise DatabaseGuardError(f"Disposable container image '{cfg_image}' does not match expected '{EXPECTED_IMAGE_TAG}'.")

    # Verify labels
    labels = config.get("Labels") or {}
    expected_owner = env_map.get("KNEXUS_DISPOSABLE_OWNER", DEFAULT_OWNER)
    if labels.get("com.knexus.pgverify.owner") != expected_owner:
        raise DatabaseGuardError(
            f"Disposable container ownership label 'com.knexus.pgverify.owner' is '{labels.get('com.knexus.pgverify.owner')}', expected '{expected_owner}'."
        )
    if labels.get("com.knexus.pgverify.run") != run_id:
        raise DatabaseGuardError(
            f"Disposable container run label 'com.knexus.pgverify.run' is '{labels.get('com.knexus.pgverify.run')}', expected '{run_id}'."
        )

    # Verify mounts: no bind mounts, exactly one volume mount to DATA_DESTINATION
    host_config = inspect_data.get("HostConfig", {})
    binds = host_config.get("Binds") or []
    if binds:
        raise DatabaseGuardError("Disposable container must not have host bind mounts.")

    mounts = inspect_data.get("Mounts") or []
    if len(mounts) != 1:
        raise DatabaseGuardError(f"Disposable container must have exactly one mount, found {len(mounts)}.")
    mount = mounts[0]
    if mount.get("Type") != "volume" or mount.get("Destination") != DATA_DESTINATION:
        raise DatabaseGuardError(f"Disposable container mount must be a volume targeting '{DATA_DESTINATION}'.")
    expected_volume = env_map.get("KNEXUS_DISPOSABLE_VOLUME")
    if expected_volume and mount.get("Name") != expected_volume:
        raise DatabaseGuardError(
            f"Disposable container mount volume name '{mount.get('Name')}' does not match expected '{expected_volume}'."
        )

    # Verify network
    network_settings = inspect_data.get("NetworkSettings", {})
    networks = network_settings.get("Networks") or {}
    expected_network = env_map.get("KNEXUS_DISPOSABLE_NETWORK")
    if expected_network and set(networks.keys()) != {expected_network}:
        raise DatabaseGuardError(
            f"Disposable container attached networks {list(networks.keys())} do not match expected '{expected_network}'."
        )

    # Verify runtime published port matches DATABASE_URL port
    ports = network_settings.get("Ports") or {}
    pg_ports = ports.get("5432/tcp")
    if not pg_ports or not isinstance(pg_ports, list) or len(pg_ports) != 1:
        raise DatabaseGuardError("Disposable container does not have exactly one runtime published port for 5432/tcp.")
    runtime_binding = pg_ports[0]
    runtime_host_ip = runtime_binding.get("HostIp")
    if runtime_host_ip != LOOPBACK_HOST:
        raise DatabaseGuardError(f"Disposable container runtime port is bound to '{runtime_host_ip}', expected '{LOOPBACK_HOST}'.")
    runtime_host_port = int(runtime_binding.get("HostPort", 0))
    if runtime_host_port != parsed.port:
        raise DatabaseGuardError(
            f"Disposable container inspected runtime port {runtime_host_port} does not match DATABASE_URL port {parsed.port}."
        )

    return target_url
