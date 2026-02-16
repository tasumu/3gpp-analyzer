"""Document processing orchestration service."""

import asyncio
import logging
import tempfile
from pathlib import Path
from typing import AsyncGenerator, Callable, Literal

from pydantic import BaseModel

from analyzer.chunking.extractor import DocxExtractor
from analyzer.chunking.heading_based import HeadingBasedChunking
from analyzer.models.api import StatusUpdate
from analyzer.models.chunk import Chunk
from analyzer.models.document import Document, DocumentStatus
from analyzer.services.document_service import DocumentService
from analyzer.services.ftp_sync import FTPSyncService
from analyzer.services.normalizer import NormalizerService
from analyzer.services.vectorizer import VectorizerService

logger = logging.getLogger(__name__)


class BatchProcessEvent(BaseModel):
    """Event model for batch processing progress."""

    type: Literal[
        "batch_start",
        "document_start",
        "document_progress",
        "document_complete",
        "batch_complete",
        "error",
    ]
    document_id: str | None = None
    contribution_number: str | None = None
    index: int | None = None
    total: int | None = None
    status: str | None = None
    progress: float | None = None
    message: str | None = None
    success: bool | None = None
    error: str | None = None
    # For batch_complete
    success_count: int | None = None
    failed_count: int | None = None
    errors: dict[str, str] | None = None


