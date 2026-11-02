"""Private local upload storage using generated, traversal-safe keys."""
from __future__ import annotations

import os
from pathlib import Path
import re
from uuid import uuid4

from app.core.config import REPOSITORY_ROOT, settings
from app.services.ingestion.errors import StorageError

_KEY_PATTERN = re.compile(r"^[0-9a-f]{32}\.(?:pdf|docx)$")


def _storage_root() -> Path:
    configured = Path(settings.DOCUMENT_STORAGE_ROOT).expanduser()
    if not configured.is_absolute():
        configured = REPOSITORY_ROOT / configured
    return configured.resolve()


def make_storage_key(source_type: str) -> str:
    if source_type not in {"pdf", "docx"}:
        raise StorageError("Unsupported storage file type.")
    return f"{uuid4().hex}.{source_type}"


def resolve_storage_path(storage_key: str) -> Path:
    if not _KEY_PATTERN.fullmatch(storage_key):
        raise StorageError("The stored file reference is invalid.")
    root = _storage_root()
    path = (root / storage_key).resolve()
    if path.parent != root:
        raise StorageError("The stored file reference is invalid.")
    return path


def write_upload(storage_key: str, content: bytes) -> Path:
    configured = Path(settings.DOCUMENT_STORAGE_ROOT).expanduser()
    if not configured.is_absolute():
        configured = REPOSITORY_ROOT / configured
    try:
        configured.mkdir(mode=0o700, parents=True, exist_ok=True)
        if configured.is_symlink():
            raise StorageError("Private upload storage cannot be a symbolic link.")
        os.chmod(configured, 0o700)
        path = resolve_storage_path(storage_key)
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(path, flags, 0o600)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
        except Exception:
            try:
                path.unlink(missing_ok=True)
            finally:
                raise
        return path
    except StorageError:
        raise
    except OSError as exc:
        raise StorageError("Private upload storage is unavailable.") from exc


def read_upload(storage_key: str) -> bytes:
    path = resolve_storage_path(storage_key)
    try:
        return path.read_bytes()
    except OSError as exc:
        raise StorageError("The stored document is unavailable.") from exc


def delete_upload(storage_key: str) -> None:
    path = resolve_storage_path(storage_key)
    try:
        path.unlink(missing_ok=True)
    except OSError as exc:
        raise StorageError("Private upload cleanup failed.") from exc
