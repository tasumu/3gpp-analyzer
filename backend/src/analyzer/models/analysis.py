"""Analysis models for Phase 2 implementation."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from analyzer.models.evidence import Evidence

# Type definitions
AnalysisType = Literal["single", "compare"]
AnalysisStatus = Literal["pending", "processing", "completed", "failed"]
ChangeType = Literal["addition", "modification", "deletion"]
Severity = Literal["high", "medium", "low"]


class Change(BaseModel):
    """A proposed change in a contribution document."""

    type: ChangeType = Field(..., description="Type of change")
    description: str = Field(..., description="Description of the change")
    clause: str | None = Field(None, description="Related clause/section number")


class Issue(BaseModel):
    """A potential issue or discussion point identified in the document."""

    description: str = Field(..., description="Description of the issue")
    severity: Severity = Field(..., description="Severity level")


class Difference(BaseModel):
    """A difference between documents in comparison analysis."""

    aspect: str = Field(..., description="The aspect being compared")
    doc1_position: str = Field(..., description="Position of document 1")
    doc2_position: str = Field(..., description="Position of document 2")


class SingleAnalysis(BaseModel):
    """Result of analyzing a single contribution document."""

    summary: str = Field(..., description="Summary of the document's purpose and proposals")
    changes: list[Change] = Field(default_factory=list, description="Proposed changes")
    issues: list[Issue] = Field(default_factory=list, description="Identified issues")
    evidences: list[Evidence] = Field(default_factory=list, description="Supporting evidence")


class CompareAnalysis(BaseModel):
    """Result of comparing multiple contribution documents."""

    common_points: list[str] = Field(default_factory=list, description="Common points")
    differences: list[Difference] = Field(default_factory=list, description="Differences")
    recommendation: str = Field(..., description="Recommended action")
    evidences: list[Evidence] = Field(default_factory=list, description="Supporting evidence")


class AnalysisOptions(BaseModel):
    """Options for analysis execution."""

    include_summary: bool = Field(default=True, description="Include summary in analysis")
    include_changes: bool = Field(default=True, description="Include changes in analysis")
    include_issues: bool = Field(default=True, description="Include issues in analysis")


class AnalysisRequest(BaseModel):
    """Request to start an analysis."""

    type: AnalysisType = Field(..., description="Type of analysis")
    contribution_numbers: list[str] = Field(
        ..., description="Contribution numbers to analyze", min_length=1, max_length=2
    )
    options: AnalysisOptions = Field(
        default_factory=AnalysisOptions, description="Analysis options"
    )
    force: bool = Field(default=False, description="Force re-analysis even if cached")


class AnalysisResult(BaseModel):
    """Persistent analysis result."""

    id: str = Field(..., description="Analysis result ID")
    document_id: str = Field(..., description="Primary document ID")
    document_ids: list[str] = Field(default_factory=list, description="All document IDs involved")
    contribution_number: str = Field(..., description="Primary contribution number")
    type: AnalysisType = Field(..., description="Type of analysis")
    status: AnalysisStatus = Field(..., description="Analysis status")
    strategy_version: str = Field(..., description="Analysis strategy version")
    options: AnalysisOptions = Field(default_factory=AnalysisOptions, description="Options used")
    result: SingleAnalysis | CompareAnalysis | None = Field(None, description="Analysis result")
    review_sheet_path: str | None = Field(None, description="GCS path to review sheet")
    error_message: str | None = Field(None, description="Error message if failed")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation time")
    completed_at: datetime | None = Field(None, description="Completion time")
    created_by: str | None = Field(None, description="User ID who created the analysis")

    def to_firestore(self) -> dict:
        """Convert to Firestore document format."""
        data = self.model_dump(mode="json")
        # Firestore timestamp conversion if needed
        return data

    @classmethod
    def from_firestore(cls, doc_id: str, data: dict) -> "AnalysisResult":
        """Create from Firestore document."""
        data["id"] = doc_id
        return cls.model_validate(data)


class AnalysisStreamEvent(BaseModel):
    """Event for SSE streaming during analysis."""

    event: Literal["progress", "partial", "complete", "error"] = Field(
        ..., description="Event type"
    )
    stage: str | None = Field(None, description="Current stage of analysis")
    progress: int | None = Field(None, description="Progress percentage (0-100)")
    partial_result: dict | None = Field(None, description="Partial result data")
    analysis_id: str | None = Field(None, description="Analysis ID on completion")
    error: str | None = Field(None, description="Error message if failed")
