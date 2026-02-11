"""Document API endpoints."""

from fastapi import APIRouter, HTTPException, Query

from analyzer.dependencies import CurrentUserDep, DocumentServiceDep, ProcessorServiceDep
from analyzer.models.api import (
    BatchDeleteRequest,
    BatchOperationResponse,
    BatchProcessRequest,
    ChunkListResponse,
    ChunkMetadataResponse,
    ChunkResponse,
    DocumentListResponse,
    DocumentResponse,
    ProcessRequest,
)
from analyzer.models.document import Document, DocumentStatus, DocumentType

router = APIRouter()


def document_to_response(doc: Document) -> DocumentResponse:
    """Convert Document to API response."""
    return DocumentResponse(
        id=doc.id,
        contribution_number=doc.contribution_number,
        document_type=doc.document_type,
        title=doc.title,
        source=doc.source,
        meeting_id=doc.meeting.id if doc.meeting else None,
        meeting_name=doc.meeting.name if doc.meeting else None,
        status=doc.status,
        analyzable=doc.analyzable,
        error_message=doc.error_message,
        chunk_count=doc.chunk_count,
        filename=doc.source_file.filename,
        ftp_path=doc.source_file.ftp_path,
        file_size_bytes=doc.source_file.size_bytes,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
    )


@router.get("/documents", response_model=DocumentListResponse)
async def list_documents(
    current_user: CurrentUserDep,
    document_service: DocumentServiceDep,
    meeting_id: str | None = Query(None, description="Filter by single meeting ID"),
    meeting_ids: str | None = Query(
        None, description="Filter by multiple meeting IDs (comma-separated, takes precedence)"
    ),
    status: DocumentStatus | None = Query(None, description="Filter by status"),
    document_type: DocumentType | None = Query(None, description="Filter by document type"),
    path_prefix: str | None = Query(None, description="Filter by FTP path prefix"),
    search_text: str | None = Query(
        None, description="Search documents by filename (case-insensitive partial match)"
    ),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
):
    """
    List documents with optional filters.

    Returns paginated list of documents with metadata.
    Supports filtering by multiple meetings via comma-separated meeting_ids parameter.
    """
    # Parse meeting_ids from comma-separated string
    parsed_meeting_ids = None
    if meeting_ids:
        parsed_meeting_ids = [id.strip() for id in meeting_ids.split(",") if id.strip()]

    documents, total = await document_service.list_documents(
        meeting_id=meeting_id,
        meeting_ids=parsed_meeting_ids,
        status=status,
        document_type=document_type,
        path_prefix=path_prefix,
        search_text=search_text,
        page=page,
        page_size=page_size,
    )

    return DocumentListResponse(
        documents=[document_to_response(doc) for doc in documents],
        total=total,
        page=page,
        page_size=page_size,
    )


# Batch operations - must be defined before {document_id} routes to avoid path conflicts
@router.post("/documents/batch/process", response_model=BatchOperationResponse)
async def batch_process_documents(
    request: BatchProcessRequest,
    current_user: CurrentUserDep,
    processor: ProcessorServiceDep,
):
    """
    Batch process multiple documents.

    Processes each document through the pipeline: normalize → chunk → vectorize → index.
    Returns summary of successes and failures.
    """
    success_count = 0
    failed_count = 0
    errors: dict[str, str] = {}

    for doc_id in request.document_ids:
        try:
            await processor.process_document(doc_id, force=request.force)
            success_count += 1
        except Exception as e:
            failed_count += 1
            errors[doc_id] = str(e)

    return BatchOperationResponse(
        total=len(request.document_ids),
        success_count=success_count,
        failed_count=failed_count,
        errors=errors,
    )


@router.delete("/documents/batch", response_model=BatchOperationResponse)
async def batch_delete_documents(
    request: BatchDeleteRequest,
    current_user: CurrentUserDep,
    document_service: DocumentServiceDep,
):
    """
    Batch delete multiple documents.

    Deletes each document and all associated data (chunks, storage files).
    Returns summary of successes and failures.
    """
    success_count = 0
    failed_count = 0
    errors: dict[str, str] = {}

    for doc_id in request.document_ids:
        try:
            deleted = await document_service.delete(doc_id)
            if deleted:
                success_count += 1
            else:
                failed_count += 1
                errors[doc_id] = "Document not found"
        except Exception as e:
            failed_count += 1
            errors[doc_id] = str(e)

    return BatchOperationResponse(
        total=len(request.document_ids),
        success_count=success_count,
        failed_count=failed_count,
        errors=errors,
    )


@router.get("/documents/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: str,
    current_user: CurrentUserDep,
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
    current_user: CurrentUserDep,
    processor: ProcessorServiceDep,
    request: ProcessRequest | None = None,
):
    """
    Trigger document processing.

    Starts the processing pipeline: normalize → chunk → vectorize → index.
    Use the SSE endpoint to monitor progress.
    """
    force = request.force if request else False

    # Check analyzability before processing
    doc = await processor.document_service.get(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if not doc.analyzable:
        raise HTTPException(
            status_code=400,
            detail=f"Document is not analyzable ({doc.source_file.filename}). "
            f"Only .doc, .docx, and .zip files are supported for analysis.",
        )

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
    current_user: CurrentUserDep,
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
    current_user: CurrentUserDep,
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


@router.get("/documents/{document_id}/chunks", response_model=ChunkListResponse)
async def get_document_chunks(
    document_id: str,
    current_user: CurrentUserDep,
    document_service: DocumentServiceDep,
    limit: int = Query(500, ge=1, le=1000, description="Maximum chunks to return"),
):
    """
    Get chunks for a document.

    Returns list of chunks with metadata. Available for indexed documents.
    """
    doc = await document_service.get(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    chunks_data = await document_service.firestore.get_chunks_by_document(document_id, limit=limit)

    chunks = []
    for chunk in chunks_data:
        metadata = chunk.get("metadata", {})
        chunks.append(
            ChunkResponse(
                id=chunk["id"],
                content=chunk.get("content", ""),
                metadata=ChunkMetadataResponse(
                    document_id=metadata.get("document_id", ""),
                    contribution_number=metadata.get("contribution_number", ""),
                    meeting_id=metadata.get("meeting_id"),
                    clause_number=metadata.get("clause_number"),
                    clause_title=metadata.get("clause_title"),
                    page_number=metadata.get("page_number"),
                    structure_type=metadata.get("structure_type", "paragraph"),
                    heading_hierarchy=metadata.get("heading_hierarchy", []),
                ),
                token_count=chunk.get("token_count", 0),
                created_at=chunk.get("created_at"),
            )
        )

    return ChunkListResponse(chunks=chunks, total=len(chunks))


@router.get("/meetings")
async def list_meetings(
    current_user: CurrentUserDep,
    document_service: DocumentServiceDep,
):
    """
    List all meetings with document counts.

    Returns list of meetings that have synced documents.
    """
    meetings = await document_service.get_meetings()
    return {"meetings": meetings}
