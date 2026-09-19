"""Document service — orchestrates upload, retrieval and deletion.

This is the single point of coordination between:
- file storage (``LocalFileStorage``)
- metadata store  (``DocumentStore``)
- extraction layer (pdf / txt extractors)

FastAPI routes call this service; they do not touch storage or extraction directly.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from fastapi import HTTPException, status

from app.core.logging import get_logger
from app.services.documents.models import DocumentRecord, DocumentStatus
from app.services.documents.store import DocumentStore
from app.services.documents.storage import LocalFileStorage
from app.services.extraction.pdf import extract_pdf
from app.services.extraction.txt import extract_txt

logger = get_logger(__name__)


class DocumentService:
    """Coordinates document ingestion and lifecycle."""

    def __init__(self, store: DocumentStore, storage: LocalFileStorage) -> None:
        self._store = store
        self._storage = storage

    # ── Upload ────────────────────────────────────────────────────────────────

    def ingest(
        self,
        *,
        original_filename: str,
        extension: str,
        content_type: str,
        data: bytes,
    ) -> DocumentRecord:
        """Persist and extract a document.  Returns the final ``DocumentRecord``.

        The record status will be PROCESSED on success, FAILED if extraction
        fails (the file is still stored).
        """
        record = DocumentRecord(
            original_filename=original_filename,
            content_type=content_type,
            file_extension=extension,
            file_size_bytes=len(data),
            storage_path=Path("/placeholder"),  # set after storage
            status=DocumentStatus.UPLOADED,
        )
        self._store.save(record)

        # ── 1. Persist file ────────────────────────────────────────────────────
        storage_path = self._storage.store(
            document_id=record.document_id,
            extension=extension,
            data=data,
        )
        record.storage_path = storage_path
        record.mark_processing()
        self._store.save(record)

        # ── 2. Extract ─────────────────────────────────────────────────────────
        try:
            if extension == ".pdf":
                result = extract_pdf(record.document_id, storage_path)
            elif extension == ".txt":
                result = extract_txt(record.document_id, storage_path)
            else:
                raise ValueError(f"No extractor for extension: {extension}")

            record.mark_processed(
                page_count=result.total_pages,
                total_chars=result.total_chars,
            )
        except Exception as exc:
            # Sanitize: log the real cause but store only a safe message
            logger.error(
                "document.extraction_failed",
                document_id=record.document_id,
                error=str(exc),
            )
            record.mark_failed("Text extraction failed.")

        self._store.save(record)
        logger.info(
            "document.ingested",
            document_id=record.document_id,
            status=record.status,
        )
        return record

    # ── Query ─────────────────────────────────────────────────────────────────

    def get(self, document_id: str) -> DocumentRecord:
        """Return a document record or raise 404."""
        record = self._store.get(document_id)
        if record is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document '{document_id}' not found.",
            )
        return record

    def list_all(self) -> List[DocumentRecord]:
        return self._store.list_all()

    # ── Delete ────────────────────────────────────────────────────────────────

    def delete(self, document_id: str) -> None:
        """Delete file and metadata.  Raises 404 for unknown document_id."""
        record = self._store.get(document_id)
        if record is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document '{document_id}' not found.",
            )

        try:
            self._storage.delete(record.storage_path)
        except Exception as exc:
            logger.error(
                "document.delete_storage_error",
                document_id=document_id,
                error=str(exc),
            )
            # Still remove the metadata so the record is not left dangling
        self._store.delete(document_id)
        logger.info("document.deleted", document_id=document_id)
