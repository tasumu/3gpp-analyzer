"""Document processing orchestration service."""

import asyncio
import tempfile
from pathlib import Path
from typing import AsyncGenerator, Callable

from analyzer.chunking.extractor import DocxExtractor
from analyzer.chunking.heading_based import HeadingBasedChunking
from analyzer.models.api import StatusUpdate
from analyzer.models.document import Document, DocumentStatus
from analyzer.services.document_service import DocumentService
from analyzer.services.ftp_sync import FTPSyncService
from analyzer.services.normalizer import NormalizerService
from analyzer.services.vectorizer import VectorizerService


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

        # Check if already processed
        if doc.status == DocumentStatus.INDEXED and not force:
            return doc

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

        try:
            # Step 1: Ensure file is downloaded
            if not doc.source_file.gcs_original_path:
                emit_status(DocumentStatus.DOWNLOADING, 0.0, "Downloading from FTP")
                await self.ftp_sync.download_document(document_id)
                # Refresh document to get updated gcs_original_path
                doc = await self.document_service.get(document_id)

            # Step 2: Normalize to docx
            emit_status(DocumentStatus.NORMALIZING, 0.1, "Converting to docx")
            normalized_path = await self.normalizer.normalize_document(
                document_id,
                self.document_service.firestore,
            )

            # Step 3: Download normalized file for chunking
            emit_status(DocumentStatus.CHUNKING, 0.3, "Extracting structure")

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

                # Step 4: Chunk the document
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
        updates: list[StatusUpdate] = []
        update_event = asyncio.Event()

        def callback(update: StatusUpdate):
            updates.append(update)
            update_event.set()

        # Start processing in background
        task = asyncio.create_task(self.process_document(document_id, force, callback))

        # Yield updates as they come
        try:
            while not task.done():
                await asyncio.wait_for(update_event.wait(), timeout=1.0)
                update_event.clear()

                while updates:
                    yield updates.pop(0)

        except asyncio.TimeoutError:
            pass  # Continue waiting

        # Get any final updates
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
