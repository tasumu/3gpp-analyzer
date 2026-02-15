"""File normalization service for doc to docx conversion (P1-02)."""

import subprocess
import tempfile
import zipfile
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

    def _is_zip(self, filename: str) -> bool:
        """Check if file is a ZIP archive."""
        return filename.lower().endswith(".zip")

    def _extract_doc_from_zip(self, zip_path: Path, output_dir: Path) -> Path | None:
        """
        Extract the main document from a ZIP file.

        Looks for .docx or .doc files in the ZIP, preferring .docx.

        Args:
            zip_path: Path to ZIP file.
            output_dir: Directory to extract to.

        Returns:
            Path to extracted document, or None if no document found.
        """
        with zipfile.ZipFile(zip_path, "r") as zf:
            # Get list of doc/docx files
            doc_files = [
                f
                for f in zf.namelist()
                if f.lower().endswith((".doc", ".docx"))
                and not f.startswith("__MACOSX")
                and not f.startswith(".")
            ]

            if not doc_files:
                return None

            # Prefer .docx over .doc
            docx_files = [f for f in doc_files if f.lower().endswith(".docx")]
            target = docx_files[0] if docx_files else doc_files[0]

            # Extract the file
            zf.extract(target, output_dir)
            return output_dir / target

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

            elif self._is_zip(filename):
                gcs_normalized = await self._normalize_from_zip(gcs_original, meeting_id, filename)

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

    async def _normalize_from_zip(
        self,
        gcs_original: str,
        meeting_id: str,
        filename: str,
    ) -> str:
        """
        Extract document from ZIP and normalize it.

        Args:
            gcs_original: GCS path of original ZIP file.
            meeting_id: Meeting ID for output path.
            filename: Original ZIP filename.

        Returns:
            GCS path of normalized .docx file.

        Raises:
            ValueError: If no document found in ZIP.
            RuntimeError: If conversion fails.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Download ZIP file
            local_zip = tmpdir_path / filename
            await self.storage.download_file(gcs_original, local_zip)

            # Extract document from ZIP
            extracted_doc = self._extract_doc_from_zip(local_zip, tmpdir_path)
            if not extracted_doc:
                raise ValueError(f"No document found in ZIP: {filename}")

            extracted_filename = extracted_doc.name

            # If it's already docx, upload directly
            if extracted_filename.lower().endswith(".docx"):
                gcs_normalized = self.storage.get_normalized_path(meeting_id, filename)
                await self.storage.upload_file(extracted_doc, gcs_normalized)
                return gcs_normalized

            # Convert .doc to .docx
            try:
                result = subprocess.run(
                    [
                        "soffice",
                        "--headless",
                        "--convert-to",
                        "docx",
                        "--outdir",
                        str(tmpdir_path),
                        str(extracted_doc),
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
            base_name = Path(extracted_filename).stem
            local_docx = tmpdir_path / f"{base_name}.docx"

            if not local_docx.exists():
                raise RuntimeError(f"Converted file not found: {local_docx}")

            # Upload to GCS
            gcs_normalized = self.storage.get_normalized_path(meeting_id, filename)
            await self.storage.upload_file(local_docx, gcs_normalized)

            return gcs_normalized

    def extract_and_normalize_all(self, zip_path: Path, output_dir: Path) -> list[tuple[str, Path]]:
        """
        Extract and normalize all doc/docx files from a ZIP.

        Extracts every Word document (.doc, .docx) from the ZIP archive,
        converts .doc files to .docx using LibreOffice, and returns paths
        to all resulting .docx files.

        Args:
            zip_path: Path to the ZIP file.
            output_dir: Directory to extract and convert files in.

        Returns:
            List of (source_filename, local_docx_path) tuples.
            Sorted with .docx files first, then .doc files.
            Empty list if no Word documents found.
        """
        with zipfile.ZipFile(zip_path, "r") as zf:
            doc_files = [
                f
                for f in zf.namelist()
                if f.lower().endswith((".doc", ".docx"))
                and not f.startswith("__MACOSX")
                and not f.startswith(".")
            ]

        if not doc_files:
            return []

        # Sort: .docx first, then .doc
        docx_files = sorted(f for f in doc_files if f.lower().endswith(".docx"))
        doc_only = sorted(
            f for f in doc_files if f.lower().endswith(".doc") and not f.lower().endswith(".docx")
        )
        sorted_files = docx_files + doc_only

        results: list[tuple[str, Path]] = []
        for doc_file in sorted_files:
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extract(doc_file, output_dir)
            extracted_path = output_dir / doc_file
            source_filename = Path(doc_file).name

            if source_filename.lower().endswith(".docx"):
                results.append((source_filename, extracted_path))
            else:
                # Convert .doc to .docx using LibreOffice
                try:
                    result = subprocess.run(
                        [
                            "soffice",
                            "--headless",
                            "--convert-to",
                            "docx",
                            "--outdir",
                            str(extracted_path.parent),
                            str(extracted_path),
                        ],
                        capture_output=True,
                        text=True,
                        timeout=self.timeout,
                    )
                    if result.returncode != 0:
                        continue  # Skip files that fail to convert

                    docx_path = extracted_path.parent / f"{Path(source_filename).stem}.docx"
                    if docx_path.exists():
                        results.append((source_filename, docx_path))
                except (subprocess.TimeoutExpired, FileNotFoundError):
                    continue  # Skip files that fail to convert

        return results

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
