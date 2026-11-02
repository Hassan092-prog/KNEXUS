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
PROTECTED_CONTAINER_NAMES = {"knexus-postgres", "knexus_postgres", "postgres"}
PROTECTED_VOLUME_NAMES = {"knexus_postgres_data", "postgres_data"}
PROTECTED_NETWORK_NAMES = {"knexus_default", "bridge", "host", "none"}
PROTECTED_DB_NAMES = {"knexus", "postgres", "admin", "template1"}
PROTECTED_USERNAMES = {"knexus_admin", "postgres", "admin", "root", "hassan"}

LOOPBACK_HOST = "127.0.0.1"
EXPECTED_SCHEME = "postgresql+asyncpg"
APPROVED_IMAGE_TAG = "pgvector/pgvector:pg16"
APPROVED_IMAGE_ID = "sha256:7b822b0aac60967beb1ea5e576b8602c94c300a157d187f385ae3e0da199b90a"
DEFAULT_OWNER = "hassan-phase1-verification"
DATA_DESTINATION = "/var/lib/postgresql/data"


class DatabaseGuardError(RuntimeError):
    """Raised when a target database fails isolation or ownership validation."""
    pass


def _bounded_docker_inspect(res_type: str, res_name: str, timeout: float = 5.0) -> dict[str, Any]:
    """Inspect a Docker resource with bounded execution timeout."""
    cmd = ["docker", res_type, "inspect", res_name]
    try:
        res = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise DatabaseGuardError(
            f"Docker {res_type} inspect for '{res_name}' timed out after {timeout}s."
        ) from exc
    except Exception as exc:
        raise DatabaseGuardError(
            f"Failed to execute docker {res_type} inspect for '{res_name}': {exc}"
        ) from exc

    if res.returncode != 0:
        raise DatabaseGuardError(
            f"Docker {res_type} inspect failed for '{res_name}' (exit code {res.returncode}): {res.stderr.strip()}"
        )

    try:
        data = json.loads(res.stdout)
        if not isinstance(data, list) or len(data) != 1 or not isinstance(data[0], dict):
            raise ValueError("Expected single JSON object in list")
        return data[0]
    except Exception as exc:
        raise DatabaseGuardError(f"Invalid inspect JSON output for '{res_name}': {exc}") from exc


