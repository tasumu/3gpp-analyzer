"""Analysis API endpoints for document analysis and summarization."""

import logging

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from analyzer.dependencies import (
    AnalysisServiceDep,
    CurrentUserDep,
    DocumentServiceDep,
)
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
