"""Q&A API endpoints for P3-05."""

import json
import logging

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from analyzer.dependencies import (
    CurrentUserDep,
    QAServiceDep,
)
from analyzer.models.qa import QAMode, QARequest, QAResult, QAScope

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Q&A"])


class QAResponse(BaseModel):
    """Response model for Q&A API."""

    id: str
    question: str
    answer: str
    scope: str
    scope_id: str | None
    mode: str = "rag"
    evidences: list[dict]
    created_at: str


class QAReportResponse(BaseModel):
    """Response model for QA report."""

    report_id: str
    qa_result_id: str
    download_url: str
    question: str = ""
    is_public: bool = False
    created_at: str = ""


class PublishRequest(BaseModel):
    """Request model for publishing/unpublishing a report."""

    is_public: bool


def qa_result_to_response(result: QAResult) -> QAResponse:
    """Convert QAResult to API response."""
    return QAResponse(
        id=result.id,
        question=result.question,
        answer=result.answer,
        scope=result.scope.value,
        scope_id=result.scope_id,
        mode=result.mode.value,
        evidences=[
            {
                "chunk_id": ev.chunk_id,
                "contribution_number": ev.contribution_number,
                "content": ev.content[:300] + "..." if len(ev.content) > 300 else ev.content,
                "clause_number": ev.clause_number,
                "clause_title": ev.clause_title,
                "page_number": ev.page_number,
                "relevance_score": ev.relevance_score,
            }
            for ev in result.evidences
        ],
        created_at=result.created_at.isoformat(),
    )


