"""Data models for Q&A functionality (P3-05)."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from analyzer.models.evidence import Evidence


class QAMode(str, Enum):
    """Mode for Q&A processing."""

    RAG = "rag"  # Traditional RAG-only search
    AGENTIC = "agentic"  # Agentic search with planning and multi-tool exploration


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
    scope_ids: list[str] | None = Field(
        default=None,
        description="Multiple scope identifiers (takes precedence over scope_id)",
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
    session_id: str | None = Field(
        default=None,
        description="Session ID for conversation continuity",
    )
    mode: QAMode = Field(
        default=QAMode.RAG,
        description="Q&A mode: rag (RAG-only) or agentic (multi-tool exploration)",
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
    mode: QAMode = Field(
        default=QAMode.RAG,
        description="Q&A mode used for this result",
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
            "mode": self.mode.value,
            "evidences": [ev.model_dump(mode="json") for ev in self.evidences],
            "created_at": self.created_at,
            "created_by": self.created_by,
        }

    @classmethod
    def from_firestore(cls, doc_id: str, data: dict[str, Any]) -> "QAResult":
        """Create from Firestore document."""
        evidences = [Evidence.model_validate(ev) for ev in data.get("evidences", [])]
        return cls(
            id=doc_id,
            question=data.get("question", ""),
            answer=data.get("answer", ""),
            scope=QAScope(data.get("scope", "global")),
            scope_id=data.get("scope_id"),
            mode=QAMode(data.get("mode", "rag")),
            evidences=evidences,
            created_at=data.get("created_at", datetime.utcnow()),
            created_by=data.get("created_by"),
        )


class QAReport(BaseModel):
    """Generated QA report with download URL."""

    id: str = Field(..., description="Unique identifier for this report")
    qa_result_id: str = Field(..., description="ID of the source QAResult")
    question: str = Field(..., description="Original question")
    gcs_path: str = Field(..., description="GCS path where report is stored")
    download_url: str = Field(..., description="Signed download URL")
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Creation timestamp",
    )
    created_by: str | None = Field(default=None, description="User ID who created")
    is_public: bool = Field(default=False, description="Whether report is visible to all users")

    def to_firestore(self) -> dict[str, Any]:
        """Convert to Firestore-compatible dictionary."""
        return {
            "qa_result_id": self.qa_result_id,
            "question": self.question,
            "gcs_path": self.gcs_path,
            "created_at": self.created_at,
            "created_by": self.created_by,
            "is_public": self.is_public,
        }


class QAStreamEvent(BaseModel):
    """Event model for Q&A streaming responses."""

    type: str = Field(..., description="Event type: chunk, evidence, done, error")
    content: str | None = Field(default=None, description="Text content for chunk events")
    evidence: Evidence | None = Field(default=None, description="Evidence for evidence events")
    error: str | None = Field(default=None, description="Error message for error events")
    result: QAResult | None = Field(default=None, description="Final result for done events")
