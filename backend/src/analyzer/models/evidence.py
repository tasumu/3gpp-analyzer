"""Evidence model for RAG search results."""

from pydantic import BaseModel, Field


class Evidence(BaseModel):
    """Evidence from a document chunk, used for citation in analysis results."""

    chunk_id: str = Field(..., description="Source chunk ID")
    document_id: str = Field(..., description="Source document ID")
    contribution_number: str = Field(..., description="3GPP contribution number")
    content: str = Field(..., description="Evidence text content")
    clause_number: str | None = Field(None, description="Clause/section number")
    clause_title: str | None = Field(None, description="Clause/section title")
    page_number: int | None = Field(None, description="Page number in original document")
    relevance_score: float = Field(..., description="Relevance score from search", ge=0.0, le=1.0)
    meeting_id: str | None = Field(None, description="Meeting identifier")

    @classmethod
    def from_chunk(cls, chunk_data: dict, relevance_score: float) -> "Evidence":
        """Create Evidence from chunk data and relevance score."""
        metadata = chunk_data.get("metadata", {})
        return cls(
            chunk_id=chunk_data.get("id", ""),
            document_id=metadata.get("document_id", ""),
            contribution_number=metadata.get("contribution_number", ""),
            content=chunk_data.get("content", ""),
            clause_number=metadata.get("clause_number"),
            clause_title=metadata.get("clause_title"),
            page_number=metadata.get("page_number"),
            relevance_score=relevance_score,
            meeting_id=metadata.get("meeting_id"),
        )
