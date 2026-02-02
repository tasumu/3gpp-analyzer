"""Analysis API endpoints for P2-05."""

import json
import logging

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import RedirectResponse
from sse_starlette.sse import EventSourceResponse

from analyzer.dependencies import (
    AnalysisServiceDep,
    CurrentUserDep,
    CurrentUserQueryDep,
    DocumentServiceDep,
    ReviewSheetGeneratorDep,
)
from analyzer.models.analysis import (
    AnalysisOptions,
    AnalysisRequest,
    AnalysisResult,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# Response models
class AnalysisStartResponse:
    """Response for starting an analysis."""

    def __init__(
        self,
        analysis_id: str,
        status: str,
        document_id: str,
        contribution_number: str,
    ):
        self.analysis_id = analysis_id
        self.status = status
        self.document_id = document_id
        self.contribution_number = contribution_number


@router.post("/analysis")
async def start_analysis(
    request: AnalysisRequest,
    current_user: CurrentUserDep,
    analysis_service: AnalysisServiceDep,
    document_service: DocumentServiceDep,
):
    """
    Start an analysis.

    For single analysis, provide one contribution number.
    Returns analysis_id. Use SSE endpoint to monitor progress.
    """
    if request.type != "single":
        raise HTTPException(
            status_code=400,
            detail="Only single analysis is currently supported",
        )

    if len(request.contribution_numbers) != 1:
        raise HTTPException(
            status_code=400,
            detail="Single analysis requires exactly one contribution number",
        )

    contribution_number = request.contribution_numbers[0]

    # Find document by contribution number
    documents, _ = await document_service.list_documents(
        contribution_number=contribution_number,
        page=1,
        page_size=1,
    )

    if not documents:
        raise HTTPException(
            status_code=404,
            detail=f"Document not found: {contribution_number}",
        )

    document = documents[0]

    if document.status != "indexed":
        raise HTTPException(
            status_code=400,
            detail=f"Document is not indexed (status: {document.status}). "
            "Process the document first.",
        )

    try:
        # Start analysis (non-streaming for POST endpoint)
        result = await analysis_service.analyze_single(
            document_id=document.id,
            options=request.options,
            force=request.force,
            user_id=current_user.uid,
        )

        return {
            "analysis_id": result.id,
            "status": result.status,
            "document_id": result.document_id,
            "contribution_number": result.contribution_number,
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Analysis failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analysis/{analysis_id}")
async def get_analysis(
    analysis_id: str,
    current_user: CurrentUserDep,
    analysis_service: AnalysisServiceDep,
):
    """
    Get analysis result by ID.

    Returns the full analysis result including summary, changes, issues, and evidence.
    """
    result = await analysis_service.get_result(analysis_id)

    if not result:
        raise HTTPException(status_code=404, detail="Analysis not found")

    return result.model_dump(mode="json")


@router.get("/analysis/{analysis_id}/stream")
async def stream_analysis(
    analysis_id: str,
    current_user: CurrentUserQueryDep,
    analysis_service: AnalysisServiceDep,
):
    """
    Stream analysis progress via SSE.

    Use this endpoint after POST /analysis to monitor progress.
    Events: progress, partial, complete, error
    """

    async def event_generator():
        """Generate SSE events for analysis progress."""
        try:
            # Get current status
            result = await analysis_service.get_result(analysis_id)

            if not result:
                yield {
                    "event": "error",
                    "data": json.dumps({"error": "Analysis not found"}),
                }
                return

            if result.status == "completed":
                yield {
                    "event": "complete",
                    "data": json.dumps(
                        {
                            "analysis_id": analysis_id,
                            "status": "completed",
                        }
                    ),
                }
                return

            if result.status == "failed":
                yield {
                    "event": "error",
                    "data": json.dumps(
                        {
                            "error": result.error_message or "Analysis failed",
                        }
                    ),
                }
                return

            # If processing, poll until complete
            import asyncio

            max_attempts = 60  # 5 minutes max
            for attempt in range(max_attempts):
                await asyncio.sleep(5)  # Poll every 5 seconds

                result = await analysis_service.get_result(analysis_id)
                if not result:
                    yield {
                        "event": "error",
                        "data": json.dumps({"error": "Analysis not found"}),
                    }
                    return

                if result.status == "completed":
                    yield {
                        "event": "complete",
                        "data": json.dumps(
                            {
                                "analysis_id": analysis_id,
                                "status": "completed",
                            }
                        ),
                    }
                    return

                if result.status == "failed":
                    yield {
                        "event": "error",
                        "data": json.dumps(
                            {
                                "error": result.error_message or "Analysis failed",
                            }
                        ),
                    }
                    return

                # Progress update
                yield {
                    "event": "progress",
                    "data": json.dumps(
                        {
                            "status": result.status,
                            "progress": (attempt + 1) * (100 // max_attempts),
                        }
                    ),
                }

        except Exception as e:
            logger.exception("Error in analysis stream")
            yield {
                "event": "error",
                "data": json.dumps({"error": str(e)}),
            }

    return EventSourceResponse(event_generator())


@router.post("/documents/{document_id}/analyze")
async def analyze_document(
    document_id: str,
    current_user: CurrentUserDep,
    analysis_service: AnalysisServiceDep,
    document_service: DocumentServiceDep,
    options: AnalysisOptions | None = None,
    force: bool = Query(False, description="Force re-analysis"),
):
    """
    Analyze a specific document.

    Convenience endpoint that accepts document_id directly.
    """
    doc = await document_service.get(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if doc.status != "indexed":
        raise HTTPException(
            status_code=400,
            detail=f"Document is not indexed (status: {doc.status}). Process the document first.",
        )

    try:
        result = await analysis_service.analyze_single(
            document_id=document_id,
            options=options or AnalysisOptions(),
            force=force,
            user_id=current_user.uid,
        )

        return result.model_dump(mode="json")

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Analysis failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/documents/{document_id}/analysis")
async def get_document_analyses(
    document_id: str,
    current_user: CurrentUserDep,
    analysis_service: AnalysisServiceDep,
):
    """
    List all analyses for a document.

    Returns list of analyses ordered by creation date.
    """
    analyses = await analysis_service.list_by_document(document_id)

    return {
        "analyses": [a.model_dump(mode="json") for a in analyses],
        "total": len(analyses),
    }


@router.get("/downloads/{analysis_id}")
async def download_review_sheet(
    analysis_id: str,
    current_user: CurrentUserDep,
    analysis_service: AnalysisServiceDep,
    review_sheet_generator: ReviewSheetGeneratorDep,
    document_service: DocumentServiceDep,
):
    """
    Download review sheet for an analysis.

    Generates and returns a signed URL for the Markdown review sheet.
    """
    # Get analysis
    result = await analysis_service.get_result(analysis_id)
    if not result:
        raise HTTPException(status_code=404, detail="Analysis not found")

    if result.status != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Analysis is not completed (status: {result.status})",
        )

    # Get document data
    doc_data = await document_service.firestore.get_document(result.document_id)
    if not doc_data:
        raise HTTPException(status_code=404, detail="Document not found")

    try:
        # Generate review sheet
        content = review_sheet_generator.generate(result, doc_data)

        # Save and get URL
        url = await review_sheet_generator.save_and_get_url(analysis_id, content)

        return RedirectResponse(url, status_code=302)

    except Exception as e:
        logger.exception("Failed to generate review sheet")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analysis")
async def list_analyses(
    current_user: CurrentUserDep,
    analysis_service: AnalysisServiceDep,
    limit: int = Query(20, ge=1, le=100, description="Maximum results"),
):
    """
    List recent analyses.

    Returns list of recent analyses for the current user.
    """
    # For now, return a simple list from recent analyses
    # This could be enhanced with user filtering and pagination
    query = (
        analysis_service.firestore.client.collection(analysis_service.ANALYSIS_RESULTS_COLLECTION)
        .order_by("created_at", direction="DESCENDING")
        .limit(limit)
    )

    results = []
    for doc in query.stream():
        result = AnalysisResult.from_firestore(doc.id, doc.to_dict())
        results.append(result.model_dump(mode="json"))

    return {"analyses": results, "total": len(results)}
