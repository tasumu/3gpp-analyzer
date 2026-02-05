"""Q&A API endpoints for P3-05."""

import json
import logging

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from analyzer.dependencies import (
    CurrentUserDep,
    CurrentUserQueryDep,
    QAServiceDep,
)
from analyzer.models.qa import QARequest, QAResult, QAScope

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Q&A"])


class QAResponse(BaseModel):
    """Response model for Q&A API."""

    id: str
    question: str
    answer: str
    scope: str
    scope_id: str | None
    evidences: list[dict]
    created_at: str


def qa_result_to_response(result: QAResult) -> QAResponse:
    """Convert QAResult to API response."""
    return QAResponse(
        id=result.id,
        question=result.question,
        answer=result.answer,
        scope=result.scope.value,
        scope_id=result.scope_id,
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
    - meeting: Questions about all documents in a meeting (requires scope_id)
    - global: Questions across all indexed documents

    Returns the answer with supporting evidence citations.
    """
    try:
        result = await qa_service.answer(
            question=request.question,
            scope=QAScope(request.scope),
            scope_id=request.scope_id,
            filters=request.filters,
            language=request.language,
            user_id=current_user.uid,
            session_id=request.session_id,
        )
        return qa_result_to_response(result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error in Q&A: {e}")
        raise HTTPException(status_code=500, detail="Failed to process question")


@router.get("/qa/stream")
async def ask_question_stream(
    current_user: CurrentUserQueryDep,
    qa_service: QAServiceDep,
    question: str = Query(..., min_length=1, max_length=2000, description="The question to answer"),
    scope: str = Query("global", description="Search scope: document, meeting, or global"),
    scope_id: str | None = Query(None, description="Scope identifier"),
    language: str = Query("ja", pattern="^(ja|en)$", description="Response language"),
    session_id: str | None = Query(None, description="Session ID for conversation continuity"),
):
    """
    Answer a question with streaming response (SSE).

    Events:
    - chunk: Text chunk of the answer
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

    async def event_generator():
        try:
            async for event in qa_service.answer_stream(
                question=question,
                scope=qa_scope,
                scope_id=scope_id,
                language=language,
                user_id=current_user.uid,
                session_id=session_id,
            ):
                if event.type == "chunk":
                    yield {
                        "event": "chunk",
                        "data": json.dumps({"content": event.content}),
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
