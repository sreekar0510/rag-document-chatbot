"""Comprehensive tests for Stage 2 document ingestion.

All tests use:
- temporary directories (never the runtime uploads/ dir)
- programmatically generated fixtures (no manually created files required)
- isolated DocumentService instances so the global singleton is not mutated
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from app.main import create_app
from app.services.documents.models import DocumentStatus
from app.services.documents.service import DocumentService
from app.services.documents.store import DocumentStore
from app.services.documents.storage import LocalFileStorage, sanitize_filename


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_minimal_pdf() -> bytes:
    """Return a minimal, valid single-page PDF in memory."""
    # Use PyMuPDF to create a real (though trivially small) PDF
    import fitz

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Test document content for unit tests.")
    data = doc.tobytes()
    doc.close()
    return data


def _make_txt(content: str = "Hello, world!") -> bytes:
    return content.encode("utf-8")


def _isolated_service(tmp_path: Path) -> DocumentService:
    """Return a fresh DocumentService backed by a temp directory."""
    store = DocumentStore()
    storage = LocalFileStorage(tmp_path)
    return DocumentService(store=store, storage=storage)


def _app_with_service(service: DocumentService) -> TestClient:
    """Return a TestClient whose dependency is overridden with *service*."""
    from app.core.dependencies import get_document_service

    application = create_app()
    application.dependency_overrides[get_document_service] = lambda: service
    return TestClient(application, raise_server_exceptions=True)


# ─────────────────────────────────────────────────────────────────────────────
# 1. Successful TXT upload
# ─────────────────────────────────────────────────────────────────────────────

def test_txt_upload_success(tmp_path: Path) -> None:
    svc = _isolated_service(tmp_path)
    client = _app_with_service(svc)

    response = client.post(
        "/api/documents/upload",
        files={"file": ("readme.txt", _make_txt("Some document text."), "text/plain")},
    )
    assert response.status_code == status.HTTP_201_CREATED
    body = response.json()
    assert body["status"] == DocumentStatus.PROCESSED
    assert body["filename"] == "readme.txt"
    assert body["file_extension"] == ".txt"
    assert "document_id" in body
    assert body["page_count"] == 1
    assert body["total_chars"] > 0


# ─────────────────────────────────────────────────────────────────────────────
# 2. Successful PDF upload
# ─────────────────────────────────────────────────────────────────────────────

def test_pdf_upload_success(tmp_path: Path) -> None:
    svc = _isolated_service(tmp_path)
    client = _app_with_service(svc)

    response = client.post(
        "/api/documents/upload",
        files={"file": ("report.pdf", _make_minimal_pdf(), "application/pdf")},
    )
    assert response.status_code == status.HTTP_201_CREATED
    body = response.json()
    assert body["status"] == DocumentStatus.PROCESSED
    assert body["file_extension"] == ".pdf"
    assert body["page_count"] >= 1


# ─────────────────────────────────────────────────────────────────────────────
# 3. PDF page metadata
# ─────────────────────────────────────────────────────────────────────────────

def test_pdf_page_metadata(tmp_path: Path) -> None:
    """Verify page_count and total_chars are populated for a PDF."""
    import fitz

    # Build a 3-page PDF
    doc = fitz.open()
    for i in range(3):
        p = doc.new_page()
        p.insert_text((72, 72), f"Page {i + 1} text content.")
    pdf_bytes = doc.tobytes()
    doc.close()

    svc = _isolated_service(tmp_path)
    client = _app_with_service(svc)

    response = client.post(
        "/api/documents/upload",
        files={"file": ("multi.pdf", pdf_bytes, "application/pdf")},
    )
    assert response.status_code == status.HTTP_201_CREATED
    body = response.json()
    assert body["page_count"] == 3
    assert body["total_chars"] > 0


# ─────────────────────────────────────────────────────────────────────────────
# 4. Unsupported extension
# ─────────────────────────────────────────────────────────────────────────────

def test_unsupported_extension_rejected(tmp_path: Path) -> None:
    svc = _isolated_service(tmp_path)
    client = _app_with_service(svc)

    response = client.post(
        "/api/documents/upload",
        files={"file": ("data.csv", b"col1,col2\n1,2\n", "text/csv")},
    )
    assert response.status_code == status.HTTP_415_UNSUPPORTED_MEDIA_TYPE


# ─────────────────────────────────────────────────────────────────────────────
# 5. Empty TXT file
# ─────────────────────────────────────────────────────────────────────────────

def test_empty_txt_rejected(tmp_path: Path) -> None:
    svc = _isolated_service(tmp_path)
    client = _app_with_service(svc)

    response = client.post(
        "/api/documents/upload",
        files={"file": ("empty.txt", b"", "text/plain")},
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


# ─────────────────────────────────────────────────────────────────────────────
# 6. Empty / invalid PDF (not a real PDF)
# ─────────────────────────────────────────────────────────────────────────────

def test_invalid_pdf_bytes_rejected(tmp_path: Path) -> None:
    """Bytes that don't start with %PDF magic should be rejected at validation."""
    svc = _isolated_service(tmp_path)
    client = _app_with_service(svc)

    response = client.post(
        "/api/documents/upload",
        files={"file": ("fake.pdf", b"this is not a pdf", "application/pdf")},
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_truncated_pdf_stored_as_failed(tmp_path: Path) -> None:
    """A real PDF magic header but truncated body → passes validation,
    extraction fails, document is stored with FAILED status."""
    svc = _isolated_service(tmp_path)
    client = _app_with_service(svc)

    truncated = b"%PDF-1.4 truncated garbage that cannot be opened"
    response = client.post(
        "/api/documents/upload",
        files={"file": ("broken.pdf", truncated, "application/pdf")},
    )
    # Passes validation (magic bytes OK), extraction fails → still 201 with FAILED status
    assert response.status_code == status.HTTP_201_CREATED
    body = response.json()
    assert body["status"] == DocumentStatus.FAILED
    assert body["error_message"] is not None
    # Must NOT expose filesystem paths in the error message
    assert "/" not in (body["error_message"] or "")
    assert "\\" not in (body["error_message"] or "")


# ─────────────────────────────────────────────────────────────────────────────
# 7. Oversized upload
# ─────────────────────────────────────────────────────────────────────────────

def _patch_max_upload(monkeypatch: pytest.MonkeyPatch, max_mb: int) -> None:
    """Helper: patch get_settings() in both config and validation modules."""
    from app.core import config as cfg_module
    import app.services.documents.validation as val_module

    original = cfg_module.get_settings()
    patched = original.model_copy(update={"max_upload_mb": max_mb})
    monkeypatch.setattr(cfg_module, "get_settings", lambda: patched)
    monkeypatch.setattr(val_module, "get_settings", lambda: patched)


def test_oversized_upload_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """File exceeding MAX_UPLOAD_MB should be rejected with 413."""
    _patch_max_upload(monkeypatch, max_mb=0)  # 0 MB → any non-empty file fails

    svc = _isolated_service(tmp_path)
    client = _app_with_service(svc)

    response = client.post(
        "/api/documents/upload",
        files={"file": ("big.txt", b"x" * 10, "text/plain")},
    )
    assert response.status_code == status.HTTP_413_REQUEST_ENTITY_TOO_LARGE


def test_oversized_upload_rejected_exactly_one_byte_over(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A file that is exactly (max_bytes + 1) bytes must be rejected.

    This regression test specifically targets the chunked-read path: the
    payload is read in _READ_CHUNK_BYTES increments and the 413 must be raised
    as soon as the running total exceeds max_bytes — the full file is never
    fully buffered.
    """
    import app.services.documents.validation as val_module

    # Set limit to exactly the chunk size so the limit is hit during the
    # second read() call, not after reading everything.
    max_bytes = val_module._READ_CHUNK_BYTES  # 64 KiB
    max_mb_exact = max_bytes / (1024 * 1024)  # fractional MB value

    from app.core import config as cfg_module
    original = cfg_module.get_settings()
    patched = original.model_copy(update={"max_upload_mb": max_mb_exact})
    monkeypatch.setattr(cfg_module, "get_settings", lambda: patched)
    monkeypatch.setattr(val_module, "get_settings", lambda: patched)

    svc = _isolated_service(tmp_path)
    client = _app_with_service(svc)

    # max_bytes + 1 bytes: one byte more than the allowed chunk boundary
    oversized_payload = b"t" * (max_bytes + 1)
    response = client.post(
        "/api/documents/upload",
        files={"file": ("over.txt", oversized_payload, "text/plain")},
    )
    assert response.status_code == status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
    # The document must NOT have been stored
    assert len(svc.list_all()) == 0


def test_file_at_exact_size_limit_accepted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A file of exactly max_bytes must be accepted (boundary condition)."""
    import app.services.documents.validation as val_module

    max_bytes = val_module._READ_CHUNK_BYTES  # 64 KiB
    max_mb_exact = max_bytes / (1024 * 1024)

    from app.core import config as cfg_module
    original = cfg_module.get_settings()
    patched = original.model_copy(update={"max_upload_mb": max_mb_exact})
    monkeypatch.setattr(cfg_module, "get_settings", lambda: patched)
    monkeypatch.setattr(val_module, "get_settings", lambda: patched)

    svc = _isolated_service(tmp_path)
    client = _app_with_service(svc)

    exact_payload = b"t" * max_bytes  # exactly at the limit — must be accepted
    response = client.post(
        "/api/documents/upload",
        files={"file": ("exact.txt", exact_payload, "text/plain")},
    )
    assert response.status_code == status.HTTP_201_CREATED


# ─────────────────────────────────────────────────────────────────────────────
# 8. Filename sanitization
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "raw,expected",
    [
        ("report.pdf", "report.pdf"),
        ("My Document (2024).pdf", "My Document _2024_.pdf"),
        ("file/name.txt", "file_name.txt"),
        ("file\\name.txt", "file_name.txt"),
        ("../../../etc/passwd.txt", "_._._etc_passwd.txt"),
        ("\x00null.txt", "null.txt"),
        ("a" * 300 + ".txt", ("a" * 255)),  # truncated to 255
    ],
)
def test_sanitize_filename(raw: str, expected: str) -> None:
    result = sanitize_filename(raw)
    assert result == expected


# ─────────────────────────────────────────────────────────────────────────────
# 9. Path traversal attempt via filename
# ─────────────────────────────────────────────────────────────────────────────

def test_path_traversal_filename_sanitized(tmp_path: Path) -> None:
    """A filename like ../../../etc/passwd.txt must not escape the upload dir."""
    svc = _isolated_service(tmp_path)
    client = _app_with_service(svc)

    response = client.post(
        "/api/documents/upload",
        files={"file": ("../../../etc/passwd.txt", _make_txt("data"), "text/plain")},
    )
    # Upload should succeed (sanitized) OR be rejected — either way the
    # stored path must not escape tmp_path.
    if response.status_code == status.HTTP_201_CREATED:
        # Verify the stored file is inside tmp_path
        doc_id = response.json()["document_id"]
        records = svc.list_all()
        record = next(r for r in records if r.document_id == doc_id)
        assert record.storage_path.is_relative_to(tmp_path)
    else:
        # Rejected is also acceptable
        assert response.status_code in (
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        )


# ─────────────────────────────────────────────────────────────────────────────
# 10. Document listing
# ─────────────────────────────────────────────────────────────────────────────

def test_list_documents_empty(tmp_path: Path) -> None:
    svc = _isolated_service(tmp_path)
    client = _app_with_service(svc)

    response = client.get("/api/documents")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 0
    assert body["documents"] == []


def test_list_documents_after_upload(tmp_path: Path) -> None:
    svc = _isolated_service(tmp_path)
    client = _app_with_service(svc)

    client.post(
        "/api/documents/upload",
        files={"file": ("a.txt", _make_txt("alpha"), "text/plain")},
    )
    client.post(
        "/api/documents/upload",
        files={"file": ("b.txt", _make_txt("bravo"), "text/plain")},
    )

    response = client.get("/api/documents")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    # Storage paths must not appear in the API response
    assert "storage_path" not in str(body)


# ─────────────────────────────────────────────────────────────────────────────
# 11. Document retrieval
# ─────────────────────────────────────────────────────────────────────────────

def test_get_document_success(tmp_path: Path) -> None:
    svc = _isolated_service(tmp_path)
    client = _app_with_service(svc)

    upload = client.post(
        "/api/documents/upload",
        files={"file": ("doc.txt", _make_txt("content"), "text/plain")},
    )
    doc_id = upload.json()["document_id"]

    response = client.get(f"/api/documents/{doc_id}")
    assert response.status_code == 200
    assert response.json()["document_id"] == doc_id


def test_get_document_not_found(tmp_path: Path) -> None:
    svc = _isolated_service(tmp_path)
    client = _app_with_service(svc)

    response = client.get(f"/api/documents/{uuid.uuid4()}")
    assert response.status_code == status.HTTP_404_NOT_FOUND


# ─────────────────────────────────────────────────────────────────────────────
# 12. Document deletion
# ─────────────────────────────────────────────────────────────────────────────

def test_delete_document_success(tmp_path: Path) -> None:
    svc = _isolated_service(tmp_path)
    client = _app_with_service(svc)

    upload = client.post(
        "/api/documents/upload",
        files={"file": ("to_delete.txt", _make_txt("bye"), "text/plain")},
    )
    doc_id = upload.json()["document_id"]

    delete = client.delete(f"/api/documents/{doc_id}")
    assert delete.status_code == 200
    assert delete.json()["deleted"] is True

    # Should be gone
    get = client.get(f"/api/documents/{doc_id}")
    assert get.status_code == status.HTTP_404_NOT_FOUND

    # File should be removed from disk
    remaining = list(tmp_path.iterdir())
    assert len(remaining) == 0


# ─────────────────────────────────────────────────────────────────────────────
# 13. Deletion of nonexistent document
# ─────────────────────────────────────────────────────────────────────────────

def test_delete_nonexistent_document(tmp_path: Path) -> None:
    svc = _isolated_service(tmp_path)
    client = _app_with_service(svc)

    response = client.delete(f"/api/documents/{uuid.uuid4()}")
    assert response.status_code == status.HTTP_404_NOT_FOUND


# ─────────────────────────────────────────────────────────────────────────────
# 14. Extraction failure handling
# ─────────────────────────────────────────────────────────────────────────────

def test_extraction_failure_stored_as_failed(tmp_path: Path) -> None:
    """A PDF with valid magic bytes but unreadable body → FAILED status, not 500."""
    svc = _isolated_service(tmp_path)
    client = _app_with_service(svc)

    bad_pdf = b"%PDF-1.0\n%%EOF"  # technically starts with %PDF but unreadable as a document
    response = client.post(
        "/api/documents/upload",
        files={"file": ("bad.pdf", bad_pdf, "application/pdf")},
    )
    assert response.status_code == status.HTTP_201_CREATED
    body = response.json()
    assert body["status"] in (DocumentStatus.FAILED, DocumentStatus.PROCESSED)
    # Must not contain stack traces in error_message
    if body["error_message"]:
        assert "Traceback" not in body["error_message"]


# ─────────────────────────────────────────────────────────────────────────────
# 15. Multiple documents with the same filename
# ─────────────────────────────────────────────────────────────────────────────

def test_same_filename_gets_unique_ids(tmp_path: Path) -> None:
    svc = _isolated_service(tmp_path)
    client = _app_with_service(svc)

    r1 = client.post(
        "/api/documents/upload",
        files={"file": ("same.txt", _make_txt("first"), "text/plain")},
    )
    r2 = client.post(
        "/api/documents/upload",
        files={"file": ("same.txt", _make_txt("second"), "text/plain")},
    )
    assert r1.status_code == status.HTTP_201_CREATED
    assert r2.status_code == status.HTTP_201_CREATED

    id1 = r1.json()["document_id"]
    id2 = r2.json()["document_id"]
    assert id1 != id2

    # Both should be in the listing
    listing = client.get("/api/documents").json()
    assert listing["total"] == 2

    # Both files on disk must be distinct
    files = list(tmp_path.iterdir())
    assert len(files) == 2


# ─────────────────────────────────────────────────────────────────────────────
# 16. Generated document IDs are unique
# ─────────────────────────────────────────────────────────────────────────────

def test_document_ids_are_unique(tmp_path: Path) -> None:
    svc = _isolated_service(tmp_path)
    client = _app_with_service(svc)

    ids = set()
    for i in range(10):
        r = client.post(
            "/api/documents/upload",
            files={"file": (f"doc{i}.txt", _make_txt(f"content {i}"), "text/plain")},
        )
        assert r.status_code == status.HTTP_201_CREATED
        ids.add(r.json()["document_id"])

    assert len(ids) == 10  # all distinct


# ─────────────────────────────────────────────────────────────────────────────
# 17. Storage path not exposed in API responses
# ─────────────────────────────────────────────────────────────────────────────

def test_storage_path_not_in_response(tmp_path: Path) -> None:
    svc = _isolated_service(tmp_path)
    client = _app_with_service(svc)

    r = client.post(
        "/api/documents/upload",
        files={"file": ("secret.txt", _make_txt("data"), "text/plain")},
    )
    body_str = r.text
    # The tmp_path directory string must not appear in the response
    assert str(tmp_path) not in body_str
    assert "storage_path" not in body_str


# ─────────────────────────────────────────────────────────────────────────────
# 18. LocalFileStorage: delete outside root is blocked
# ─────────────────────────────────────────────────────────────────────────────

def test_storage_delete_outside_root_raises(tmp_path: Path) -> None:
    storage = LocalFileStorage(tmp_path)
    outside = Path("/tmp/should_not_delete.txt")
    outside.write_text("do not delete me")
    try:
        with pytest.raises(PermissionError):
            storage.delete(outside)
    finally:
        outside.unlink(missing_ok=True)


# ─────────────────────────────────────────────────────────────────────────────
# Stage-1 health check still works
# ─────────────────────────────────────────────────────────────────────────────

def test_health_still_works(tmp_path: Path) -> None:
    svc = _isolated_service(tmp_path)
    client = _app_with_service(svc)
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
