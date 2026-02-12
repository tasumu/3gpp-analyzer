"""Analysis API endpoints for document analysis and summarization."""

import logging

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from analyzer.dependencies import (
    AnalysisServiceDep,
    CurrentUserDep,
    DocumentServiceDep,
    ReviewSheetGeneratorDep,
)
from analyzer.models.analysis import AnalysisResult
from analyzer.models.meeting_analysis import DocumentSummary

logger = logging.getLogger(__name__)

router = APIRouter()


class AnalyzeDocumentRequest(BaseModel):
    """Request body for analyze document endpoint."""

    language: str = Field(default="ja", pattern="^(ja|en)$", description="Output language")
    custom_prompt: str | None = Field(default=None, max_length=2000, description="Custom focus")
    force: bool = Field(default=False, description="Force re-generation even if cached")


@router.post("/documents/{document_id}/analyze", response_model=DocumentSummary)
async def analyze_document(
    document_id: str,
    current_user: CurrentUserDep,
    analysis_service: AnalysisServiceDep,
    document_service: DocumentServiceDep,
    request: AnalyzeDocumentRequest | None = None,
) -> DocumentSummary:
    """
    Analyze a specific document and return a summary.

    Returns a DocumentSummary with summary text and key points.
    Results are cached and shared with meeting summarization.
    """
    doc = await document_service.get(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if doc.status != "indexed":
        raise HTTPException(
            status_code=400,
            detail=f"Document is not indexed (status: {doc.status}). Process the document first.",
        )

    # Extract options from request body
    req = request or AnalyzeDocumentRequest()

    try:
        summary = await analysis_service.generate_summary(
            document_id=document_id,
            language=req.language,
            custom_prompt=req.custom_prompt,
            force=req.force,
            user_id=current_user.uid,
        )

        return summary

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Analysis failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/documents/{document_id}/summary", response_model=DocumentSummary | None)
async def get_document_summary(
    document_id: str,
    current_user: CurrentUserDep,
    analysis_service: AnalysisServiceDep,
    document_service: DocumentServiceDep,
    language: str = Query("ja", pattern="^(ja|en)$", description="Output language"),
    custom_prompt: str | None = Query(None, max_length=2000, description="Custom focus"),
) -> DocumentSummary | None:
    """
    Get cached document summary.

    Returns the cached summary if available, or null if not cached.
    Use POST /documents/{document_id}/analyze to generate a new summary.
    """
    doc = await document_service.get(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    summary = await analysis_service.get_cached_summary(
        document_id=document_id,
        language=language,
        custom_prompt=custom_prompt,
    )

    return summary


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
