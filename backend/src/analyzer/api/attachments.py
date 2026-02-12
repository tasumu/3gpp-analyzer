"""Attachment API endpoints for user-uploaded supplementary files."""

import logging

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from analyzer.dependencies import (
    AttachmentServiceDep,
    CurrentUserDep,
)

logger = logging.getLogger(__name__)

router = APIRouter()


class AttachmentResponse(BaseModel):
    """Response model for attachment metadata."""

    id: str
    filename: str
    content_type: str
    meeting_id: str
    file_size_bytes: int
    uploaded_by: str
    created_at: str


class AttachmentContentResponse(BaseModel):
    """Response model for attachment extracted text content."""

    attachment_id: str
    filename: str
    extracted_text: str


@router.post("/meetings/{meeting_id}/attachments", response_model=AttachmentResponse)
async def upload_attachment(
    meeting_id: str,
    current_user: CurrentUserDep,
    attachment_service: AttachmentServiceDep,
    file: UploadFile = File(...),
):
    """Upload a supplementary file for a meeting."""
    content = await file.read()

    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large (max 20MB)")

    try:
        attachment = await attachment_service.upload(
            meeting_id=meeting_id,
            filename=file.filename or "unnamed",
            content=content,
            content_type=file.content_type or "application/octet-stream",
            uploaded_by=current_user.uid,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return AttachmentResponse(
        id=attachment.id,
        filename=attachment.filename,
        content_type=attachment.content_type,
        meeting_id=attachment.meeting_id,
        file_size_bytes=attachment.file_size_bytes,
        uploaded_by=attachment.uploaded_by,
        created_at=attachment.created_at.isoformat(),
    )


@router.get("/meetings/{meeting_id}/attachments", response_model=list[AttachmentResponse])
async def list_attachments(
    meeting_id: str,
    current_user: CurrentUserDep,
    attachment_service: AttachmentServiceDep,
):
    """List all attachments for a meeting."""
    attachments = await attachment_service.list_by_meeting(meeting_id)
    return [
        AttachmentResponse(
            id=a.id,
            filename=a.filename,
            content_type=a.content_type,
            meeting_id=a.meeting_id,
            file_size_bytes=a.file_size_bytes,
            uploaded_by=a.uploaded_by,
            created_at=a.created_at.isoformat(),
        )
        for a in attachments
    ]


@router.get("/attachments/{attachment_id}/content", response_model=AttachmentContentResponse)
async def get_attachment_content(
    attachment_id: str,
    current_user: CurrentUserDep,
    attachment_service: AttachmentServiceDep,
):
    """Get extracted text content of an attachment."""
    attachment, text = await attachment_service.get_extracted_text_with_metadata(attachment_id)
    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")
    if text is None:
        raise HTTPException(status_code=404, detail="Extracted text not available")

    return AttachmentContentResponse(
        attachment_id=attachment_id,
        filename=attachment.filename,
        extracted_text=text,
    )


@router.delete("/attachments/{attachment_id}", status_code=204)
async def delete_attachment(
    attachment_id: str,
    current_user: CurrentUserDep,
    attachment_service: AttachmentServiceDep,
):
    """Delete an attachment (only by uploader)."""
    try:
        deleted = await attachment_service.delete(attachment_id, current_user.uid)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    if not deleted:
        raise HTTPException(status_code=404, detail="Attachment not found")
