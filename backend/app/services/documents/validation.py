"""File upload validation utilities.

All validation here operates on raw bytes + filename metadata.
No filesystem I/O is performed.
"""

from __future__ import annotations

from pathlib import PurePosixPath

from fastapi import HTTPException, UploadFile, status

from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.documents.storage import sanitize_filename

logger = get_logger(__name__)

# Chunk size used when reading the upload stream (64 KiB).
# Small enough to keep memory overhead low, large enough to avoid syscall
# overhead on typical documents.
_READ_CHUNK_BYTES = 64 * 1024

# Magic bytes for supported binary types
_PDF_MAGIC = b"%PDF"


def _detect_content_type(data: bytes, extension: str) -> str:
    """Return a normalised content-type string based on bytes + extension.

    Extension is the trusted normalised extension after validation.
    Magic-byte check provides an extra layer against mismatched files.
    """
    if extension == ".pdf":
        if not data.startswith(_PDF_MAGIC):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="File has .pdf extension but does not appear to be a valid PDF.",
            )
        return "application/pdf"
    if extension == ".txt":
        return "text/plain"
    # Should never reach here after extension validation
    return "application/octet-stream"


async def _read_with_size_limit(upload: UploadFile, max_bytes: int) -> bytes:
    """Read *upload* in chunks, raising 413 as soon as the limit is exceeded.

    We do NOT rely on the client-provided Content-Length header because it can
    be absent, spoofed, or wrong (e.g. chunked transfer-encoding).  Instead we
    accumulate chunks and abort early the moment we exceed *max_bytes*.

    Reading one extra byte beyond the limit is intentional: it lets us detect
    an over-limit file even when its size is exactly max_bytes + 1 without
    waiting to read the entire payload.
    """
    chunks: list[bytes] = []
    total = 0

    while True:
        chunk = await upload.read(_READ_CHUNK_BYTES)
        if not chunk:
            break
        chunks.append(chunk)
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File exceeds the maximum allowed size of "
                       f"{get_settings().max_upload_mb} MB.",
            )

    return b"".join(chunks)


async def validate_upload(upload: UploadFile) -> tuple[str, str, str, bytes]:
    """Validate an uploaded file and return (safe_filename, extension, content_type, data).

    Raises ``HTTPException`` on any validation failure.  Callers receive a
    clean error message with no internal paths or stack traces.

    Size is checked *during* reading — the full payload is never loaded into
    memory for over-limit uploads.
    """
    settings = get_settings()

    # ── 1. Filename must exist ─────────────────────────────────────────────────
    if not upload.filename:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Uploaded file must have a filename.",
        )

    # ── 2. Sanitize + check extension ─────────────────────────────────────────
    safe_name = sanitize_filename(upload.filename)
    # Use PurePosixPath so Windows-style separators in filenames are handled
    suffix = PurePosixPath(safe_name).suffix.lower()
    if not suffix or suffix not in settings.allowed_extensions:
        allowed = ", ".join(sorted(settings.allowed_extensions))
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type '{suffix}'. Allowed: {allowed}",
        )

    # ── 3. Read content (enforces size limit during reading) ───────────────────
    max_bytes = settings.max_upload_mb * 1024 * 1024
    data = await _read_with_size_limit(upload, max_bytes)

    # ── 4. Non-empty ──────────────────────────────────────────────────────────
    if not data:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Uploaded file is empty.",
        )

    # ── 5. Content-type detection (magic bytes) ───────────────────────────────
    content_type = _detect_content_type(data, suffix)

    logger.debug(
        "validation.passed",
        safe_filename=safe_name,
        extension=suffix,
        size_bytes=len(data),
    )
    return safe_name, suffix, content_type, data