@router.post("/qa", response_model=QAResponse)
async def ask_question(
    request: QARequest,
    current_user: CurrentUserDep,
    qa_service: QAServiceDep,
):
    """
    Answer a question using RAG-based search.

    Supports three scopes:
    - document: Questions about a specific document (requires scope_id)
    - meeting: Questions about all documents in a meeting (requires scope_id or scope_ids)
    - global: Questions across all indexed documents

    Returns the answer with supporting evidence citations.
    """
    try:
        result = await qa_service.answer(
            question=request.question,
            scope=QAScope(request.scope),
            scope_id=request.scope_id,
            scope_ids=request.scope_ids,
            filters=request.filters,
            language=request.language,
            user_id=current_user.uid,
            session_id=request.session_id,
            mode=QAMode(request.mode),
        )
        return qa_result_to_response(result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error in Q&A: {e}")
        raise HTTPException(status_code=500, detail="Failed to process question")


@router.get("/qa/stream")
async def ask_question_stream(
    current_user: CurrentUserDep,
    qa_service: QAServiceDep,
    question: str = Query(..., min_length=1, max_length=2000, description="The question to answer"),
    scope: str = Query("global", description="Search scope: document, meeting, or global"),
    scope_id: str | None = Query(None, description="Scope identifier"),
    scope_ids: str | None = Query(None, description="Multiple scope identifiers (comma-separated)"),
    language: str = Query("ja", pattern="^(ja|en)$", description="Response language"),
    session_id: str | None = Query(None, description="Session ID for conversation continuity"),
    mode: str = Query("rag", pattern="^(rag|agentic)$", description="Q&A mode"),
):
    """
    Answer a question with streaming response (SSE).

    Requires Authorization header with Bearer token.

    Events:
    - chunk: Text chunk of the answer
    - tool_call: Tool invocation info (agentic mode)
    - tool_result: Tool result summary (agentic mode)
    - evidence: Supporting evidence
    - done: Final result with complete answer
    - error: Error message if something went wrong
    """
    try:
        qa_scope = QAScope(scope)
    except ValueError:

        async def error_generator():
            yield {
                "event": "error",
                "data": json.dumps({"error": f"Invalid scope: {scope}"}),
            }

        return EventSourceResponse(error_generator())

    try:
        qa_mode = QAMode(mode)
    except ValueError:
        qa_mode = QAMode.RAG

    async def event_generator():
        try:
            # Parse scope_ids from comma-separated string
            parsed_scope_ids = None
            if scope_ids:
                parsed_scope_ids = [id.strip() for id in scope_ids.split(",") if id.strip()]

            async for event in qa_service.answer_stream(
                question=question,
                scope=qa_scope,
                scope_id=scope_id,
                scope_ids=parsed_scope_ids,
                language=language,
                user_id=current_user.uid,
                session_id=session_id,
                mode=qa_mode,
            ):
                if event.type == "chunk":
                    yield {
                        "event": "chunk",
                        "data": json.dumps({"content": event.content}),
                    }
                elif event.type == "tool_call":
                    yield {
                        "event": "tool_call",
                        "data": event.content or "{}",
                    }
                elif event.type == "tool_result":
                    yield {
                        "event": "tool_result",
                        "data": event.content or "{}",
                    }
                elif event.type == "evidence":
                    yield {
                        "event": "evidence",
                        "data": json.dumps(
                            {
                                "evidence": {
                                    "chunk_id": event.evidence.chunk_id,
                                    "contribution_number": event.evidence.contribution_number,
                                    "content": event.evidence.content[:300],
                                    "clause_number": event.evidence.clause_number,
                                    "relevance_score": event.evidence.relevance_score,
                                }
                            }
                        ),
                    }
                elif event.type == "done":
                    yield {
                        "event": "done",
                        "data": json.dumps(
                            {
                                "result_id": event.result.id,
                                "answer": event.result.answer,
                                "evidence_count": len(event.result.evidences),
                            }
                        ),
                    }
                elif event.type == "error":
                    yield {
                        "event": "error",
                        "data": json.dumps({"error": event.error}),
                    }
        except Exception as e:
            logger.error(f"Error in Q&A stream: {e}")
            yield {
                "event": "error",
                "data": json.dumps({"error": str(e)}),
            }

    return EventSourceResponse(event_generator())


@router.get("/qa/reports", response_model=list[QAReportResponse])
async def list_qa_reports(
    current_user: CurrentUserDep,
    qa_service: QAServiceDep,
    limit: int = Query(20, ge=1, le=100, description="Maximum reports to return"),
):
    """List QA reports visible to the current user (own + public)."""
    reports = await qa_service.list_reports(
        user_id=current_user.uid,
        limit=limit,
    )
    return [
        QAReportResponse(
            report_id=r.id,
            qa_result_id=r.qa_result_id,
            download_url=r.download_url,
            question=r.question,
            is_public=r.is_public,
            created_at=r.created_at.isoformat(),
        )
        for r in reports
    ]


@router.patch("/qa/reports/{report_id}/publish", response_model=QAReportResponse)
async def publish_qa_report(
    report_id: str,
    request: PublishRequest,
    current_user: CurrentUserDep,
    qa_service: QAServiceDep,
):
    """Toggle the public visibility of a QA report. Only the owner can publish."""
    try:
        report = await qa_service.publish_report(
            report_id=report_id,
            user_id=current_user.uid,
            is_public=request.is_public,
        )
        return QAReportResponse(
            report_id=report.id,
            qa_result_id=report.qa_result_id,
            download_url=report.download_url,
            question=report.question,
            is_public=report.is_public,
            created_at=report.created_at.isoformat(),
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Error publishing QA report {report_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update report")


@router.delete("/qa/reports/{report_id}", status_code=204)
async def delete_qa_report(
    report_id: str,
    current_user: CurrentUserDep,
    qa_service: QAServiceDep,
):
    """Delete a QA report. Only the owner can delete."""
    try:
        await qa_service.delete_report(
            report_id=report_id,
            user_id=current_user.uid,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Error deleting QA report {report_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete report")


@router.post("/qa/{result_id}/report", response_model=QAReportResponse)
async def generate_qa_report(
    result_id: str,
    current_user: CurrentUserDep,
    qa_service: QAServiceDep,
):
    """
    Generate a downloadable Markdown report from an existing QA result.

    Takes the saved QA answer, formats it with question, answer, and evidence
    citations as Markdown, uploads to GCS, and returns a signed download URL.
    No LLM re-execution is performed.
    """
    try:
        report = await qa_service.generate_report(
            result_id=result_id,
            user_id=current_user.uid,
        )
        return QAReportResponse(
            report_id=report.id,
            qa_result_id=report.qa_result_id,
            download_url=report.download_url,
            question=report.question,
            is_public=report.is_public,
            created_at=report.created_at.isoformat(),
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Error generating QA report for {result_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate report")


@router.get("/qa/{result_id}", response_model=QAResponse)
async def get_qa_result(
    result_id: str,
    current_user: CurrentUserDep,
    qa_service: QAServiceDep,
):
    """Get a previously saved Q&A result by ID."""
    result = await qa_service.get_result(result_id)
    if not result:
        raise HTTPException(status_code=404, detail="Q&A result not found")
    return qa_result_to_response(result)


@router.get("/qa", response_model=list[QAResponse])
async def list_qa_results(
    current_user: CurrentUserDep,
    qa_service: QAServiceDep,
    scope: str | None = Query(None, description="Filter by scope"),
    limit: int = Query(50, ge=1, le=100, description="Maximum results to return"),
):
    """List Q&A results for the current user."""
    qa_scope = QAScope(scope) if scope else None
    results = await qa_service.list_results(
        user_id=current_user.uid,
        scope=qa_scope,
        limit=limit,
    )
    return [qa_result_to_response(r) for r in results]
