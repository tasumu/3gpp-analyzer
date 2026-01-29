"""FTP browser and sync API endpoints."""

import asyncio
import uuid
from typing import AsyncIterator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from analyzer.dependencies import FTPSyncServiceDep
from analyzer.models.api import (
    FTPBrowseResponse,
    FTPDirectoryEntry,
    FTPSyncProgress,
    FTPSyncRequest,
)

router = APIRouter(prefix="/ftp")

# In-memory store for active sync operations
_active_syncs: dict[str, dict] = {}


@router.get("/browse", response_model=FTPBrowseResponse)
async def browse_directory(
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
    request: FTPSyncRequest,
    ftp_service: FTPSyncServiceDep,
):
    """
    Start FTP sync operation.

    Returns a sync_id that can be used to stream progress updates.
    """
    sync_id = str(uuid.uuid4())

    # Initialize sync state
    _active_syncs[sync_id] = {
        "status": "pending",
        "path": request.path,
        "path_pattern": request.path_pattern,
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
):
    """
    Stream sync progress via Server-Sent Events.

    Starts the actual sync operation and streams progress updates.
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

            result = await ftp_service.sync_meeting(
                meeting_path=sync_state["path"],
                path_pattern=sync_state["path_pattern"],
                progress_callback=progress_callback,
            )

            sync_state["status"] = "completed"
            sync_state["documents_found"] = result["documents_found"]
            sync_state["documents_new"] = result["documents_new"]
            sync_state["documents_updated"] = result["documents_updated"]
            sync_state["errors"] = result.get("errors", [])
            sync_state["result"] = result

        except Exception as e:
            sync_state["status"] = "error"
            sync_state["errors"].append(str(e))

    async def event_generator() -> AsyncIterator[str]:
        """Generate SSE events for sync progress."""
        try:
            sync_state["status"] = "running"

            # Send initial status
            yield _format_sse(
                FTPSyncProgress(
                    sync_id=sync_id,
                    status="running",
                    message="Starting sync...",
                )
            )

            # Start sync as background task
            sync_task = asyncio.create_task(run_sync())

            # Poll for progress updates
            last_current = -1
            while sync_state["status"] == "running":
                if sync_state["current"] != last_current:
                    yield _format_sse(
                        FTPSyncProgress(
                            sync_id=sync_id,
                            status="running",
                            message=sync_state["message"],
                            current=sync_state["current"],
                            total=sync_state["total"],
                        )
                    )
                    last_current = sync_state["current"]
                await asyncio.sleep(0.2)

            # Wait for task to complete
            await sync_task

            # Send final status
            if sync_state["status"] == "completed":
                yield _format_sse(
                    FTPSyncProgress(
                        sync_id=sync_id,
                        status="completed",
                        message="Sync completed",
                        current=sync_state["total"],
                        total=sync_state["total"],
                        documents_found=sync_state["documents_found"],
                        documents_new=sync_state["documents_new"],
                        documents_updated=sync_state["documents_updated"],
                        errors=sync_state["errors"],
                    )
                )
            else:
                yield _format_sse(
                    FTPSyncProgress(
                        sync_id=sync_id,
                        status="error",
                        message=sync_state["errors"][0]
                        if sync_state["errors"]
                        else "Unknown error",
                        errors=sync_state["errors"],
                    )
                )

        except Exception as e:
            sync_state["status"] = "error"
            sync_state["errors"].append(str(e))

            yield _format_sse(
                FTPSyncProgress(
                    sync_id=sync_id,
                    status="error",
                    message=str(e),
                    errors=[str(e)],
                )
            )

        finally:
            # Clean up after a delay
            await asyncio.sleep(60)
            _active_syncs.pop(sync_id, None)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _format_sse(data: FTPSyncProgress) -> str:
    """Format data as Server-Sent Event."""
    return f"data: {data.model_dump_json()}\n\n"
