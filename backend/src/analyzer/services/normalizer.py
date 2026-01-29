"""File normalization service for doc to docx conversion (P1-02)."""

import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

from analyzer.models.document import DocumentStatus
from analyzer.providers.firestore_client import FirestoreClient
from analyzer.providers.storage_client import StorageClient


class NormalizerService:
    """
    Service for normalizing document formats.

    Converts .doc files to .docx using LibreOffice headless mode.
    The canonical format for processing is .docx.
    """

    def __init__(
        self,
        storage: StorageClient,
        timeout: int = 60,
    ):
        """
        Initialize normalizer service.

        Args:
            storage: GCS client for file storage.
            timeout: Timeout in seconds for LibreOffice conversion.
        """
        self.storage = storage
        self.timeout = timeout

    def _needs_conversion(self, filename: str) -> bool:
        """Check if file needs conversion to docx."""
        lower = filename.lower()
        return lower.endswith(".doc") and not lower.endswith(".docx")

    async def normalize_document(
        self,
        document_id: str,
        firestore: FirestoreClient,
    ) -> str:
        """
        Normalize a document to docx format.

        Args:
            document_id: Document ID to normalize.
            firestore: Firestore client for document updates.

        Returns:
            GCS path of normalized file.

        Raises:
            ValueError: If document not found or not downloaded.
            RuntimeError: If conversion fails.
        """
        # Get document from Firestore
        doc_data = await firestore.get_document(document_id)
        if not doc_data:
            raise ValueError(f"Document not found: {document_id}")

        source_file = doc_data.get("source_file", {})
        gcs_original = source_file.get("gcs_original_path")
        if not gcs_original:
            raise ValueError(f"Document not downloaded: {document_id}")

        filename = source_file.get("filename", "")
        meeting_id = doc_data.get("meeting", {}).get("id", "unknown")

        # Check if already normalized
        gcs_normalized = source_file.get("gcs_normalized_path")
        if gcs_normalized and await self.storage.exists(gcs_normalized):
            return gcs_normalized

        # Update status
        await firestore.update_document(
            document_id,
            {
                "status": DocumentStatus.NORMALIZING.value,
                "updated_at": datetime.utcnow().isoformat(),
            },
        )

        try:
            # If already docx, just copy to normalized location
            if filename.lower().endswith(".docx"):
                gcs_normalized = self.storage.get_normalized_path(meeting_id, filename)
                content = await self.storage.download_bytes(gcs_original)
                await self.storage.upload_bytes(content, gcs_normalized)

            elif self._needs_conversion(filename):
                gcs_normalized = await self._convert_doc_to_docx(gcs_original, meeting_id, filename)

            else:
                raise ValueError(f"Unsupported file format: {filename}")

            # Update document with normalized path
            await firestore.update_document(
                document_id,
                {
                    "source_file.gcs_normalized_path": gcs_normalized,
                    "status": DocumentStatus.NORMALIZED.value,
                    "updated_at": datetime.utcnow().isoformat(),
                },
            )

            return gcs_normalized

        except Exception as e:
            await firestore.update_document(
                document_id,
                {
                    "status": DocumentStatus.ERROR.value,
                    "error_message": f"Normalization failed: {e}",
                    "updated_at": datetime.utcnow().isoformat(),
                },
            )
            raise

    async def _convert_doc_to_docx(
        self,
        gcs_original: str,
        meeting_id: str,
        filename: str,
    ) -> str:
        """
        Convert .doc file to .docx using LibreOffice.

        Args:
            gcs_original: GCS path of original .doc file.
            meeting_id: Meeting ID for output path.
            filename: Original filename.

        Returns:
            GCS path of converted .docx file.

        Raises:
            RuntimeError: If conversion fails.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Download original file
            local_doc = tmpdir_path / filename
            await self.storage.download_file(gcs_original, local_doc)

            # Convert using LibreOffice headless
            try:
                result = subprocess.run(
                    [
                        "soffice",
                        "--headless",
                        "--convert-to",
                        "docx",
                        "--outdir",
                        str(tmpdir_path),
                        str(local_doc),
                    ],
                    capture_output=True,
                    text=True,
                    timeout=self.timeout,
                )

                if result.returncode != 0:
                    raise RuntimeError(f"LibreOffice conversion failed: {result.stderr}")

            except subprocess.TimeoutExpired:
                raise RuntimeError(f"Conversion timed out after {self.timeout}s")

            except FileNotFoundError:
                raise RuntimeError(
                    "LibreOffice not found. Install with: apt-get install libreoffice"
                )

            # Find converted file
            base_name = Path(filename).stem
            local_docx = tmpdir_path / f"{base_name}.docx"

            if not local_docx.exists():
                raise RuntimeError(f"Converted file not found: {local_docx}")

            # Upload to GCS
            gcs_normalized = self.storage.get_normalized_path(meeting_id, filename)
            await self.storage.upload_file(local_docx, gcs_normalized)

            return gcs_normalized

    async def normalize_batch(
        self,
        document_ids: list[str],
        firestore: FirestoreClient,
    ) -> dict:
        """
        Normalize multiple documents.

        Args:
            document_ids: List of document IDs to normalize.
            firestore: Firestore client.

        Returns:
            Dict with success/failure counts and errors.
        """
        result = {
            "total": len(document_ids),
            "success": 0,
            "failed": 0,
            "errors": [],
        }

        for doc_id in document_ids:
            try:
                await self.normalize_document(doc_id, firestore)
                result["success"] += 1
            except Exception as e:
                result["failed"] += 1
                result["errors"].append(f"{doc_id}: {e}")

        return result
