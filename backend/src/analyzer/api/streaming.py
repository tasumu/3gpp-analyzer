"""SSE streaming endpoints for real-time status updates."""

import asyncio
import json
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException, Query
from sse_starlette.sse import EventSourceResponse

from analyzer.auth import verify_firebase_token
from analyzer.dependencies import DocumentServiceDep, ProcessorServiceDep
from analyzer.models.document import DocumentStatus

router = APIRouter()


async def status_event_generator(
    document_id: str,
    processor: ProcessorServiceDep,
    force: bool = False,
) -> AsyncGenerator[dict, None]:
    """
    Generate SSE events for document processing status.

    Yields status updates as the document is processed.
    """
    try:
        async for update in processor.process_document_stream(document_id, force):
            yield {
                "event": "status",
                "data": json.dumps(update.model_dump(mode="json")),
            }

            # If done or error, stop
            if update.status in (DocumentStatus.INDEXED, DocumentStatus.ERROR):
                break

    except ValueError as e:
        yield {
            "event": "error",
            "data": json.dumps({"error": str(e)}),
        }
    except Exception as e:
        yield {
            "event": "error",
            "data": json.dumps({"error": str(e)}),
        }


@router.get("/documents/{document_id}/status/stream")
async def stream_document_status(
    document_id: str,
    processor: ProcessorServiceDep,
    document_service: DocumentServiceDep,
    token: str = Query(..., description="Firebase ID token for SSE authentication"),
    force: bool = False,
):
    """
    Stream document processing status via SSE.

    Starts processing the document and streams status updates
    as events. Use this for real-time progress monitoring.
    Requires token as query parameter since EventSource cannot set headers.

    Events:
    - status: StatusUpdate with progress info
    - error: Error occurred

    Example client code:
    ```javascript
    const token = await user.getIdToken();
    const evtSource = new EventSource(
        `/api/documents/S2-123/status/stream?token=${token}`
    );
    evtSource.addEventListener('status', (e) => {
        const status = JSON.parse(e.data);
        console.log(status.progress, status.message);
    });
    ```
    """
    # Verify authentication via query parameter (SSE cannot use headers)
    await verify_firebase_token(token)

    # Verify document exists
    doc = await document_service.get(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    return EventSourceResponse(status_event_generator(document_id, processor, force))


async def watch_status_generator(
    document_id: str,
    document_service: DocumentServiceDep,
    interval: float = 2.0,
) -> AsyncGenerator[dict, None]:
    """
    Watch document status changes via polling.

    Alternative to processing stream for monitoring status
    without triggering processing.
    """
    last_status = None
    last_updated = None

    while True:
        doc = await document_service.get(document_id)
        if not doc:
            yield {
                "event": "error",
                "data": json.dumps({"error": "Document not found"}),
            }
            break

        # Only emit if status or updated_at changed
        if doc.status != last_status or doc.updated_at != last_updated:
            last_status = doc.status
            last_updated = doc.updated_at

            yield {
                "event": "status",
                "data": json.dumps(
                    {
                        "document_id": doc.id,
                        "status": doc.status.value,
                        "chunk_count": doc.chunk_count,
                        "error_message": doc.error_message,
                        "updated_at": doc.updated_at.isoformat(),
                    }
                ),
            }

            # Stop watching if terminal state
            if doc.status in (DocumentStatus.INDEXED, DocumentStatus.ERROR):
                break

        await asyncio.sleep(interval)


@router.get("/documents/{document_id}/status/watch")
async def watch_document_status(
    document_id: str,
    document_service: DocumentServiceDep,
    token: str = Query(..., description="Firebase ID token for SSE authentication"),
):
    """
    Watch document status changes via SSE (polling).

    Unlike the /stream endpoint, this does NOT trigger processing.
    It simply watches for status changes via polling.
    Requires token as query parameter since EventSource cannot set headers.

    Use this to monitor a document being processed by another process.
    """
    # Verify authentication via query parameter (SSE cannot use headers)
    await verify_firebase_token(token)

    # Verify document exists
    doc = await document_service.get(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    return EventSourceResponse(watch_status_generator(document_id, document_service))