def guard_disposable_database_url(
    url: str | None = None,
    expected_url: str | None = None,
    env: dict[str, str] | None = None,
    inspect_fn: Callable[[str, str], dict[str, Any]] | None = None,
    inspect_timeout: float = 5.0,
) -> str:
    """Validate that a target database URL points strictly to an owned, disposable container.

    Args:
        url: The target database URL (defaults to os.environ["DATABASE_URL"]).
        expected_url: The expected database URL (defaults to os.environ["KNEXUS_VERIFY_EXPECTED_DATABASE_URL"]).
        env: Mapping of environment variables (defaults to os.environ).
        inspect_fn: Optional callable (res_type, name) -> dict for offline testing.
            Environment-based JSON inspection bypass is prohibited.
        inspect_timeout: Bounded timeout in seconds for live container/resource inspection.

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

    # 1. Scheme check
    if parsed.scheme != EXPECTED_SCHEME:
        raise DatabaseGuardError(f"Target scheme must be '{EXPECTED_SCHEME}', got '{parsed.scheme}'.")

    # 2. Host check
    if parsed.hostname != LOOPBACK_HOST:
        raise DatabaseGuardError(f"Target host must be loopback '{LOOPBACK_HOST}', got '{parsed.hostname}'.")

    # 3. Port check: reject port 5435 unconditionally
    if parsed.port == PROTECTED_SHARED_PORT:
        raise DatabaseGuardError(
            f"Target points to protected port {PROTECTED_SHARED_PORT} (reserved for shared development database)."
        )

    if not parsed.port or not (1024 <= parsed.port <= 65535):
        raise DatabaseGuardError(f"Target port {parsed.port} is invalid or out of range.")

    # 4. Mandatory Run Identity
    run_id = env_map.get("KNEXUS_DISPOSABLE_RUN_ID") or env_map.get("KNEXUS_RUN_TAG")
    if not run_id or not re.fullmatch(r"[A-Za-z0-9_-]{4,64}", run_id):
        raise DatabaseGuardError(
            "Missing or invalid unique run identity (KNEXUS_DISPOSABLE_RUN_ID / KNEXUS_RUN_TAG)."
        )

    # 5. Mandatory Resource Naming & Protected Name Checks
    container_name = env_map.get("KNEXUS_DISPOSABLE_CONTAINER")
    if not container_name:
        raise DatabaseGuardError("Missing required KNEXUS_DISPOSABLE_CONTAINER setting.")
    if container_name in PROTECTED_CONTAINER_NAMES:
        raise DatabaseGuardError(f"Container name '{container_name}' is a protected resource name.")

    volume_name = env_map.get("KNEXUS_DISPOSABLE_VOLUME")
    if not volume_name:
        raise DatabaseGuardError("Missing required KNEXUS_DISPOSABLE_VOLUME setting.")
    if volume_name in PROTECTED_VOLUME_NAMES:
        raise DatabaseGuardError(f"Volume name '{volume_name}' is a protected resource name.")

    network_name = env_map.get("KNEXUS_DISPOSABLE_NETWORK")
    if not network_name:
        raise DatabaseGuardError("Missing required KNEXUS_DISPOSABLE_NETWORK setting.")
    if network_name in PROTECTED_NETWORK_NAMES:
        raise DatabaseGuardError(f"Network name '{network_name}' is a protected or default network.")

    # 6. Synthetic database and username checks
    db_name = (parsed.path or "").lstrip("/")
    if not db_name or db_name in PROTECTED_DB_NAMES:
        raise DatabaseGuardError(f"Target database name '{db_name}' is forbidden or empty.")
    if not (
        db_name.startswith(("knx_test_", "test_knx_", "knexus_test_"))
        or db_name == "knexus_test"
    ):
        raise DatabaseGuardError(f"Target database name '{db_name}' does not follow synthetic naming conventions.")

    username = parsed.username or ""
    if not username or username in PROTECTED_USERNAMES:
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

    expected_owner = env_map.get("KNEXUS_DISPOSABLE_OWNER", DEFAULT_OWNER)

    # 7. Inspection helper (live Docker inspection unless explicit test hook is supplied)
    def inspect_resource(kind: str, name: str) -> dict[str, Any]:
        if inspect_fn is not None:
            return inspect_fn(kind, name)
        return _bounded_docker_inspect(kind, name, timeout=inspect_timeout)

    # 8. Container Inspection & Verification
    c_data = inspect_resource("container", container_name)
    c_state = c_data.get("State", {})
    if c_state.get("Running") is not True:
        raise DatabaseGuardError(f"Disposable container '{container_name}' is not in running state.")

    c_name = c_data.get("Name", "")
    if c_name not in (f"/{container_name}", container_name):
        raise DatabaseGuardError(f"Container inspect name '{c_name}' does not match expected '{container_name}'.")

    # Image tag and immutable Image ID check
    c_config = c_data.get("Config", {})
    cfg_image = c_config.get("Image", "")
    if cfg_image != APPROVED_IMAGE_TAG:
        raise DatabaseGuardError(
            f"Disposable container image tag '{cfg_image}' does not match approved '{APPROVED_IMAGE_TAG}'."
        )
    img_id = c_data.get("Image", "")
    if img_id != APPROVED_IMAGE_ID:
        raise DatabaseGuardError(
            f"Disposable container image ID '{img_id}' does not match approved immutable ID '{APPROVED_IMAGE_ID}'."
        )

    # Container ownership labels
    c_labels = c_config.get("Labels") or {}
    if c_labels.get("com.knexus.pgverify.owner") != expected_owner:
        raise DatabaseGuardError(
            f"Container ownership label 'com.knexus.pgverify.owner' is '{c_labels.get('com.knexus.pgverify.owner')}', expected '{expected_owner}'."
        )
    if c_labels.get("com.knexus.pgverify.run") != run_id:
        raise DatabaseGuardError(
            f"Container run label 'com.knexus.pgverify.run' is '{c_labels.get('com.knexus.pgverify.run')}', expected '{run_id}'."
        )

    # Container Mounts: no bind mounts, exactly one volume mount
    host_cfg = c_data.get("HostConfig", {})
    binds = host_cfg.get("Binds") or []
    if binds:
        raise DatabaseGuardError("Disposable container must not have host bind mounts.")

    mounts = c_data.get("Mounts") or []
    if len(mounts) != 1:
        raise DatabaseGuardError(f"Disposable container must have exactly one mount, found {len(mounts)}.")
    mount = mounts[0]
    if (
        mount.get("Type") != "volume"
        or mount.get("Destination") != DATA_DESTINATION
        or mount.get("RW") is not True
    ):
        raise DatabaseGuardError(
            f"Disposable container mount must be a read-write volume targeting '{DATA_DESTINATION}'."
        )
    if mount.get("Name") != volume_name:
        raise DatabaseGuardError(
            f"Container mounted volume '{mount.get('Name')}' does not match expected '{volume_name}'."
        )

    # Container Networks
    c_net_settings = c_data.get("NetworkSettings", {})
    c_networks = c_net_settings.get("Networks") or {}
    if set(c_networks.keys()) != {network_name}:
        raise DatabaseGuardError(
            f"Disposable container attached networks {list(c_networks.keys())} do not match expected '{network_name}'."
        )

    # Configured port bindings
    configured_bindings = host_cfg.get("PortBindings") or {}
    if not isinstance(configured_bindings, dict) or set(configured_bindings.keys()) != {"5432/tcp"}:
        raise DatabaseGuardError("Configured port bindings must contain only '5432/tcp'.")
    cfg_entries = configured_bindings.get("5432/tcp") or []
    if not isinstance(cfg_entries, list) or len(cfg_entries) != 1:
        raise DatabaseGuardError("Configured port binding count must be exactly one.")
    if cfg_entries[0].get("HostIp") != LOOPBACK_HOST:
        raise DatabaseGuardError(
            f"Configured port binding host IP '{cfg_entries[0].get('HostIp')}' must be loopback '{LOOPBACK_HOST}'."
        )

    # Runtime published port
    c_ports = c_net_settings.get("Ports") or {}
    if not isinstance(c_ports, dict) or set(c_ports.keys()) != {"5432/tcp"}:
        raise DatabaseGuardError("Runtime port bindings must contain only '5432/tcp'.")
    pg_ports = c_ports.get("5432/tcp") or []
    if not isinstance(pg_ports, list) or len(pg_ports) != 1:
        raise DatabaseGuardError("Disposable container must have exactly one runtime published port for 5432/tcp.")
    runtime_binding = pg_ports[0]
    if runtime_binding.get("HostIp") != LOOPBACK_HOST:
        raise DatabaseGuardError(
            f"Disposable container runtime port is bound to '{runtime_binding.get('HostIp')}', expected '{LOOPBACK_HOST}'."
        )
    runtime_host_port = int(runtime_binding.get("HostPort", 0))
    if runtime_host_port != parsed.port:
        raise DatabaseGuardError(
            f"Disposable container inspected runtime port {runtime_host_port} does not match DATABASE_URL port {parsed.port}."
        )

    # 9. Volume Inspection & Ownership Verification
    v_data = inspect_resource("volume", volume_name)
    v_name = v_data.get("Name", "")
    if v_name != volume_name:
        raise DatabaseGuardError(f"Volume inspect name '{v_name}' does not match expected '{volume_name}'.")
    if v_data.get("Driver") != "local":
        raise DatabaseGuardError(f"Volume driver must be 'local', got '{v_data.get('Driver')}'.")
    v_labels = v_data.get("Labels") or {}
    if v_labels.get("com.knexus.pgverify.owner") != expected_owner:
        raise DatabaseGuardError(
            f"Volume ownership label 'com.knexus.pgverify.owner' is '{v_labels.get('com.knexus.pgverify.owner')}', expected '{expected_owner}'."
        )
    if v_labels.get("com.knexus.pgverify.run") != run_id:
        raise DatabaseGuardError(
            f"Volume run label 'com.knexus.pgverify.run' is '{v_labels.get('com.knexus.pgverify.run')}', expected '{run_id}'."
        )

    # 10. Network Inspection & Ownership Verification
    n_data = inspect_resource("network", network_name)
    n_name = n_data.get("Name", "")
    if n_name != network_name:
        raise DatabaseGuardError(f"Network inspect name '{n_name}' does not match expected '{network_name}'.")
    if n_data.get("Driver") != "bridge":
        raise DatabaseGuardError(f"Network driver must be 'bridge', got '{n_data.get('Driver')}'.")
    n_labels = n_data.get("Labels") or {}
    if n_labels.get("com.knexus.pgverify.owner") != expected_owner:
        raise DatabaseGuardError(
            f"Network ownership label 'com.knexus.pgverify.owner' is '{n_labels.get('com.knexus.pgverify.owner')}', expected '{expected_owner}'."
        )
    if n_labels.get("com.knexus.pgverify.run") != run_id:
        raise DatabaseGuardError(
            f"Network run label 'com.knexus.pgverify.run' is '{n_labels.get('com.knexus.pgverify.run')}', expected '{run_id}'."
        )

    return target_url
