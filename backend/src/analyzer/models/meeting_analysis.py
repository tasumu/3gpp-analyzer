"""Data models for meeting analysis (P3-02, P3-06)."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class DocumentSummary(BaseModel):
    """Summary of a single document within a meeting."""

    document_id: str = Field(..., description="Document ID")
    contribution_number: str = Field(..., description="3GPP contribution number")
    title: str = Field(..., description="Document title")
    source: str | None = Field(default=None, description="Contributing company/entity")
    summary: str = Field(..., description="Summary text")
    key_points: list[str] = Field(default_factory=list, description="Key points from the document")
    from_cache: bool = Field(default=False, description="Whether summary was retrieved from cache")


class MeetingSummary(BaseModel):
    """Summary of an entire meeting's contributions."""

    id: str = Field(..., description="Unique identifier for this summary")
    meeting_id: str = Field(..., description="Meeting ID (e.g., 'SA2#162')")
    custom_prompt: str | None = Field(default=None, description="Custom prompt used for analysis")
    individual_summaries: list[DocumentSummary] = Field(
        default_factory=list, description="Summaries of individual documents"
    )
    overall_report: str = Field(..., description="Overall meeting summary report")
    key_topics: list[str] = Field(
        default_factory=list, description="Key topics discussed in the meeting"
    )
    document_count: int = Field(..., description="Total number of documents analyzed")
    language: str = Field(default="ja", description="Output language")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")
    created_by: str | None = Field(default=None, description="User ID who created")

    def to_firestore(self) -> dict[str, Any]:
        """Convert to Firestore-compatible dictionary."""
        return {
            "meeting_id": self.meeting_id,
            "custom_prompt": self.custom_prompt,
            "individual_summaries": [s.model_dump() for s in self.individual_summaries],
            "overall_report": self.overall_report,
            "key_topics": self.key_topics,
            "document_count": self.document_count,
            "language": self.language,
            "created_at": self.created_at,
            "created_by": self.created_by,
        }

    @classmethod
    def from_firestore(cls, doc_id: str, data: dict[str, Any]) -> "MeetingSummary":
        """Create from Firestore document."""
        individual_summaries = [
            DocumentSummary.model_validate(s) for s in data.get("individual_summaries", [])
        ]
        return cls(
            id=doc_id,
            meeting_id=data.get("meeting_id", ""),
            custom_prompt=data.get("custom_prompt"),
            individual_summaries=individual_summaries,
            overall_report=data.get("overall_report", ""),
            key_topics=data.get("key_topics", []),
            document_count=data.get("document_count", 0),
            language=data.get("language", "ja"),
            created_at=data.get("created_at", datetime.utcnow()),
            created_by=data.get("created_by"),
        )


class MeetingReport(BaseModel):
    """Generated meeting report with download URL."""

    id: str = Field(..., description="Unique identifier for this report")
    meeting_id: str = Field(..., description="Meeting ID")
    summary_id: str = Field(..., description="ID of the associated MeetingSummary")
    content: str = Field(..., description="Full report content (Markdown)")
    gcs_path: str = Field(..., description="GCS path where report is stored")
    download_url: str = Field(..., description="Signed download URL")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")
    created_by: str | None = Field(default=None, description="User ID who created")

    def to_firestore(self) -> dict[str, Any]:
        """Convert to Firestore-compatible dictionary."""
        return {
            "meeting_id": self.meeting_id,
            "summary_id": self.summary_id,
            "gcs_path": self.gcs_path,
            "created_at": self.created_at,
            "created_by": self.created_by,
        }


class MeetingSummarizeRequest(BaseModel):
    """Request model for meeting summarization."""

    analysis_prompt: str | None = Field(
        default=None,
        max_length=2000,
        description="Custom prompt for individual document analysis",
    )
    report_prompt: str | None = Field(
        default=None,
        max_length=2000,
        description="Custom prompt for overall report generation",
    )
    language: str = Field(
        default="ja",
        pattern="^(ja|en)$",
        description="Output language: ja (Japanese) or en (English)",
    )
    force: bool = Field(
        default=False,
        description="Force re-analysis even if cached results exist",
    )


class MeetingReportRequest(BaseModel):
    """Request model for meeting report generation."""

    analysis_prompt: str | None = Field(
        default=None,
        max_length=2000,
        description="Custom prompt for individual document analysis",
    )
    report_prompt: str | None = Field(
        default=None,
        max_length=2000,
        description="Custom prompt for report generation",
    )
    language: str = Field(
        default="ja",
        pattern="^(ja|en)$",
        description="Output language",
    )


