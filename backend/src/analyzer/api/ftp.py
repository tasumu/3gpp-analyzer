"""FTP browser and sync API endpoints."""

import asyncio
import uuid

from fastapi import APIRouter, HTTPException, Query
from sse_starlette.sse import EventSourceResponse

from analyzer.dependencies import CurrentUserDep, FTPSyncServiceDep, UserServiceDep
from analyzer.models.api import (
    FTPBrowseResponse,
    FTPDirectoryEntry,
    FTPSyncProgress,
    FTPSyncRequest,
    SyncHistoryEntry,
    SyncHistoryResponse,
)
from analyzer.models.user import UserRole

router = APIRouter(prefix="/ftp")

# In-memory store for active sync operations
_active_syncs: dict[str, dict] = {}


@router.get("/browse", response_model=FTPBrowseResponse)
async def browse_directory(
    current_user: CurrentUserDep,
    ftp_service: FTPSyncServiceDep,
    path: str = "/",
):
    """
    Browse FTP directory contents.

    Returns list of subdirectories and files at the given path,
    with sync status for directories.
    """
    try:
        result = await ftp_service.list_directory(path)

        entries = [
            FTPDirectoryEntry(
                name=entry.name,
                type=entry.entry_type,
                size=entry.size,
                synced=entry.synced,
                synced_count=entry.synced_count,
            )
            for entry in result["entries"]
        ]

        return FTPBrowseResponse(
            path=result["path"],
            parent=result["parent"],
            entries=entries,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"FTP browse failed: {e}")


@router.post("/sync")
async def start_sync(
    current_user: CurrentUserDep,
    request: FTPSyncRequest,
    ftp_service: FTPSyncServiceDep,
    user_service: UserServiceDep,
):
    """
    Start FTP sync operation.

    Re-sync of previously synced directories is allowed for all approved users.
    Initial sync of new directories requires admin privileges.
    """
    # Check if this is a re-sync (directory was synced before)
    is_resync = await ftp_service.has_sync_history(request.path)

    if not is_resync:
        # New directory sync requires admin
        user = await user_service.get_user(current_user.uid)
        if not user or user.role != UserRole.ADMIN:
            raise HTTPException(
                status_code=403,
                detail="Admin privileges required for initial directory sync",
            )

    sync_id = str(uuid.uuid4())

    # Initialize sync state
    _active_syncs[sync_id] = {
        "status": "pending",
        "path": request.path,
        "path_pattern": request.path_pattern,
        "include_non_contributions": request.include_non_contributions,
        "ftp_service": ftp_service,
        "current": 0,
        "total": 0,
        "documents_found": 0,
        "documents_new": 0,
        "documents_updated": 0,
        "errors": [],
        "message": None,
    }

    return {"sync_id": sync_id}


@router.get("/sync/{sync_id}/stream")
async def stream_sync_progress(
    sync_id: str,
    ftp_service: FTPSyncServiceDep,
    current_user: CurrentUserDep,
):
    """
    Stream sync progress via Server-Sent Events.

    Starts the actual sync operation and streams progress updates.
    Authorization is enforced at the POST /sync endpoint.
    """

    if sync_id not in _active_syncs:
        raise HTTPException(status_code=404, detail="Sync operation not found")

    sync_state = _active_syncs[sync_id]

    async def run_sync():
        """Run the sync operation in a background task."""
        try:

            def progress_callback(message: str, current: int, total: int):
                sync_state["current"] = current
                sync_state["total"] = total
                sync_state["message"] = message

            result = await ftp_service.sync_directory(
                directory_path=sync_state["path"],
                path_pattern=sync_state["path_pattern"],
                include_non_contributions=sync_state.get("include_non_contributions", True),
                progress_callback=progress_callback,
            )

            sync_state["status"] = "completed"
            sync_state["documents_found"] = result["documents_found"]
            sync_state["documents_new"] = result["documents_new"]
            sync_state["documents_updated"] = result["documents_updated"]
            sync_state["errors"] = result.get("errors", [])
            sync_state["result"] = result

            # Record sync history
            await ftp_service.record_sync(
                directory_path=sync_state["path"],
                result=result,
            )

        except Exception as e:
            sync_state["status"] = "error"
            sync_state["errors"].append(str(e))

    async def event_generator():
        """Generate SSE events for sync progress."""
        try:
            sync_state["status"] = "running"

            # Send initial status
            yield {
                "event": "progress",
                "data": FTPSyncProgress(
                    sync_id=sync_id,
                    status="running",
                    message="Starting sync...",
                ).model_dump_json(),
            }

            # Start sync as background task
            sync_task = asyncio.create_task(run_sync())

            # Poll for progress updates
            last_current = -1
            while sync_state["status"] == "running":
                if sync_state["current"] != last_current:
                    yield {
                        "event": "progress",
                        "data": FTPSyncProgress(
                            sync_id=sync_id,
                            status="running",
                            message=sync_state["message"],
                            current=sync_state["current"],
                            total=sync_state["total"],
                        ).model_dump_json(),
                    }
                    last_current = sync_state["current"]
                await asyncio.sleep(0.2)

            # Wait for task to complete
            await sync_task

            # Send final status
            if sync_state["status"] == "completed":
                yield {
                    "event": "complete",
                    "data": FTPSyncProgress(
                        sync_id=sync_id,
                        status="completed",
                        message="Sync completed",
                        current=sync_state["total"],
                        total=sync_state["total"],
                        documents_found=sync_state["documents_found"],
                        documents_new=sync_state["documents_new"],
                        documents_updated=sync_state["documents_updated"],
                        errors=sync_state["errors"],
                    ).model_dump_json(),
                }
            else:
                yield {
                    "event": "error",
                    "data": FTPSyncProgress(
                        sync_id=sync_id,
                        status="error",
                        message=sync_state["errors"][0]
                        if sync_state["errors"]
                        else "Unknown error",
                        errors=sync_state["errors"],
                    ).model_dump_json(),
                }

        except Exception as e:
            sync_state["status"] = "error"
            sync_state["errors"].append(str(e))

            yield {
                "event": "error",
                "data": FTPSyncProgress(
                    sync_id=sync_id,
                    status="error",
                    message=str(e),
                    errors=[str(e)],
                ).model_dump_json(),
            }

        finally:
            # Clean up after a delay
            await asyncio.sleep(60)
            _active_syncs.pop(sync_id, None)

    return EventSourceResponse(event_generator())


@router.get("/sync-history", response_model=SyncHistoryResponse)
async def get_sync_history(
    current_user: CurrentUserDep,
    ftp_service: FTPSyncServiceDep,
    limit: int = Query(20, ge=1, le=100),
):
    """
    Get list of previously synced directories.

    Returns directories sorted by last_synced_at descending.
    """
    try:
        entries = await ftp_service.get_sync_history(limit=limit)
        return SyncHistoryResponse(
            entries=[
                SyncHistoryEntry(
                    id=e.id,
                    directory_path=e.directory_path,
                    last_synced_at=e.last_synced_at,
                    documents_found=e.documents_found,
                    documents_new=e.documents_new,
                    documents_updated=e.documents_updated,
                    synced_count=e.synced_count,
                )
                for e in entries
            ],
            total=len(entries),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get sync history: {e}")
