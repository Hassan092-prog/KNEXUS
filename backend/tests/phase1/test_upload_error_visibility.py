from io import BytesIO
from pathlib import Path
import logging
import pytest
from starlette.testclient import TestClient
from docx import Document as WordDocument

from app.core.config import settings
from app.core.database import get_db
from app.main import app

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _make_docx() -> bytes:
    doc = WordDocument()
    doc.add_paragraph("Demo test document content.")
    buf = BytesIO()
    doc.save(buf)
    return buf.getvalue()


class FailingSession:
    def __init__(self, exc_to_raise: Exception):
        self.exc_to_raise = exc_to_raise
        self.added = []
        self.rollbacks = 0
        self.commits = 0

    def add(self, row):
        self.added.append(row)

    async def flush(self):
        raise self.exc_to_raise

    async def rollback(self):
        self.rollbacks += 1

    async def commit(self):
        self.commits += 1


def test_upload_missing_demo_seed_logs_remediation_and_returns_safe_500(monkeypatch, tmp_path, caplog):
    """When DB flush fails due to missing demo identity, log seed remediation and return safe 500."""
    monkeypatch.setattr(settings, "DOCUMENT_STORAGE_ROOT", tmp_path / "private")
    caplog.set_level(logging.INFO)

    error_msg = 'insert or update on table "documents" violates foreign key constraint "documents_org_id_fkey" DETAIL: Key (org_id)=(...) is not present in table "organizations".'
    session = FailingSession(RuntimeError(error_msg))

    async def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/documents/upload",
                files=[
                    ("file", ("demo.docx", _make_docx(), DOCX_MIME)),
                    ("allowed_roles", (None, "employee")),
                ],
            )
            assert response.status_code == 500
            body = response.json()
            assert body["code"] == "INTERNAL_ERROR"
            assert body["detail"] == "The upload could not be accepted."
            assert "organizations" not in body["detail"]
            assert "foreign key" not in body["detail"]
            assert "Traceback" not in response.text

            request_id = response.headers.get("x-request-id")
            assert request_id is not None
            assert body["request_id"] == request_id

            # Verify server-side logging
            log_text = caplog.text
            assert f"request_id={request_id}" in log_text
            assert "Upload failed because demo organization or user is missing." in log_text
            assert "Run the seed command from DEMO_RUNBOOK.md:" in log_text
            assert "python -m app.db.demo_seed" in log_text
            assert session.rollbacks == 1
    finally:
        app.dependency_overrides.clear()


def test_upload_generic_flush_error_logs_exception_without_seed_message(monkeypatch, tmp_path, caplog):
    """When DB flush fails generically, log exception with request_id and return safe 500 without seed note."""
    monkeypatch.setattr(settings, "DOCUMENT_STORAGE_ROOT", tmp_path / "private")
    caplog.set_level(logging.INFO)

    session = FailingSession(RuntimeError("disk write failure"))

    async def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/documents/upload",
                files=[
                    ("file", ("demo.docx", _make_docx(), DOCX_MIME)),
                    ("allowed_roles", (None, "employee")),
                ],
            )
            assert response.status_code == 500
            body = response.json()
            assert body["code"] == "INTERNAL_ERROR"
            assert body["detail"] == "The upload could not be accepted."
            assert "disk write failure" not in body["detail"]

            request_id = response.headers.get("x-request-id")
            assert request_id is not None
            assert f"request_id={request_id}" in caplog.text
            assert "disk write failure" in caplog.text
            assert "python -m app.db.demo_seed" not in caplog.text
    finally:
        app.dependency_overrides.clear()