class MeetingSummaryStreamEvent(BaseModel):
    """Event model for streaming meeting summary progress."""

    type: str = Field(
        ...,
        description="Event type: progress, document_summary, overall_report, done, error",
    )
    progress: dict | None = Field(default=None, description="Progress info for progress events")
    document_summary: DocumentSummary | None = Field(
        default=None, description="Document summary for document_summary events"
    )
    overall_report: str | None = Field(
        default=None, description="Overall report for overall_report events"
    )
    result: MeetingSummary | None = Field(default=None, description="Final result for done events")
    error: str | None = Field(default=None, description="Error message")


class MultiMeetingSummary(BaseModel):
    """Summary of multiple meetings analyzed together."""

    id: str = Field(..., description="Unique identifier for this multi-meeting summary")
    meeting_ids: list[str] = Field(
        ..., description="List of meeting IDs (e.g., ['SA2#162', 'SA2#163'])"
    )
    custom_prompt: str | None = Field(default=None, description="Custom prompt used for analysis")
    individual_meeting_summaries: list[MeetingSummary] = Field(
        default_factory=list, description="Summaries of individual meetings"
    )
    integrated_report: str = Field(..., description="Integrated report across all meetings")
    all_key_topics: list[str] = Field(
        default_factory=list, description="Key topics from all meetings combined"
    )
    language: str = Field(default="ja", description="Output language")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")
    created_by: str | None = Field(default=None, description="User ID who created")

    def to_firestore(self) -> dict[str, Any]:
        """Convert to Firestore-compatible dictionary."""
        return {
            "meeting_ids": self.meeting_ids,
            "custom_prompt": self.custom_prompt,
            "individual_meeting_summaries": [
                s.to_firestore() for s in self.individual_meeting_summaries
            ],
            "integrated_report": self.integrated_report,
            "all_key_topics": self.all_key_topics,
            "language": self.language,
            "created_at": self.created_at,
            "created_by": self.created_by,
        }

    @classmethod
    def from_firestore(cls, doc_id: str, data: dict[str, Any]) -> "MultiMeetingSummary":
        """Create from Firestore document."""
        individual_summaries = []
        for summary_data in data.get("individual_meeting_summaries", []):
            individual_summaries.append(
                MeetingSummary.from_firestore(
                    doc_id=summary_data.get("meeting_id", ""),
                    data=summary_data,
                )
            )
        return cls(
            id=doc_id,
            meeting_ids=data.get("meeting_ids", []),
            custom_prompt=data.get("custom_prompt"),
            individual_meeting_summaries=individual_summaries,
            integrated_report=data.get("integrated_report", ""),
            all_key_topics=data.get("all_key_topics", []),
            language=data.get("language", "ja"),
            created_at=data.get("created_at", datetime.utcnow()),
            created_by=data.get("created_by"),
        )


class MultiMeetingSummarizeRequest(BaseModel):
    """Request model for multi-meeting summarization."""

    meeting_ids: list[str] = Field(
        ...,
        min_length=2,
        max_length=5,
        description="List of meeting IDs to summarize (2-5 meetings)",
    )
    analysis_prompt: str | None = Field(
        default=None,
        max_length=2000,
        description="Custom prompt for individual document analysis",
    )
    report_prompt: str | None = Field(
        default=None,
        max_length=2000,
        description="Custom prompt for integrated report generation",
    )
    language: str = Field(
        default="ja",
        pattern="^(ja|en)$",
        description="Output language: ja (Japanese) or en (English)",
    )
    force: bool = Field(
        default=False,
        description="Force re-analysis even if cached results exist",
    )


class MultiMeetingSummaryStreamEvent(BaseModel):
    """Event model for streaming multi-meeting summary progress."""

    type: str = Field(
        ...,
        description=(
            "Event type: meeting_start, meeting_progress, meeting_complete, "
            "integrated_report, done, error"
        ),
    )
    meeting_id: str | None = Field(
        default=None, description="Meeting ID for meeting-specific events"
    )
    progress: dict | None = Field(default=None, description="Progress info for progress events")
    meeting_summary: MeetingSummary | None = Field(
        default=None, description="Meeting summary for meeting_complete events"
    )
    integrated_report: str | None = Field(
        default=None, description="Integrated report for integrated_report events"
    )
    all_key_topics: list[str] | None = Field(
        default=None, description="All key topics for integrated_report events"
    )
    result: MultiMeetingSummary | None = Field(
        default=None, description="Final result for done events"
    )
    error: str | None = Field(default=None, description="Error message")
