"""Meeting analysis API endpoints for P3-02 and P3-06."""

import json
import logging

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from analyzer.dependencies import (
    CurrentUserDep,
    CurrentUserQueryDep,
    DocumentServiceDep,
    MeetingReportGeneratorDep,
    MeetingServiceDep,
    ProcessorServiceDep,
)
from analyzer.models.document import DocumentStatus
from analyzer.models.meeting_analysis import (
    MeetingReportRequest,
    MeetingSummarizeRequest,
    MeetingSummary,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/meetings", tags=["meetings"])


class MeetingSummaryResponse(BaseModel):
    """Response model for meeting summary."""

    id: str
    meeting_id: str
    custom_prompt: str | None
    overall_report: str
    key_topics: list[str]
    document_count: int
    language: str
    created_at: str
    summaries: list[dict]


class MeetingReportResponse(BaseModel):
    """Response model for meeting report."""

    report_id: str
    meeting_id: str
    download_url: str
    summary_id: str


class BatchProcessRequest(BaseModel):
    """Request model for batch processing."""

    force: bool = Field(default=False, description="Force reprocess already indexed docs")
    concurrency: int = Field(default=3, ge=1, le=10, description="Max concurrent processes")


def meeting_summary_to_response(summary: MeetingSummary) -> MeetingSummaryResponse:
    """Convert MeetingSummary to API response."""
    return MeetingSummaryResponse(
        id=summary.id,
        meeting_id=summary.meeting_id,
        custom_prompt=summary.custom_prompt,
        overall_report=summary.overall_report,
        key_topics=summary.key_topics,
        document_count=summary.document_count,
        language=summary.language,
        created_at=summary.created_at.isoformat(),
        summaries=[
            {
                "document_id": s.document_id,
                "contribution_number": s.contribution_number,
                "title": s.title,
                "source": s.source,
                "summary": s.summary,
                "key_points": s.key_points,
                "from_cache": s.from_cache,
            }
            for s in summary.individual_summaries
        ],
    )


@router.post("/{meeting_id}/summarize", response_model=MeetingSummaryResponse)
async def summarize_meeting(
    meeting_id: str,
    request: MeetingSummarizeRequest,
    current_user: CurrentUserDep,
    meeting_service: MeetingServiceDep,
):
    """
    Summarize all contributions in a meeting (P3-02).

    This endpoint:
    1. Retrieves all indexed documents for the meeting
    2. Summarizes each document individually (using lightweight model)
    3. Generates an overall meeting report (using high-performance model)

    The custom_prompt parameter allows focusing the analysis on specific aspects
    (e.g., "Focus on security implications" or "Highlight UE power saving topics").

    Results are cached and reused unless force=true.
    """
    try:
        result = await meeting_service.summarize_meeting(
            meeting_id=meeting_id,
            custom_prompt=request.custom_prompt,
            language=request.language,
            user_id=current_user.uid,
            force=request.force,
        )
        return meeting_summary_to_response(result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error summarizing meeting {meeting_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to summarize meeting")


@router.get("/{meeting_id}/summarize/stream")
async def summarize_meeting_stream(
    meeting_id: str,
    current_user: CurrentUserQueryDep,
    meeting_service: MeetingServiceDep,
    custom_prompt: str | None = Query(None, max_length=2000),
    language: str = Query("ja", pattern="^(ja|en)$"),
    force: bool = Query(False),
):
    """
    Summarize meeting with streaming progress updates (SSE).

    Events:
    - progress: Processing progress update
    - document_summary: Individual document summary completed
    - overall_report: Overall report generated
    - done: Final result with complete summary
    - error: Error message
    """

    async def event_generator():
        try:
            async for event in meeting_service.summarize_meeting_stream(
                meeting_id=meeting_id,
                custom_prompt=custom_prompt,
                language=language,
                user_id=current_user.uid,
                force=force,
            ):
                if event.type == "progress":
                    # Map backend progress format to frontend expected format
                    progress_data = {
                        "event": "progress",
                        "current": event.progress.get("processed", 0),
                        "total": event.progress.get("total_documents", 0),
                        "contribution_number": event.progress.get("current_document", ""),
                    }
                    yield {
                        "event": "progress",
                        "data": json.dumps(progress_data),
                    }
                elif event.type == "document_summary":
                    # Send progress event for document_summary
                    if event.progress:
                        progress_data = {
                            "event": "progress",
                            "current": event.progress.get("processed", 0),
                            "total": event.progress.get("total_documents", 0),
                            "contribution_number": event.progress.get("current_document", ""),
                        }
                        yield {
                            "event": "progress",
                            "data": json.dumps(progress_data),
                        }
                    yield {
                        "event": "document_summary",
                        "data": json.dumps(
                            {
                                "document_id": event.document_summary.document_id,
                                "contribution_number": event.document_summary.contribution_number,
                                "title": event.document_summary.title,
                                "summary": event.document_summary.summary[:200] + "..."
                                if len(event.document_summary.summary) > 200
                                else event.document_summary.summary,
                                "from_cache": event.document_summary.from_cache,
                            }
                        ),
                    }
                elif event.type == "overall_report":
                    yield {
                        "event": "overall_report",
                        "data": json.dumps(
                            {
                                "report": event.overall_report[:500] + "..."
                                if len(event.overall_report) > 500
                                else event.overall_report,
                            }
                        ),
                    }
                elif event.type == "done":
                    # Send complete event with full summary for frontend compatibility
                    summary_response = meeting_summary_to_response(event.result)
                    yield {
                        "event": "complete",
                        "data": json.dumps(
                            {
                                "event": "complete",
                                "summary": summary_response.model_dump(),
                            }
                        ),
                    }
                elif event.type == "error":
                    yield {
                        "event": "error",
                        "data": json.dumps({"error": event.error}),
                    }
        except Exception as e:
            logger.error(f"Error in meeting summary stream: {e}")
            yield {
                "event": "error",
                "data": json.dumps({"error": str(e)}),
            }

    return EventSourceResponse(event_generator())


@router.get("/{meeting_id}/summary/{summary_id}", response_model=MeetingSummaryResponse)
async def get_meeting_summary(
    meeting_id: str,
    summary_id: str,
    current_user: CurrentUserDep,
    meeting_service: MeetingServiceDep,
):
    """Get a specific meeting summary by ID."""
    result = await meeting_service.get_summary(summary_id)
    if not result:
        raise HTTPException(status_code=404, detail="Summary not found")
    if result.meeting_id != meeting_id:
        raise HTTPException(status_code=404, detail="Summary not found for this meeting")
    return meeting_summary_to_response(result)


@router.get("/{meeting_id}/summaries", response_model=list[MeetingSummaryResponse])
async def list_meeting_summaries(
    meeting_id: str,
    current_user: CurrentUserDep,
    meeting_service: MeetingServiceDep,
    limit: int = Query(10, ge=1, le=50),
):
    """List all summaries for a specific meeting."""
    results = await meeting_service.list_summaries(
        meeting_id=meeting_id,
        limit=limit,
    )
    return [meeting_summary_to_response(r) for r in results]


@router.get("/{meeting_id}/info")
async def get_meeting_info(
    meeting_id: str,
    current_user: CurrentUserDep,
    document_service: DocumentServiceDep,
):
    """
    Get meeting information including document counts.

    Returns document statistics for the meeting.
    """
    # Get total documents
    _, total = await document_service.list_documents(
        meeting_id=meeting_id,
        page_size=1,
    )

    # Get indexed documents
    _, indexed = await document_service.list_documents(
        meeting_id=meeting_id,
        status=DocumentStatus.INDEXED,
        page_size=1,
    )

    # Parse meeting_id to get working group
    parts = meeting_id.split("#")
    working_group = parts[0] if parts else "Unknown"
    meeting_number = parts[1] if len(parts) > 1 else "Unknown"

    return {
        "meeting_id": meeting_id,
        "working_group": working_group,
        "meeting_number": meeting_number,
        "total_documents": total,
        "indexed_documents": indexed,
        "unindexed_count": total - indexed,
        "ready_for_analysis": indexed > 0,
    }


# ============================================================================
# Batch Processing Endpoints
# ============================================================================


@router.get("/{meeting_id}/process/stream")
async def batch_process_meeting_stream(
    meeting_id: str,
    current_user: CurrentUserQueryDep,
    document_service: DocumentServiceDep,
    processor: ProcessorServiceDep,
    force: bool = Query(False, description="Force reprocess already indexed docs"),
    concurrency: int = Query(3, ge=1, le=10, description="Max concurrent processes"),
):
    """
    Batch process all unindexed documents in a meeting with streaming progress (SSE).

    Events:
    - batch_start: Processing started with total document count
    - document_start: Started processing a specific document
    - document_progress: Progress update for current document
    - document_complete: Document processing completed (success or failure)
    - batch_complete: All documents processed
    - error: Error occurred
    """

    async def event_generator():
        try:
            # Get documents to process
            if force:
                # Get all documents
                documents, _ = await document_service.list_documents(
                    meeting_id=meeting_id,
                    page_size=1000,
                )
            else:
                # Get only unindexed documents (not INDEXED status)
                all_docs, _ = await document_service.list_documents(
                    meeting_id=meeting_id,
                    page_size=1000,
                )
                documents = [doc for doc in all_docs if doc.status != DocumentStatus.INDEXED]

            if not documents:
                yield {
                    "event": "batch_complete",
                    "data": json.dumps(
                        {
                            "total": 0,
                            "success_count": 0,
                            "failed_count": 0,
                            "message": "No documents to process",
                        }
                    ),
                }
                return

            document_ids = [doc.id for doc in documents]

            async for event in processor.process_batch_stream(
                document_ids=document_ids,
                force=force,
                concurrency=concurrency,
            ):
                yield {
                    "event": event.type,
                    "data": event.model_dump_json(exclude_none=True),
                }

        except Exception as e:
            logger.error(f"Error in batch processing stream: {e}")
            yield {
                "event": "error",
                "data": json.dumps({"error": str(e)}),
            }

    return EventSourceResponse(event_generator())


# ============================================================================
# Meeting Report Endpoints (P3-06)
# ============================================================================


@router.post("/{meeting_id}/report", response_model=MeetingReportResponse)
async def generate_meeting_report(
    meeting_id: str,
    request: MeetingReportRequest,
    current_user: CurrentUserDep,
    report_generator: MeetingReportGeneratorDep,
):
    """
    Generate a comprehensive meeting report (P3-06).

    This endpoint:
    1. Calls summarize_meeting() internally to get base summary
    2. Uses an agent with RAG search for detailed analysis
    3. Generates a Markdown report with:
       - Executive summary
       - Key topics and trends
       - Notable contributions
       - Detailed analysis with citations
    4. Saves to GCS and returns a signed download URL

    The custom_prompt parameter allows focusing the report on specific aspects.
    """
    try:
        report = await report_generator.generate(
            meeting_id=meeting_id,
            custom_prompt=request.custom_prompt,
            language=request.language,
            user_id=current_user.uid,
        )
        return MeetingReportResponse(
            report_id=report.id,
            meeting_id=report.meeting_id,
            download_url=report.download_url,
            summary_id=report.summary_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error generating report for {meeting_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate report")


@router.get("/{meeting_id}/report/{report_id}", response_model=MeetingReportResponse)
async def get_meeting_report(
    meeting_id: str,
    report_id: str,
    current_user: CurrentUserDep,
    report_generator: MeetingReportGeneratorDep,
):
    """Get a specific meeting report by ID with refreshed download URL."""
    report = await report_generator.get_report(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    if report.meeting_id != meeting_id:
        raise HTTPException(status_code=404, detail="Report not found for this meeting")
    return MeetingReportResponse(
        report_id=report.id,
        meeting_id=report.meeting_id,
        download_url=report.download_url,
        summary_id=report.summary_id,
    )


@router.get("/{meeting_id}/reports")
async def list_meeting_reports(
    meeting_id: str,
    current_user: CurrentUserDep,
    report_generator: MeetingReportGeneratorDep,
    limit: int = Query(10, ge=1, le=50),
):
    """List all reports for a specific meeting."""
    reports = await report_generator.list_reports(
        meeting_id=meeting_id,
        limit=limit,
    )
    return [
        {
            "report_id": r.id,
            "meeting_id": r.meeting_id,
            "download_url": r.download_url,
            "summary_id": r.summary_id,
            "created_at": r.created_at.isoformat(),
        }
        for r in reports
    ]
