"""API-facing Pydantic models for document endpoints.

These schemas define what clients receive.  They deliberately exclude:
- storage paths
- internal status details not meant for clients
- extraction artefacts (pages, raw text)
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from app.services.documents.models import DocumentRecord, DocumentStatus


class DocumentResponse(BaseModel):
    """Public representation of a document record."""

    document_id: str
    filename: str
    content_type: str
    file_extension: str
    file_size_bytes: int
    status: DocumentStatus
    error_message: Optional[str] = None
    page_count: Optional[int] = None
    total_chars: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_record(cls, record: DocumentRecord) -> "DocumentResponse":
        return cls(
            document_id=record.document_id,
            filename=record.original_filename,
            content_type=record.content_type,
            file_extension=record.file_extension,
            file_size_bytes=record.file_size_bytes,
            status=record.status,
            error_message=record.error_message,
            page_count=record.page_count,
            total_chars=record.total_chars,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )


class DocumentListResponse(BaseModel):
    """Paginated-ready list of documents."""

    documents: list[DocumentResponse]
    total: int


class DeleteResponse(BaseModel):
    document_id: str
    deleted: bool
