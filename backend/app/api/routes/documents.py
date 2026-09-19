"""Documents API router.

Handles HTTP concerns only — validation, serialization, error mapping.
All business logic is delegated to ``DocumentService``.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, UploadFile, status
from fastapi.responses import JSONResponse

from app.core.dependencies import get_document_service
from app.core.logging import get_logger
from app.models.documents import DeleteResponse, DocumentListResponse, DocumentResponse
from app.services.documents.service import DocumentService
from app.services.documents.validation import validate_upload

logger = get_logger(__name__)

router = APIRouter(prefix="/documents", tags=["documents"])

ServiceDep = Annotated[DocumentService, Depends(get_document_service)]


@router.post(
    "/upload",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a document (PDF or TXT)",
)
async def upload_document(
    file: UploadFile,
    service: ServiceDep,
) -> DocumentResponse:
    """Upload, validate, store, and extract a document."""
    safe_name, extension, content_type, data = await validate_upload(file)
    logger.info(
        "api.upload",
        filename=safe_name,
        extension=extension,
        size_bytes=len(data),
    )
    record = service.ingest(
        original_filename=safe_name,
        extension=extension,
        content_type=content_type,
        data=data,
    )
    return DocumentResponse.from_record(record)


@router.get(
    "",
    response_model=DocumentListResponse,
    summary="List all documents",
)
def list_documents(service: ServiceDep) -> DocumentListResponse:
    """Return metadata for all uploaded documents."""
    records = service.list_all()
    return DocumentListResponse(
        documents=[DocumentResponse.from_record(r) for r in records],
        total=len(records),
    )


@router.get(
    "/{document_id}",
    response_model=DocumentResponse,
    summary="Get a document by ID",
)
def get_document(document_id: str, service: ServiceDep) -> DocumentResponse:
    """Return metadata for a single document."""
    record = service.get(document_id)
    return DocumentResponse.from_record(record)


@router.delete(
    "/{document_id}",
    response_model=DeleteResponse,
    summary="Delete a document",
)
def delete_document(document_id: str, service: ServiceDep) -> DeleteResponse:
    """Delete a document and its stored file."""
    service.delete(document_id)
    return DeleteResponse(document_id=document_id, deleted=True)
