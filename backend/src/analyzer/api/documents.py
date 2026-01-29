"""Document API endpoints."""

from fastapi import APIRouter, HTTPException, Query

from analyzer.dependencies import DocumentServiceDep, ProcessorServiceDep
from analyzer.models.api import (
    DocumentListResponse,
    DocumentResponse,
    ProcessRequest,
)
from analyzer.models.document import Document, DocumentStatus

router = APIRouter()


def document_to_response(doc: Document) -> DocumentResponse:
    """Convert Document to API response."""
    return DocumentResponse(
        id=doc.id,
        contribution_number=doc.contribution_number,
        title=doc.title,
        source=doc.source,
        meeting_id=doc.meeting.id if doc.meeting else None,
        meeting_name=doc.meeting.name if doc.meeting else None,
        status=doc.status,
        error_message=doc.error_message,
        chunk_count=doc.chunk_count,
        filename=doc.source_file.filename,
        file_size_bytes=doc.source_file.size_bytes,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
    )


@router.get("/documents", response_model=DocumentListResponse)
async def list_documents(
    document_service: DocumentServiceDep,
    meeting_id: str | None = Query(None, description="Filter by meeting ID"),
    status: DocumentStatus | None = Query(None, description="Filter by status"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
):
    """
    List documents with optional filters.

    Returns paginated list of documents with metadata.
    """
    documents, total = await document_service.list_documents(
        meeting_id=meeting_id,
        status=status,
        page=page,
        page_size=page_size,
    )

    return DocumentListResponse(
        documents=[document_to_response(doc) for doc in documents],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/documents/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: str,
    document_service: DocumentServiceDep,
):
    """
    Get a document by ID.

    Returns document metadata and processing status.
    """
    doc = await document_service.get(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    return document_to_response(doc)


@router.post("/documents/{document_id}/process", response_model=DocumentResponse)
async def process_document(
    document_id: str,
    processor: ProcessorServiceDep,
    request: ProcessRequest | None = None,
):
    """
    Trigger document processing.

    Starts the processing pipeline: normalize → chunk → vectorize → index.
    Use the SSE endpoint to monitor progress.
    """
    force = request.force if request else False

    try:
        doc = await processor.process_document(document_id, force=force)
        return document_to_response(doc)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/documents/{document_id}")
async def delete_document(
    document_id: str,
    document_service: DocumentServiceDep,
):
    """
    Delete a document and all associated data.

    Removes the document, its chunks, and storage files.
    """
    deleted = await document_service.delete(document_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Document not found")

    return {"status": "deleted", "document_id": document_id}


@router.get("/documents/{document_id}/download")
async def get_download_url(
    document_id: str,
    document_service: DocumentServiceDep,
    normalized: bool = Query(True, description="Download normalized (docx) or original"),
):
    """
    Get a signed download URL for a document.

    Returns a temporary URL that can be used to download the file.
    """
    url = await document_service.get_download_url(
        document_id,
        normalized=normalized,
    )

    if not url:
        raise HTTPException(
            status_code=404,
            detail="Document or file not found",
        )

    return {"download_url": url}


@router.get("/meetings")
async def list_meetings(
    document_service: DocumentServiceDep,
):
    """
    List all meetings with document counts.

    Returns list of meetings that have synced documents.
    """
    meetings = await document_service.get_meetings()
    return {"meetings": meetings}
