"""Internal API endpoints (not exposed publicly)."""

from fastapi import APIRouter, HTTPException, status

from analyzer.dependencies import (
    CurrentUserDep,
    FirestoreClientDep,
    FTPSyncServiceDep,
    NormalizerServiceDep,
    UserServiceDep,
    VectorizerServiceDep,
)
from analyzer.models.api import (
    IndexRequest,
    IndexResponse,
    NormalizeRequest,
    NormalizeResponse,
    SyncRequest,
    SyncResponse,
)
from analyzer.models.user import User, UserRole

router = APIRouter()


async def _require_admin(current_user: CurrentUserDep, user_service: UserServiceDep) -> User:
    """
    Verify current user has admin privileges.

    Internal endpoints are restricted to administrators only.

    Args:
        current_user: Authenticated user
        user_service: User service instance

    Returns:
        User instance with admin role

    Raises:
        HTTPException: If user is not admin
    """
    user = await user_service.get_user(current_user.uid)
    if not user or user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required for internal endpoints",
        )
    return user


@router.post("/sync", response_model=SyncResponse)
async def sync_meeting(
    request: SyncRequest,
    ftp_service: FTPSyncServiceDep,
    current_user: CurrentUserDep,
    user_service: UserServiceDep,
):
    """
    Sync documents from FTP for a meeting.

    This is an internal endpoint for triggering FTP synchronization.
    Downloads metadata only; actual files are fetched on-demand.

    Requires admin privileges.
    """
    await _require_admin(current_user, user_service)

    try:
        result = await ftp_service.sync_meeting(
            meeting_path=f"/Meetings/{request.meeting_id}/Docs",
            path_pattern=request.path_pattern,
        )

        return SyncResponse(
            meeting_id=result["meeting_id"],
            documents_found=result["documents_found"],
            documents_new=result["documents_new"],
            documents_updated=result["documents_updated"],
            errors=result["errors"],
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sync/{meeting_id}/download/{document_id}")
async def download_document(
    meeting_id: str,
    document_id: str,
    ftp_service: FTPSyncServiceDep,
    current_user: CurrentUserDep,
    user_service: UserServiceDep,
):
    """
    Download a specific document from FTP.

    Downloads the file from FTP and stores it in GCS.

    Requires admin privileges.
    """
    await _require_admin(current_user, user_service)

    try:
        gcs_path = await ftp_service.download_document(document_id)
        return {"status": "downloaded", "gcs_path": gcs_path}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/normalize", response_model=NormalizeResponse)
async def normalize_document(
    request: NormalizeRequest,
    normalizer: NormalizerServiceDep,
    firestore: FirestoreClientDep,
    current_user: CurrentUserDep,
    user_service: UserServiceDep,
):
    """
    Normalize a document to docx format.

    Converts .doc files to .docx using LibreOffice.

    Requires admin privileges.
    """
    await _require_admin(current_user, user_service)

    try:
        normalized_path = await normalizer.normalize_document(
            request.document_id,
            firestore,
        )

        return NormalizeResponse(
            document_id=request.document_id,
            success=True,
            normalized_path=normalized_path,
        )

    except ValueError as e:
        return NormalizeResponse(
            document_id=request.document_id,
            success=False,
            error=str(e),
        )
    except Exception as e:
        return NormalizeResponse(
            document_id=request.document_id,
            success=False,
            error=str(e),
        )


@router.post("/index", response_model=IndexResponse)
async def index_document(
    request: IndexRequest,
    vectorizer: VectorizerServiceDep,
    firestore: FirestoreClientDep,
    current_user: CurrentUserDep,
    user_service: UserServiceDep,
):
    """
    Index a document (generate embeddings and store chunks).

    This requires the document to be normalized first.

    Requires admin privileges.
    """
    await _require_admin(current_user, user_service)

    try:
        # Get document to check status
        doc_data = await firestore.get_document(request.document_id)
        if not doc_data:
            return IndexResponse(
                document_id=request.document_id,
                success=False,
                error="Document not found",
            )

        # Get chunks from processing (would need chunking first)
        # This endpoint is mainly for re-indexing existing chunks
        chunks = await firestore.get_chunks_by_document(request.document_id)

        if not chunks:
            return IndexResponse(
                document_id=request.document_id,
                success=False,
                error="No chunks found. Process the document first.",
            )

        # Re-index with fresh embeddings
        from analyzer.models.chunk import Chunk

        chunk_objects = [Chunk.from_firestore(c["id"], c) for c in chunks]

        count = await vectorizer.reindex_document(
            request.document_id,
            chunk_objects,
        )

        return IndexResponse(
            document_id=request.document_id,
            success=True,
            chunks_created=count,
        )

    except Exception as e:
        return IndexResponse(
            document_id=request.document_id,
            success=False,
            error=str(e),
        )


@router.post("/batch/normalize")
async def batch_normalize(
    document_ids: list[str],
    normalizer: NormalizerServiceDep,
    firestore: FirestoreClientDep,
    current_user: CurrentUserDep,
    user_service: UserServiceDep,
):
    """
    Normalize multiple documents.

    Batch operation for converting multiple .doc files.

    Requires admin privileges.
    """
    await _require_admin(current_user, user_service)

    result = await normalizer.normalize_batch(document_ids, firestore)
    return result