class ProcessorService:
    """
    Orchestrates the full document processing pipeline.

    Pipeline: Download → Normalize → Chunk → Vectorize → Index

    Provides both synchronous processing and streaming status updates.
    """

    def __init__(
        self,
        document_service: DocumentService,
        ftp_sync: FTPSyncService,
        normalizer: NormalizerService,
        vectorizer: VectorizerService,
        chunk_max_tokens: int = 1000,
    ):
        """
        Initialize processor service.

        Args:
            document_service: Document CRUD service.
            ftp_sync: FTP synchronization service for downloading.
            normalizer: File normalization service.
            vectorizer: Vectorization service.
            chunk_max_tokens: Maximum tokens per chunk.
        """
        self.document_service = document_service
        self.ftp_sync = ftp_sync
        self.normalizer = normalizer
        self.vectorizer = vectorizer
        self.chunker = HeadingBasedChunking(max_tokens=chunk_max_tokens)
        self.extractor = DocxExtractor()

    async def process_document(
        self,
        document_id: str,
        force: bool = False,
        status_callback: Callable[[StatusUpdate], None] | None = None,
    ) -> Document:
        """
        Process a document through the full pipeline.

        Args:
            document_id: Document ID to process.
            force: Force reprocessing even if already indexed.
            status_callback: Optional callback for status updates.

        Returns:
            Processed document.

        Raises:
            ValueError: If document not found.
        """
        # Get document
        doc = await self.document_service.get(document_id)
        if not doc:
            raise ValueError(f"Document not found: {document_id}")

        def emit_status(status: DocumentStatus, progress: float, message: str | None = None):
            if status_callback:
                status_callback(
                    StatusUpdate(
                        document_id=document_id,
                        status=status,
                        progress=progress,
                        message=message,
                    )
                )

        # Non-analyzable documents: download only, skip processing pipeline
        if not doc.analyzable:
            if doc.status == DocumentStatus.DOWNLOADED and not force:
                return doc
            if not doc.source_file.gcs_original_path:
                emit_status(DocumentStatus.DOWNLOADING, 0.0, "Downloading from FTP")
                await self.ftp_sync.download_document(document_id)
            doc = await self.document_service.get(document_id)
            emit_status(DocumentStatus.DOWNLOADED, 1.0, "Download complete")
            return doc

        # Check if already processed
        if doc.status == DocumentStatus.INDEXED and not force:
            return doc

        try:
            # Step 1: Ensure file is downloaded
            if not doc.source_file.gcs_original_path:
                emit_status(DocumentStatus.DOWNLOADING, 0.0, "Downloading from FTP")
                await self.ftp_sync.download_document(document_id)
                # Refresh document to get updated gcs_original_path
                doc = await self.document_service.get(document_id)

            # Step 2: Normalize to docx
            emit_status(DocumentStatus.NORMALIZING, 0.1, "Converting to docx")
            try:
                normalized_path = await self.normalizer.normalize_document(
                    document_id,
                    self.document_service.firestore,
                )
            except ValueError as e:
                if "No document found in ZIP" in str(e):
                    # ZIP contains no analyzable content - downgrade to download-only
                    await self.document_service.update(
                        document_id,
                        {
                            "analyzable": False,
                            "status": DocumentStatus.DOWNLOADED.value,
                            "error_message": None,
                        },
                    )
                    emit_status(
                        DocumentStatus.DOWNLOADED,
                        1.0,
                        "ZIP contains no Word documents - marked as download-only",
                    )
                    return await self.document_service.get(document_id)
                raise

            # Step 3: Chunk the document(s)
            emit_status(DocumentStatus.CHUNKING, 0.3, "Extracting structure")

            # Refresh doc to get updated gcs_original_path after download
            doc = await self.document_service.get(document_id)

            if (
                doc.source_file.filename.lower().endswith(".zip")
                and doc.source_file.gcs_original_path
            ):
                # ZIP: extract and chunk ALL Word documents inside
                chunks = await self._chunk_zip_contents(doc, document_id, emit_status)
            else:
                # Non-ZIP: chunk the single normalized file
                with tempfile.TemporaryDirectory() as tmpdir:
                    local_path = Path(tmpdir) / "document.docx"
                    await self.document_service.storage.download_file(
                        normalized_path,
                        local_path,
                    )

                    # Extract title if not set
                    if not doc.title:
                        title = self.extractor.extract_title(local_path)
                        if title:
                            await self.document_service.update(document_id, {"title": title})

                    emit_status(DocumentStatus.CHUNKING, 0.4, "Creating chunks")
                    chunks = await self.chunker.chunk_document(
                        local_path,
                        document_id,
                        doc.contribution_number,
                        doc.meeting.id if doc.meeting else None,
                    )

            # Step 5: Vectorize and index
            emit_status(DocumentStatus.INDEXING, 0.5, "Generating embeddings")

            def index_progress(message: str, progress: float):
                # Scale progress from 0.5 to 0.95
                scaled = 0.5 + progress * 0.45
                emit_status(DocumentStatus.INDEXING, scaled, message)

            chunk_count = await self.vectorizer.index_document(
                document_id,
                chunks,
                progress_callback=index_progress,
            )

            # Done
            emit_status(DocumentStatus.INDEXED, 1.0, f"Indexed {chunk_count} chunks")

            return await self.document_service.get(document_id)

        except Exception as e:
            # Update status to error
            await self.document_service.update_status(
                document_id,
                DocumentStatus.ERROR,
                error_message=str(e),
            )
            if status_callback:
                status_callback(
                    StatusUpdate(
                        document_id=document_id,
                        status=DocumentStatus.ERROR,
                        progress=0.0,
                        error=str(e),
                    )
                )
            raise

    async def _chunk_zip_contents(
        self,
        doc: Document,
        document_id: str,
        emit_status: Callable,
    ) -> list[Chunk]:
        """
        Extract and chunk all Word documents inside a ZIP archive.

        Downloads the original ZIP from GCS, extracts all .doc/.docx files,
        converts each to .docx, and chunks them all. All chunks are tagged
        with the source filename for traceability.

        Args:
            doc: Document model with source_file info.
            document_id: Document ID for chunk metadata.
            emit_status: Callback for status updates.

        Returns:
            List of chunks from all Word documents in the ZIP.
        """
        all_chunks: list[Chunk] = []

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Download original ZIP from GCS
            local_zip = tmpdir_path / doc.source_file.filename
            await self.document_service.storage.download_file(
                doc.source_file.gcs_original_path,
                local_zip,
            )

            # Extract and normalize all Word documents
            normalized_files = self.normalizer.extract_and_normalize_all(local_zip, tmpdir_path)

            if not normalized_files:
                logger.warning(f"No Word documents found in ZIP: {doc.source_file.filename}")
                return []

            total_files = len(normalized_files)
            logger.info(f"ZIP {doc.source_file.filename} contains {total_files} Word document(s)")

            for i, (source_filename, local_docx_path) in enumerate(normalized_files):
                # Extract title from the first file if not set
                if i == 0 and not doc.title:
                    title = self.extractor.extract_title(local_docx_path)
                    if title:
                        await self.document_service.update(document_id, {"title": title})

                emit_status(
                    DocumentStatus.CHUNKING,
                    0.3 + (i / total_files) * 0.2,
                    f"Chunking {source_filename} ({i + 1}/{total_files})",
                )

                file_chunks = await self.chunker.chunk_document(
                    local_docx_path,
                    document_id,
                    doc.contribution_number,
                    doc.meeting.id if doc.meeting else None,
                )

                # Tag each chunk with the source filename
                for chunk in file_chunks:
                    chunk.metadata.source_filename = source_filename

                all_chunks.extend(file_chunks)
                logger.info(f"  {source_filename}: {len(file_chunks)} chunks")

        return all_chunks

    async def process_document_stream(
        self,
        document_id: str,
        force: bool = False,
    ) -> AsyncGenerator[StatusUpdate, None]:
        """
        Process a document and yield status updates.

        Args:
            document_id: Document ID to process.
            force: Force reprocessing.

        Yields:
            StatusUpdate objects as processing progresses.
        """
        from analyzer.models.api import StatusUpdate

        updates: list[StatusUpdate] = []
        update_event = asyncio.Event()

        def callback(update: StatusUpdate):
            updates.append(update)
            update_event.set()

        # Yield initial status to confirm connection
        doc = await self.document_service.get(document_id)
        if doc:
            yield StatusUpdate(
                document_id=document_id,
                status=doc.status,
                progress=0.0,
                message="Starting processing...",
            )

        # Start processing in background
        task = asyncio.create_task(self.process_document(document_id, force, callback))

        # Yield updates as they come
        while not task.done():
            try:
                await asyncio.wait_for(update_event.wait(), timeout=1.0)
                update_event.clear()

                while updates:
                    yield updates.pop(0)
            except asyncio.TimeoutError:
                # Continue waiting, don't break the loop
                pass

        # Get any final updates after task completes
        while updates:
            yield updates.pop(0)

        # Check for exceptions
        if task.exception():
            raise task.exception()

    async def process_batch(
        self,
        document_ids: list[str],
        force: bool = False,
        concurrency: int = 5,
    ) -> dict:
        """
        Process multiple documents concurrently.

        Args:
            document_ids: List of document IDs.
            force: Force reprocessing.
            concurrency: Maximum concurrent processing tasks.

        Returns:
            Result dict with success/failure counts.
        """
        semaphore = asyncio.Semaphore(concurrency)

        async def process_one(doc_id: str) -> tuple[str, bool, str | None]:
            async with semaphore:
                try:
                    await self.process_document(doc_id, force)
                    return (doc_id, True, None)
                except Exception as e:
                    return (doc_id, False, str(e))

        # Process all documents
        tasks = [process_one(doc_id) for doc_id in document_ids]
        results = await asyncio.gather(*tasks)

        # Aggregate results
        success = sum(1 for _, ok, _ in results if ok)
        failed = sum(1 for _, ok, _ in results if not ok)
        errors = {doc_id: err for doc_id, ok, err in results if not ok and err}

        return {
            "total": len(document_ids),
            "success": success,
            "failed": failed,
            "errors": errors,
        }

    async def process_batch_stream(
        self,
        document_ids: list[str],
        force: bool = False,
        concurrency: int = 3,
    ) -> AsyncGenerator[BatchProcessEvent, None]:
        """
        Process multiple documents with streaming progress updates.

        Args:
            document_ids: List of document IDs to process.
            force: Force reprocessing.
            concurrency: Maximum concurrent processing tasks.

        Yields:
            BatchProcessEvent objects as processing progresses.
        """
        total = len(document_ids)
        if total == 0:
            yield BatchProcessEvent(
                type="batch_complete",
                total=0,
                success_count=0,
                failed_count=0,
                errors={},
            )
            return

        # Emit batch start
        yield BatchProcessEvent(
            type="batch_start",
            total=total,
        )

        # Track results
        success_count = 0
        failed_count = 0
        errors: dict[str, str] = {}

        # Process documents with limited concurrency
        semaphore = asyncio.Semaphore(concurrency)
        pending_docs = list(enumerate(document_ids))
        completed = 0

        # Queue for events from concurrent tasks
        event_queue: asyncio.Queue[BatchProcessEvent] = asyncio.Queue()

        async def process_one(idx: int, doc_id: str):
            """Process a single document and put events in queue."""
            async with semaphore:
                # Get document info for contribution_number
                doc = await self.document_service.get(doc_id)
                contrib_num = doc.contribution_number if doc else doc_id

                await event_queue.put(
                    BatchProcessEvent(
                        type="document_start",
                        document_id=doc_id,
                        contribution_number=contrib_num,
                        index=idx + 1,
                        total=total,
                    )
                )

                try:
                    # Process with progress callback
                    def progress_callback(update: StatusUpdate):
                        # Put progress event in queue (non-blocking)
                        try:
                            event_queue.put_nowait(
                                BatchProcessEvent(
                                    type="document_progress",
                                    document_id=doc_id,
                                    contribution_number=contrib_num,
                                    status=update.status.value,
                                    progress=update.progress,
                                    message=update.message,
                                )
                            )
                        except asyncio.QueueFull:
                            pass  # Skip if queue is full

                    await self.process_document(doc_id, force, progress_callback)

                    await event_queue.put(
                        BatchProcessEvent(
                            type="document_complete",
                            document_id=doc_id,
                            contribution_number=contrib_num,
                            success=True,
                        )
                    )
                    return (doc_id, True, None)

                except Exception as e:
                    error_msg = str(e)
                    await event_queue.put(
                        BatchProcessEvent(
                            type="document_complete",
                            document_id=doc_id,
                            contribution_number=contrib_num,
                            success=False,
                            error=error_msg,
                        )
                    )
                    return (doc_id, False, error_msg)

        # Start all tasks
        tasks = [asyncio.create_task(process_one(idx, doc_id)) for idx, doc_id in pending_docs]

        # Process events as they come
        while completed < total:
            try:
                # Wait for next event with timeout
                event = await asyncio.wait_for(event_queue.get(), timeout=1.0)
                yield event

                if event.type == "document_complete":
                    completed += 1
                    if event.success:
                        success_count += 1
                    else:
                        failed_count += 1
                        if event.document_id and event.error:
                            errors[event.document_id] = event.error

            except asyncio.TimeoutError:
                # Check if all tasks are done
                if all(t.done() for t in tasks):
                    # Drain remaining events
                    while not event_queue.empty():
                        event = event_queue.get_nowait()
                        yield event
                        if event.type == "document_complete":
                            completed += 1
                            if event.success:
                                success_count += 1
                            else:
                                failed_count += 1
                                if event.document_id and event.error:
                                    errors[event.document_id] = event.error
                    break

        # Emit batch complete
        yield BatchProcessEvent(
            type="batch_complete",
            total=total,
            success_count=success_count,
            failed_count=failed_count,
            errors=errors if errors else None,
        )
