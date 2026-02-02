"""Custom analysis API endpoints."""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from analyzer.dependencies import (
    AnalysisServiceDep,
    CurrentUserDep,
    CustomPromptServiceDep,
    DocumentServiceDep,
)
from analyzer.models.analysis import AnalysisLanguage

logger = logging.getLogger(__name__)

router = APIRouter()


# Request/Response models
class CustomAnalysisRequest(BaseModel):
    """Request body for custom analysis."""

    prompt_text: str = Field(
        ..., min_length=1, max_length=2000, description="Custom analysis prompt"
    )
    prompt_id: str | None = Field(None, description="ID of saved prompt if using one")
    language: AnalysisLanguage = Field(default="ja", description="Output language")


class CreatePromptRequest(BaseModel):
    """Request body for creating a custom prompt."""

    name: str = Field(..., min_length=1, max_length=100, description="Display name")
    prompt_text: str = Field(..., min_length=1, max_length=2000, description="Prompt text")


class UpdatePromptRequest(BaseModel):
    """Request body for updating a custom prompt."""

    name: str | None = Field(None, min_length=1, max_length=100, description="New name")
    prompt_text: str | None = Field(
        None, min_length=1, max_length=2000, description="New prompt text"
    )


# Custom Analysis endpoint
@router.post("/documents/{document_id}/analyze/custom")
async def run_custom_analysis(
    document_id: str,
    request: CustomAnalysisRequest,
    current_user: CurrentUserDep,
    analysis_service: AnalysisServiceDep,
    document_service: DocumentServiceDep,
):
    """
    Run custom analysis with user-provided prompt.

    Analyze a document based on a user's specific question or perspective.
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
        result = await analysis_service.analyze_custom(
            document_id=document_id,
            custom_prompt=request.prompt_text,
            prompt_id=request.prompt_id,
            language=request.language,
            user_id=current_user.uid,
        )

        return result.model_dump(mode="json")

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Custom analysis failed")
        raise HTTPException(status_code=500, detail=str(e))


# Custom Prompts CRUD endpoints
@router.get("/prompts")
async def list_prompts(
    current_user: CurrentUserDep,
    prompt_service: CustomPromptServiceDep,
):
    """List user's saved custom prompts."""
    prompts = await prompt_service.list_by_user(current_user.uid)

    return {"prompts": [p.model_dump(mode="json") for p in prompts]}


@router.post("/prompts")
async def create_prompt(
    request: CreatePromptRequest,
    current_user: CurrentUserDep,
    prompt_service: CustomPromptServiceDep,
):
    """Save a new custom prompt."""
    try:
        prompt = await prompt_service.create(
            user_id=current_user.uid,
            name=request.name,
            prompt_text=request.prompt_text,
        )

        return prompt.model_dump(mode="json")

    except Exception as e:
        logger.exception("Failed to create prompt")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/prompts/{prompt_id}")
async def get_prompt(
    prompt_id: str,
    current_user: CurrentUserDep,
    prompt_service: CustomPromptServiceDep,
):
    """Get a saved prompt by ID."""
    prompt = await prompt_service.get(prompt_id)

    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")

    if prompt.user_id != current_user.uid:
        raise HTTPException(status_code=403, detail="Permission denied")

    return prompt.model_dump(mode="json")


@router.put("/prompts/{prompt_id}")
async def update_prompt(
    prompt_id: str,
    request: UpdatePromptRequest,
    current_user: CurrentUserDep,
    prompt_service: CustomPromptServiceDep,
):
    """Update a saved prompt."""
    try:
        prompt = await prompt_service.update(
            prompt_id=prompt_id,
            user_id=current_user.uid,
            name=request.name,
            prompt_text=request.prompt_text,
        )

        if not prompt:
            raise HTTPException(status_code=404, detail="Prompt not found")

        return prompt.model_dump(mode="json")

    except PermissionError:
        raise HTTPException(status_code=403, detail="Permission denied")
    except Exception as e:
        logger.exception("Failed to update prompt")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/prompts/{prompt_id}")
async def delete_prompt(
    prompt_id: str,
    current_user: CurrentUserDep,
    prompt_service: CustomPromptServiceDep,
):
    """Delete a saved prompt."""
    try:
        deleted = await prompt_service.delete(prompt_id, current_user.uid)

        if not deleted:
            raise HTTPException(status_code=404, detail="Prompt not found")

        return {"status": "deleted"}

    except PermissionError:
        raise HTTPException(status_code=403, detail="Permission denied")
    except Exception as e:
        logger.exception("Failed to delete prompt")
        raise HTTPException(status_code=500, detail=str(e))
