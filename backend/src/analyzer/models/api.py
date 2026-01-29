"""API request and response schemas."""

from datetime import datetime

from pydantic import BaseModel, Field

from analyzer.models.document import DocumentStatus


class DocumentResponse(BaseModel):
    """Response model for a single document."""

    id: str
    contribution_number: str
    title: str | None
    source: str | None
    meeting_id: str | None
    meeting_name: str | None
    status: DocumentStatus
    error_message: str | None
    chunk_count: int
    filename: str
    file_size_bytes: int
    created_at: datetime
    updated_at: datetime


class DocumentListResponse(BaseModel):
    """Response model for document list."""

    documents: list[DocumentResponse]
    total: int
    page: int = 1
    page_size: int = 50


class ProcessRequest(BaseModel):
    """Request to process a document."""

    force: bool = Field(default=False, description="Force reprocessing even if already processed")


class SyncRequest(BaseModel):
    """Request to sync documents from FTP."""

    meeting_id: str = Field(..., description="Meeting identifier to sync")
    path_pattern: str | None = Field(
        None, description="Optional path pattern to filter files"
    )


class SyncResponse(BaseModel):
    """Response from FTP sync operation."""

    meeting_id: str
    documents_found: int
    documents_new: int
    documents_updated: int
    errors: list[str] = Field(default_factory=list)


class NormalizeRequest(BaseModel):
    """Request to normalize a document."""

    document_id: str = Field(..., description="Document ID to normalize")


class NormalizeResponse(BaseModel):
    """Response from normalization operation."""

    document_id: str
    success: bool
    normalized_path: str | None = None
    error: str | None = None


class IndexRequest(BaseModel):
    """Request to index a document."""

    document_id: str = Field(..., description="Document ID to index")


class IndexResponse(BaseModel):
    """Response from indexing operation."""

    document_id: str
    success: bool
    chunks_created: int = 0
    error: str | None = None


class StatusUpdate(BaseModel):
    """Server-sent event for document status updates."""

    document_id: str
    status: DocumentStatus
    progress: float = Field(default=0.0, ge=0.0, le=1.0, description="Progress percentage")
    message: str | None = None
    error: str | None = None
