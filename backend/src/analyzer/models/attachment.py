"""Attachment model for user-uploaded supplementary files."""

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class Attachment(BaseModel):
    """User-uploaded supplementary file associated with a meeting."""

    id: str = Field(..., description="Firestore document ID")
    filename: str = Field(..., description="Original filename")
    content_type: str = Field(..., description="MIME type of the file")
    meeting_id: str = Field(..., description="Associated meeting ID")
    gcs_path: str = Field(..., description="GCS path for the uploaded file")
    extracted_text_gcs_path: str | None = Field(
        None, description="GCS path for extracted text content"
    )
    file_size_bytes: int = Field(..., description="File size in bytes")
    uploaded_by: str = Field(..., description="User ID who uploaded the file")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    session_id: str | None = Field(None, description="QA session ID this attachment belongs to")

    def to_firestore(self) -> dict[str, Any]:
        """Convert to Firestore-compatible dictionary."""
        data = self.model_dump(mode="json")
        # Preserve created_at as datetime for Firestore native Timestamp
        data["created_at"] = self.created_at
        return data

    @classmethod
    def from_firestore(cls, doc_id: str, data: dict[str, Any]) -> "Attachment":
        """Create from Firestore document."""
        data["id"] = doc_id
        return cls.model_validate(data)
