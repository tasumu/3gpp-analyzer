"""Data models for Q&A functionality (P3-05)."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from analyzer.models.evidence import Evidence


class QAScope(str, Enum):
    """Scope for Q&A searches."""

    DOCUMENT = "document"  # Single document
    MEETING = "meeting"  # All documents in a meeting
    GLOBAL = "global"  # All indexed documents


class QARequest(BaseModel):
    """Request model for Q&A API."""

    question: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="The question to answer",
    )
    scope: QAScope = Field(
        default=QAScope.GLOBAL,
        description="Search scope: document, meeting, or global",
    )
    scope_id: str | None = Field(
        default=None,
        description="Scope identifier: document_id (scope=document) or meeting_id (scope=meeting)",
    )
    filters: dict[str, Any] | None = Field(
        default=None,
        description="Additional metadata filters for search",
    )
    language: str = Field(
        default="ja",
        pattern="^(ja|en)$",
        description="Response language: ja (Japanese) or en (English)",
    )


class QAResult(BaseModel):
    """Result model for Q&A responses."""

    id: str = Field(..., description="Unique identifier for this Q&A result")
    question: str = Field(..., description="The original question")
    answer: str = Field(..., description="The generated answer")
    scope: QAScope = Field(..., description="Search scope used")
    scope_id: str | None = Field(default=None, description="Scope identifier used")
    evidences: list[Evidence] = Field(
        default_factory=list,
        description="List of evidence chunks used to generate the answer",
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp when the result was created",
    )
    created_by: str | None = Field(
        default=None,
        description="User ID who initiated the Q&A",
    )

    def to_firestore(self) -> dict[str, Any]:
        """Convert to Firestore-compatible dictionary."""
        return {
            "question": self.question,
            "answer": self.answer,
            "scope": self.scope.value,
            "scope_id": self.scope_id,
            "evidences": [ev.model_dump(mode="json") for ev in self.evidences],
            "created_at": self.created_at,
            "created_by": self.created_by,
        }

    @classmethod
    def from_firestore(cls, doc_id: str, data: dict[str, Any]) -> "QAResult":
        """Create from Firestore document."""
        evidences = [
            Evidence.model_validate(ev) for ev in data.get("evidences", [])
        ]
        return cls(
            id=doc_id,
            question=data.get("question", ""),
            answer=data.get("answer", ""),
            scope=QAScope(data.get("scope", "global")),
            scope_id=data.get("scope_id"),
            evidences=evidences,
            created_at=data.get("created_at", datetime.utcnow()),
            created_by=data.get("created_by"),
        )


class QAStreamEvent(BaseModel):
    """Event model for Q&A streaming responses."""

    type: str = Field(..., description="Event type: chunk, evidence, done, error")
    content: str | None = Field(default=None, description="Text content for chunk events")
    evidence: Evidence | None = Field(
        default=None, description="Evidence for evidence events"
    )
    error: str | None = Field(default=None, description="Error message for error events")
    result: QAResult | None = Field(
        default=None, description="Final result for done events"
    )
