"""FTP synchronization service for 3GPP documents (P1-01)."""

import re
from datetime import datetime
from ftplib import FTP
from typing import Callable

from analyzer.models.document import Document, DocumentStatus, Meeting, SourceFile
from analyzer.providers.firestore_client import FirestoreClient
from analyzer.providers.storage_client import StorageClient

# Contribution number pattern: e.g., S2-2401234, R1-2312345
CONTRIBUTION_PATTERN = re.compile(r"^([A-Z]\d-\d{6,7})")


class FTPSyncService:
    """
    Service for synchronizing 3GPP documents from FTP.

    Implements metadata-first synchronization:
    1. List files from FTP and extract metadata
    2. Store metadata in Firestore with status=metadata_only
    3. Download files on-demand when processing is requested

    FTP structure: ftp.3gpp.org/Meetings/{WG}/{meeting}/Docs/
    """

    def __init__(
        self,
        firestore: FirestoreClient,
        storage: StorageClient,
        host: str = "ftp.3gpp.org",
        user: str = "anonymous",
        password: str = "",
        base_path: str = "/Meetings",
    ):
        """
        Initialize FTP sync service.

        Args:
            firestore: Firestore client for document storage.
            storage: GCS client for file storage.
            host: FTP server hostname.
            user: FTP username.
            password: FTP password.
            base_path: Base path on FTP server.
        """
        self.firestore = firestore
        self.storage = storage
        self.host = host
        self.user = user
        self.password = password
        self.base_path = base_path

    def _connect(self) -> FTP:
        """Establish FTP connection."""
        ftp = FTP(self.host)
        ftp.login(self.user, self.password)
        return ftp

    def _parse_contribution_number(self, filename: str) -> str | None:
        """Extract contribution number from filename."""
        match = CONTRIBUTION_PATTERN.match(filename)
        if match:
            return match.group(1)
        return None

    def _parse_meeting_path(self, path: str) -> Meeting | None:
        """Parse meeting information from FTP path."""
        # Expected format: /Meetings/{WG}/{meeting_name}/Docs/
        # e.g., /Meetings/SA2/SA2_162/Docs/
        parts = path.strip("/").split("/")
        if len(parts) >= 3:
            wg = parts[1]  # Working group
            meeting_name = parts[2]  # Meeting name

            # Extract meeting ID (e.g., SA2#162 from SA2_162)
            meeting_id = meeting_name.replace("_", "#")

            return Meeting(
                id=meeting_id,
                name=meeting_name,
                working_group=wg,
            )
        return None

    async def list_meeting_files(
        self,
        meeting_path: str,
    ) -> list[dict]:
        """
        List all document files in a meeting directory.

        Args:
            meeting_path: Path to meeting docs folder (e.g., /Meetings/SA2/SA2_162/Docs)

        Returns:
            List of file info dicts with filename, size, modified_at.
        """
        files = []
        ftp = self._connect()

        try:
            ftp.cwd(meeting_path)

            # Use MLSD for detailed file listing
            for entry in ftp.mlsd():
                name, facts = entry
                if facts.get("type") == "file":
                    # Filter for document files
                    if name.lower().endswith((".doc", ".docx", ".zip")):
                        # Parse modification time
                        modify_str = facts.get("modify", "")
                        if modify_str:
                            modified_at = datetime.strptime(modify_str, "%Y%m%d%H%M%S")
                        else:
                            modified_at = datetime.utcnow()

                        files.append({
                            "filename": name,
                            "size_bytes": int(facts.get("size", 0)),
                            "modified_at": modified_at,
                            "ftp_path": f"{meeting_path}/{name}",
                        })
        finally:
            ftp.quit()

        return files

    async def sync_meeting(
        self,
        meeting_path: str,
        path_pattern: str | None = None,
        progress_callback: Callable[[str, int, int], None] | None = None,
    ) -> dict:
        """
        Sync metadata for all documents in a meeting.

        Args:
            meeting_path: Path to meeting docs folder.
            path_pattern: Optional regex pattern to filter files.
            progress_callback: Optional callback(message, current, total).

        Returns:
            Sync result with counts of found, new, and updated documents.
        """
        meeting = self._parse_meeting_path(meeting_path)
        if not meeting:
            raise ValueError(f"Could not parse meeting from path: {meeting_path}")

        # List files from FTP
        files = await self.list_meeting_files(meeting_path)

        # Filter by pattern if provided
        if path_pattern:
            pattern = re.compile(path_pattern)
            files = [f for f in files if pattern.search(f["filename"])]

        result = {
            "meeting_id": meeting.id,
            "documents_found": len(files),
            "documents_new": 0,
            "documents_updated": 0,
            "errors": [],
        }

        total = len(files)
        for i, file_info in enumerate(files):
            try:
                if progress_callback:
                    progress_callback(f"Processing {file_info['filename']}", i + 1, total)

                # Extract contribution number
                contrib_num = self._parse_contribution_number(file_info["filename"])
                if not contrib_num:
                    # Skip files without valid contribution number
                    continue

                # Create document ID
                doc_id = contrib_num

                # Check if document exists
                existing = await self.firestore.get_document(doc_id)

                source_file = SourceFile(
                    filename=file_info["filename"],
                    ftp_path=file_info["ftp_path"],
                    size_bytes=file_info["size_bytes"],
                    modified_at=file_info["modified_at"],
                )

                if existing:
                    # Update if file has changed
                    existing_modified = existing.get("source_file", {}).get("modified_at")
                    if existing_modified != file_info["modified_at"].isoformat():
                        await self.firestore.update_document(doc_id, {
                            "source_file": source_file.model_dump(mode="json"),
                            "updated_at": datetime.utcnow().isoformat(),
                        })
                        result["documents_updated"] += 1
                else:
                    # Create new document with metadata only
                    doc = Document(
                        id=doc_id,
                        contribution_number=contrib_num,
                        meeting=meeting,
                        source_file=source_file,
                        status=DocumentStatus.METADATA_ONLY,
                    )
                    await self.firestore.create_document(doc_id, doc.to_firestore())
                    result["documents_new"] += 1

            except Exception as e:
                result["errors"].append(f"Error processing {file_info['filename']}: {e}")

        return result

    async def download_document(self, document_id: str) -> str:
        """
        Download a document file from FTP to GCS.

        Args:
            document_id: Document ID to download.

        Returns:
            GCS path of downloaded file.

        Raises:
            ValueError: If document not found or missing FTP path.
        """
        # Get document from Firestore
        doc_data = await self.firestore.get_document(document_id)
        if not doc_data:
            raise ValueError(f"Document not found: {document_id}")

        source_file = doc_data.get("source_file", {})
        ftp_path = source_file.get("ftp_path")
        if not ftp_path:
            raise ValueError(f"Document has no FTP path: {document_id}")

        # Update status
        await self.firestore.update_document(document_id, {
            "status": DocumentStatus.DOWNLOADING.value,
            "updated_at": datetime.utcnow().isoformat(),
        })

        try:
            # Download from FTP
            ftp = self._connect()
            data = bytearray()

            try:
                ftp.retrbinary(f"RETR {ftp_path}", data.extend)
            finally:
                ftp.quit()

            # Upload to GCS
            meeting_id = doc_data.get("meeting", {}).get("id", "unknown")
            filename = source_file.get("filename")
            gcs_path = self.storage.get_original_path(meeting_id, filename)

            await self.storage.upload_bytes(bytes(data), gcs_path)

            # Update document with GCS path
            await self.firestore.update_document(document_id, {
                "source_file.gcs_original_path": gcs_path,
                "status": DocumentStatus.DOWNLOADED.value,
                "updated_at": datetime.utcnow().isoformat(),
            })

            return gcs_path

        except Exception as e:
            await self.firestore.update_document(document_id, {
                "status": DocumentStatus.ERROR.value,
                "error_message": f"Download failed: {e}",
                "updated_at": datetime.utcnow().isoformat(),
            })
            raise
