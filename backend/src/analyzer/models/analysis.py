"""Analysis models for Phase 2 implementation."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from analyzer.models.evidence import Evidence

# Type definitions
AnalysisType = Literal["single", "custom"]
AnalysisLanguage = Literal["ja", "en"]
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


class SingleAnalysis(BaseModel):
    """Result of analyzing a single contribution document."""

    summary: str = Field(..., description="Summary of the document's purpose and proposals")
    changes: list[Change] = Field(default_factory=list, description="Proposed changes")
    issues: list[Issue] = Field(default_factory=list, description="Identified issues")
    evidences: list[Evidence] = Field(default_factory=list, description="Supporting evidence")


class CustomAnalysisResult(BaseModel):
    """Result of custom analysis with user-defined prompt."""

    prompt_text: str = Field(..., description="The custom prompt used for analysis")
    prompt_id: str | None = Field(None, description="ID of saved prompt if used")
    answer: str = Field(..., description="Free-form answer to the custom prompt")
    evidences: list[Evidence] = Field(default_factory=list, description="Supporting evidence")


class AnalysisOptions(BaseModel):
    """Options for analysis execution."""

    include_summary: bool = Field(default=True, description="Include summary in analysis")
    include_changes: bool = Field(default=True, description="Include changes in analysis")
    include_issues: bool = Field(default=True, description="Include issues in analysis")
    language: AnalysisLanguage = Field(
        default="ja", description="Output language for summary and descriptions"
    )


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
    result: SingleAnalysis | CustomAnalysisResult | None = Field(
        None, description="Analysis result"
    )
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
