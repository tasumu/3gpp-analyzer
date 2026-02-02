"""Report prompts API endpoints."""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from analyzer.dependencies import (
    CurrentUserDep,
    ReportPromptServiceDep,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# Request/Response models
class CreateReportPromptRequest(BaseModel):
    """Request body for creating a report prompt."""

    name: str = Field(..., min_length=1, max_length=100, description="Display name")
    prompt_text: str = Field(..., min_length=1, max_length=2000, description="Prompt text")


class UpdateReportPromptRequest(BaseModel):
    """Request body for updating a report prompt."""

    name: str | None = Field(None, min_length=1, max_length=100, description="New name")
    prompt_text: str | None = Field(
        None, min_length=1, max_length=2000, description="New prompt text"
    )


# Report Prompts CRUD endpoints
@router.get("/report-prompts")
async def list_report_prompts(
    current_user: CurrentUserDep,
    prompt_service: ReportPromptServiceDep,
):
    """List user's saved report prompts."""
    prompts = await prompt_service.list_by_user(current_user.uid)

    return {"prompts": [p.model_dump(mode="json") for p in prompts]}


@router.post("/report-prompts")
async def create_report_prompt(
    request: CreateReportPromptRequest,
    current_user: CurrentUserDep,
    prompt_service: ReportPromptServiceDep,
):
    """Save a new report prompt."""
    try:
        prompt = await prompt_service.create(
            user_id=current_user.uid,
            name=request.name,
            prompt_text=request.prompt_text,
        )

        return prompt.model_dump(mode="json")

    except Exception as e:
        logger.exception("Failed to create report prompt")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/report-prompts/{prompt_id}")
async def get_report_prompt(
    prompt_id: str,
    current_user: CurrentUserDep,
    prompt_service: ReportPromptServiceDep,
):
    """Get a saved report prompt by ID."""
    prompt = await prompt_service.get(prompt_id)

    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")

    if prompt.user_id != current_user.uid:
        raise HTTPException(status_code=403, detail="Permission denied")

    return prompt.model_dump(mode="json")


@router.put("/report-prompts/{prompt_id}")
async def update_report_prompt(
    prompt_id: str,
    request: UpdateReportPromptRequest,
    current_user: CurrentUserDep,
    prompt_service: ReportPromptServiceDep,
):
    """Update a saved report prompt."""
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
        logger.exception("Failed to update report prompt")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/report-prompts/{prompt_id}")
async def delete_report_prompt(
    prompt_id: str,
    current_user: CurrentUserDep,
    prompt_service: ReportPromptServiceDep,
):
    """Delete a saved report prompt."""
    try:
        deleted = await prompt_service.delete(prompt_id, current_user.uid)

        if not deleted:
            raise HTTPException(status_code=404, detail="Prompt not found")

        return {"status": "deleted"}

    except PermissionError:
        raise HTTPException(status_code=403, detail="Permission denied")
    except Exception as e:
        logger.exception("Failed to delete report prompt")
        raise HTTPException(status_code=500, detail=str(e))
