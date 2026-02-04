"""API request and response schemas."""

from datetime import datetime

from pydantic import BaseModel, Field

from analyzer.models.document import DocumentStatus, DocumentType


class DocumentResponse(BaseModel):
    """Response model for a single document."""

    id: str
    contribution_number: str | None
    document_type: DocumentType
    title: str | None
    source: str | None
    meeting_id: str | None
    meeting_name: str | None
    status: DocumentStatus
    error_message: str | None
    chunk_count: int
    filename: str
    ftp_path: str
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


class BatchProcessRequest(BaseModel):
    """Request to batch process multiple documents."""

    document_ids: list[str] = Field(
        ..., min_length=1, max_length=100, description="Document IDs to process"
    )
    force: bool = Field(default=False, description="Force reprocessing even if already processed")


class BatchDeleteRequest(BaseModel):
    """Request to batch delete multiple documents."""

    document_ids: list[str] = Field(
        ..., min_length=1, max_length=100, description="Document IDs to delete"
    )


class BatchOperationResponse(BaseModel):
    """Response for batch operations."""

    total: int = Field(..., description="Total number of documents in the request")
    success_count: int = Field(..., description="Number of successfully processed documents")
    failed_count: int = Field(..., description="Number of failed documents")
    errors: dict[str, str] = Field(
        default_factory=dict, description="Map of document_id to error message"
    )


class SyncRequest(BaseModel):
    """Request to sync documents from FTP."""

    meeting_id: str = Field(..., description="Meeting identifier to sync")
    path_pattern: str | None = Field(None, description="Optional path pattern to filter files")


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


# FTP Browser schemas


class FTPDirectoryEntry(BaseModel):
    """Entry in FTP directory listing."""

    name: str
    type: str = Field(..., description="'directory' or 'file'")
    size: int | None = Field(None, description="File size in bytes (files only)")
    synced: bool = Field(False, description="Whether documents have been synced (directories only)")
    synced_count: int | None = Field(
        None, description="Number of synced documents (directories only)"
    )


class FTPBrowseResponse(BaseModel):
    """Response from FTP browse endpoint."""

    path: str = Field(..., description="Current directory path")
    parent: str | None = Field(None, description="Parent directory path")
    entries: list[FTPDirectoryEntry] = Field(default_factory=list)


class FTPSyncRequest(BaseModel):
    """Request to sync documents from an FTP path."""

    path: str = Field(..., description="FTP directory path to sync")
    path_pattern: str | None = Field(None, description="Optional regex to filter files")
    include_non_contributions: bool = Field(
        True, description="Include files without contribution numbers"
    )


class FTPSyncProgress(BaseModel):
    """Progress update for FTP sync operation."""

    sync_id: str
    status: str = Field(..., description="'running', 'completed', or 'error'")
    message: str | None = None
    current: int = 0
    total: int = 0
    documents_found: int = 0
    documents_new: int = 0
    documents_updated: int = 0
    errors: list[str] = Field(default_factory=list)


# Chunk schemas


class ChunkMetadataResponse(BaseModel):
    """Response model for chunk metadata."""

    document_id: str
    contribution_number: str | None = None
    meeting_id: str | None = None
    clause_number: str | None = None
    clause_title: str | None = None
    page_number: int | None = None
    structure_type: str
    heading_hierarchy: list[str] = Field(default_factory=list)


class ChunkResponse(BaseModel):
    """Response model for a single chunk."""

    id: str
    content: str
    metadata: ChunkMetadataResponse
    token_count: int
    created_at: datetime


class ChunkListResponse(BaseModel):
    """Response model for chunk list."""

    chunks: list[ChunkResponse]
    total: int
