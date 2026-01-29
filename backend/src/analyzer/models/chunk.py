"""Chunk-related models for document structure extraction."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class StructureType(str, Enum):
    """Type of document structure element."""

    TITLE = "title"
    HEADING1 = "heading1"
    HEADING2 = "heading2"
    HEADING3 = "heading3"
    HEADING4 = "heading4"
    HEADING5 = "heading5"
    HEADING6 = "heading6"
    PARAGRAPH = "paragraph"
    LIST_ITEM = "list_item"
    TABLE = "table"
    FIGURE = "figure"


class ChunkMetadata(BaseModel):
    """Metadata for a document chunk."""

    document_id: str = Field(..., description="Parent document ID")
    contribution_number: str = Field(..., description="3GPP contribution number")
    meeting_id: str | None = Field(None, description="Meeting identifier")
    clause_number: str | None = Field(None, description="Clause/section number (e.g., '5.2.1')")
    clause_title: str | None = Field(None, description="Clause/section title")
    page_number: int | None = Field(None, description="Page number in original document")
    structure_type: StructureType = Field(
        default=StructureType.PARAGRAPH, description="Type of structure element"
    )
    heading_hierarchy: list[str] = Field(
        default_factory=list, description="Parent heading hierarchy"
    )


class Chunk(BaseModel):
    """A chunk of document content with metadata and embedding."""

    id: str = Field(..., description="Firestore document ID")
    content: str = Field(..., description="Text content of the chunk")
    metadata: ChunkMetadata = Field(..., description="Chunk metadata")
    embedding: list[float] | None = Field(None, description="Vector embedding")
    token_count: int = Field(default=0, description="Approximate token count")
    created_at: datetime = Field(default_factory=datetime.utcnow)

    def to_firestore(self) -> dict:
        """Convert to Firestore document format."""
        data = self.model_dump(mode="json")
        return data

    @classmethod
    def from_firestore(cls, doc_id: str, data: dict) -> "Chunk":
        """Create from Firestore document."""
        data["id"] = doc_id
        return cls.model_validate(data)
