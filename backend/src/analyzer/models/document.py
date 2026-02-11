"""Document-related models."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

# File extensions that can be normalized to docx and analyzed
ANALYZABLE_EXTENSIONS = (".doc", ".docx", ".zip")

# All file extensions to collect from FTP (includes download-only formats)
ALL_DOCUMENT_EXTENSIONS = (
    ".doc",
    ".docx",
    ".zip",
    ".pptx",
    ".ppt",
    ".xlsx",
    ".xls",
    ".pdf",
)


class DocumentType(str, Enum):
    """Type of document based on filename pattern."""

    CONTRIBUTION = "contribution"  # Standard SX-XXXXXX format (e.g., S2-2401234)
    OTHER = "other"  # Other documents without contribution number


class DocumentStatus(str, Enum):
    """Status of document processing pipeline."""

    METADATA_ONLY = "metadata_only"  # Only metadata synced from FTP
    DOWNLOADING = "downloading"  # File being downloaded
    DOWNLOADED = "downloaded"  # File downloaded to GCS
    NORMALIZING = "normalizing"  # Converting to docx
    NORMALIZED = "normalized"  # Conversion complete
    CHUNKING = "chunking"  # Extracting structure and chunking
    CHUNKED = "chunked"  # Chunks created
    INDEXING = "indexing"  # Creating embeddings
    INDEXED = "indexed"  # Ready for search
    ERROR = "error"  # Processing failed


class Meeting(BaseModel):
    """3GPP meeting information."""

    id: str = Field(..., description="Meeting identifier (e.g., 'SA2#162')")
    name: str = Field(..., description="Meeting name")
    working_group: str = Field(..., description="Working group (e.g., 'SA2', 'RAN1')")
    date_start: datetime | None = Field(None, description="Meeting start date")
    date_end: datetime | None = Field(None, description="Meeting end date")
    location: str | None = Field(None, description="Meeting location")


class SourceFile(BaseModel):
    """Source file information from FTP."""

    filename: str = Field(..., description="Original filename")
    ftp_path: str = Field(..., description="Full FTP path")
    size_bytes: int = Field(..., description="File size in bytes")
    modified_at: datetime = Field(..., description="Last modified timestamp")
    gcs_original_path: str | None = Field(None, description="GCS path for original file")
    gcs_normalized_path: str | None = Field(None, description="GCS path for normalized docx")


class Document(BaseModel):
    """3GPP document (contribution or other)."""

    id: str = Field(..., description="Firestore document ID")
    contribution_number: str | None = Field(None, description="3GPP contribution number")
    document_type: DocumentType = Field(
        default=DocumentType.CONTRIBUTION, description="Document type based on filename pattern"
    )
    title: str | None = Field(None, description="Document title")
    source: str | None = Field(None, description="Source company/organization")
    meeting: Meeting | None = Field(None, description="Associated meeting")
    source_file: SourceFile = Field(..., description="Source file information")
    status: DocumentStatus = Field(default=DocumentStatus.METADATA_ONLY)
    analyzable: bool = Field(
        default=True,
        description="Whether the document format supports analysis",
    )
    error_message: str | None = Field(None, description="Error message if status is ERROR")
    chunk_count: int = Field(default=0, description="Number of chunks created")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    def to_firestore(self) -> dict:
        """Convert to Firestore document format."""
        data = self.model_dump(mode="json")
        # Firestore handles datetime serialization
        return data

    @classmethod
    def from_firestore(cls, doc_id: str, data: dict) -> "Document":
        """Create from Firestore document."""
        data["id"] = doc_id
        return cls.model_validate(data)
