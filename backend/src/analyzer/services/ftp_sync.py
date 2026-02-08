"""FTP synchronization service for 3GPP documents (P1-01)."""

import asyncio
import hashlib
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from ftplib import FTP
from typing import Callable

from analyzer.models.document import Document, DocumentStatus, DocumentType, Meeting, SourceFile
from analyzer.models.sync_history import SyncHistory
from analyzer.providers.firestore_client import FirestoreClient
from analyzer.providers.storage_client import StorageClient

logger = logging.getLogger(__name__)

# Contribution number pattern: e.g., S2-2401234, R1-2312345
CONTRIBUTION_PATTERN = re.compile(r"^([A-Z]\d-\d{6,7})")


@dataclass
class DirectoryEntry:
    """Represents a file or directory entry in FTP listing."""

    name: str
    entry_type: str  # "directory" or "file"
    size: int | None = None  # Only for files
    synced: bool = False  # Only for directories
    synced_count: int | None = None  # Only for directories


class FTPSyncService:
    """
    Service for synchronizing 3GPP documents from FTP.

    Implements metadata-first synchronization:
    1. List files from FTP and extract metadata
    2. Store metadata in Firestore with status=metadata_only
    3. Download files on-demand when processing is requested

    FTP structure: ftp.3gpp.org/Meetings/{WG}/{meeting}/Docs/
    """

    SYNC_HISTORY_COLLECTION = "sync_history"

    # Mock data for development when FTP is unavailable
    MOCK_DIRECTORIES: dict[str, list[tuple[str, str, int | None]]] = {
        "/": [
            ("Meetings", "directory", None),
            ("Specs", "directory", None),
            ("Information", "directory", None),
            ("readme.txt", "file", 1024),
        ],
        "/Meetings": [
            ("SA2", "directory", None),
            ("SA3", "directory", None),
            ("RAN1", "directory", None),
            ("RAN2", "directory", None),
            ("CT1", "directory", None),
        ],
        "/Meetings/SA2": [
            ("SA2_163", "directory", None),
            ("SA2_162", "directory", None),
            ("SA2_161", "directory", None),
        ],
        "/Meetings/SA2/SA2_163": [
            ("Docs", "directory", None),
            ("Agenda", "directory", None),
        ],
        "/Meetings/SA2/SA2_163/Docs": [
            ("S2-2401001.zip", "file", 102400),
            ("S2-2401002.zip", "file", 204800),
            ("S2-2401003.doc", "file", 51200),
            ("S2-2401004.docx", "file", 76800),
        ],
    }

    def __init__(
        self,
        firestore: FirestoreClient,
        storage: StorageClient,
        host: str = "ftp.3gpp.org",
        user: str = "anonymous",
        password: str = "",
        base_path: str = "/Meetings",
        mock_mode: bool = False,
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
            mock_mode: Use mock data instead of real FTP (for development).
        """
        self.firestore = firestore
        self.storage = storage
        self.host = host
        self.user = user
        self.password = password
        self.base_path = base_path
        self.mock_mode = mock_mode

    def _connect(self, timeout: int = 60) -> FTP:
        """Establish FTP connection."""
        ftp = FTP(self.host, timeout=timeout)
        ftp.login(self.user, self.password)

        # Patch makepasv to handle EPSV responses from servers like 3gpp.org
        # Some servers return EPSV (229) response even for PASV command
        host = ftp.host  # Capture host for closure

        def patched_makepasv() -> tuple[str, int]:
            # Send PASV and check if we get an EPSV-style response
            resp = ftp.sendcmd("PASV")
            # Check for EPSV response format: 229 Extended Passive Mode Entered (|||port|)
            epsv_match = re.search(r"\|\|\|(\d+)\|", resp)
            if epsv_match:
                port = int(epsv_match.group(1))
                return (host, port)
            # Standard PASV response: 227 Entering Passive Mode (h1,h2,h3,h4,p1,p2)
            pasv_match = re.search(r"\((\d+),(\d+),(\d+),(\d+),(\d+),(\d+)\)", resp)
            if pasv_match:
                numbers = [int(x) for x in pasv_match.groups()]
                pasv_host = ".".join(str(n) for n in numbers[:4])
                port = (numbers[4] << 8) + numbers[5]
                return (pasv_host, port)
            raise ValueError(f"Cannot parse PASV response: {resp}")

        ftp.makepasv = patched_makepasv  # type: ignore[method-assign]
        return ftp

    def _list_directory_with_fallback(self, ftp: FTP) -> list[tuple[str, dict]]:
        """
        List directory using MLSD, falling back to LIST if MLSD is not supported.

        Some FTP servers (including 3gpp.org) don't support MLSD command.
        This method tries MLSD first, then falls back to parsing LIST output.

        Returns:
            List of (name, facts) tuples in MLSD format.
        """
        try:
            return list(ftp.mlsd())
        except Exception:
            # MLSD not supported, fall back to LIST
            lines: list[str] = []
            ftp.retrlines("LIST", lines.append)
            return self._parse_list_output(lines)

    def _parse_list_output(self, lines: list[str]) -> list[tuple[str, dict]]:
        """
        Parse LIST output into MLSD-compatible format.

        Handles both Unix-style and Windows IIS-style listings:

        Unix-style:
        drwxr-xr-x  2 user group  4096 Jan 31 10:00 dirname
        -rw-r--r--  1 user group 12345 Jan 31 10:00 filename.doc

        Windows IIS-style (used by 3gpp.org):
        02-21-19  10:39AM       <DIR>          dirname
        01-31-26  10:00AM               12345 filename.doc

        Returns:
            List of (name, facts) tuples compatible with MLSD format.
        """
        result: list[tuple[str, dict]] = []

        for line in lines:
            if not line.strip():
                continue

            # Try Windows IIS format first (3gpp.org uses this)
            # Format: MM-DD-YY  HH:MMAM/PM  <DIR>|size  name
            iis_match = re.match(
                r"(\d{2}-\d{2}-\d{2})\s+(\d{1,2}:\d{2}[AP]M)\s+(<DIR>|\d+)\s+(.+)", line
            )
            if iis_match:
                dir_or_size = iis_match.group(3)
                name = iis_match.group(4).strip()

                if name in (".", ".."):
                    continue

                if dir_or_size == "<DIR>":
                    facts = {"type": "dir"}
                else:
                    facts = {"type": "file", "size": dir_or_size}

                result.append((name, facts))
                continue

            # Fall back to Unix format
            parts = line.split()
            if len(parts) < 9:
                continue

            permissions = parts[0]
            size = parts[4]
            # Handle filenames with spaces by joining all parts from index 8
            name = " ".join(parts[8:])

            if name in (".", ".."):
                continue

            if permissions.startswith("d"):
                facts = {"type": "dir"}
            elif permissions.startswith("l"):
                # Symbolic link - treat as directory for navigation
                facts = {"type": "dir"}
            else:
                facts = {"type": "file", "size": size}

            result.append((name, facts))

        return result

    def _list_directory_sync(self, path: str) -> list[tuple[str, str, int | None]]:
        """
        Synchronous FTP directory listing (runs in thread pool).

        Returns list of (name, type, size) tuples.
        """
        if self.mock_mode:
            return self.MOCK_DIRECTORIES.get(path, [])

        ftp = self._connect()
        try:
            ftp.cwd(path)
            result = []

            for name, facts in self._list_directory_with_fallback(ftp):
                if name in (".", ".."):
                    continue

                entry_type = facts.get("type", "")
                if entry_type == "dir":
                    result.append((name, "directory", None))
                elif entry_type == "file":
                    size = int(facts.get("size", 0))
                    result.append((name, "file", size))

            return result
        finally:
            ftp.quit()

    async def list_directory(self, path: str = "/") -> dict:
        """
        List contents of a directory on the FTP server.

        Args:
            path: Directory path to list (e.g., "/" or "/Meetings/SA2")

        Returns:
            Dict with path, parent, and entries list.
        """
        # Run blocking FTP operation in thread pool
        raw_entries = await asyncio.to_thread(self._list_directory_sync, path)

        entries: list[DirectoryEntry] = []
        for name, entry_type, size in raw_entries:
            if entry_type == "directory":
                full_path = f"{path.rstrip('/')}/{name}"
                synced_count = await self._count_synced_documents(full_path)
                entries.append(
                    DirectoryEntry(
                        name=name,
                        entry_type="directory",
                        synced=synced_count > 0,
                        synced_count=synced_count if synced_count > 0 else None,
                    )
                )
            else:
                entries.append(
                    DirectoryEntry(
                        name=name,
                        entry_type="file",
                        size=size,
                    )
                )

        # Sort: directories first, then alphabetically
        entries.sort(key=lambda e: (e.entry_type != "directory", e.name.lower()))

        # Compute parent path
        parent = None
        if path != "/":
            parts = path.rstrip("/").rsplit("/", 1)
            parent = parts[0] if parts[0] else "/"

        return {
            "path": path,
            "parent": parent,
            "entries": entries,
        }

    async def _count_synced_documents(self, directory_path: str) -> int:
        """
        Count documents synced from a given FTP directory path.

        Checks if any documents have source_file.ftp_path starting with this directory.
        """
        # We need to query Firestore for documents with ftp_path starting with this path
        # Since Firestore doesn't support startsWith directly, we use range query
        path_prefix = f"{directory_path.rstrip('/')}/"

        try:
            query = (
                self.firestore.client.collection(FirestoreClient.DOCUMENTS_COLLECTION)
                .where("source_file.ftp_path", ">=", path_prefix)
                .where("source_file.ftp_path", "<", path_prefix + "\uffff")
            )
            count_query = query.count()
            results = count_query.get()
            return results[0][0].value
        except Exception:
            return 0

    def _parse_contribution_number(self, filename: str) -> str | None:
        """Extract contribution number from filename."""
        match = CONTRIBUTION_PATTERN.match(filename)
        if match:
            return match.group(1)
        return None

    def _generate_document_id(self, ftp_path: str, contribution_number: str | None) -> str:
        """
        Generate unique document ID.

        For contribution documents, use the contribution number as ID.
        For other documents, generate a stable hash from the FTP path.
        """
        if contribution_number:
            return contribution_number
        # Generate stable hash from ftp_path (first 16 chars of SHA256)
        return hashlib.sha256(ftp_path.encode()).hexdigest()[:16]

    def _determine_document_type(self, filename: str) -> DocumentType:
        """
        Determine document type based on filename pattern.

        Documents matching SX-XXXXXX pattern are contributions.
        All others are classified as OTHER.
        """
        if CONTRIBUTION_PATTERN.match(filename):
            return DocumentType.CONTRIBUTION
        return DocumentType.OTHER

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

    def _download_file_sync(self, ftp_path: str) -> bytes:
        """
        Synchronous file download from FTP (runs in thread pool).

        Returns file contents as bytes.
        """
        ftp = self._connect()
        data = bytearray()

        try:
            ftp.retrbinary(f"RETR {ftp_path}", data.extend)
        finally:
            ftp.quit()

        return bytes(data)

    def _list_meeting_files_sync(self, meeting_path: str) -> list[dict]:
        """
        Synchronous listing of meeting files (runs in thread pool).

        Returns list of file info dicts.
        """
        if self.mock_mode:
            mock_entries = self.MOCK_DIRECTORIES.get(meeting_path, [])
            files = []
            for name, entry_type, size in mock_entries:
                if entry_type == "file" and name.lower().endswith((".doc", ".docx", ".zip")):
                    files.append(
                        {
                            "filename": name,
                            "size_bytes": size or 0,
                            "modified_at": datetime.utcnow(),
                            "ftp_path": f"{meeting_path}/{name}",
                        }
                    )
            return files

        files: list[dict] = []
        # Use longer timeout for recursive operations
        ftp = self._connect(timeout=120)

        try:
            self._collect_files_recursive(ftp, meeting_path, files)
        finally:
            try:
                ftp.quit()
            except Exception:
                pass  # Connection may already be closed

        return files

    def _collect_files_recursive(self, ftp: FTP, path: str, files: list[dict]) -> None:
        """
        Recursively collect document files from FTP directory.

        Args:
            ftp: Active FTP connection.
            path: Current directory path.
            files: List to append found files to.
        """
        try:
            ftp.cwd(path)
        except Exception:
            # Directory doesn't exist or access denied
            return

        entries = self._list_directory_with_fallback(ftp)

        for name, facts in entries:
            if name in (".", ".."):
                continue

            entry_type = facts.get("type", "")
            full_path = f"{path.rstrip('/')}/{name}"

            if entry_type == "dir":
                # Recursively explore subdirectory
                self._collect_files_recursive(ftp, full_path, files)
                # Return to current directory after recursion
                try:
                    ftp.cwd(path)
                except Exception:
                    pass
            elif entry_type == "file":
                if name.lower().endswith((".doc", ".docx", ".zip")):
                    modify_str = facts.get("modify", "")
                    if modify_str:
                        modified_at = datetime.strptime(modify_str, "%Y%m%d%H%M%S")
                    else:
                        modified_at = datetime.utcnow()

                    files.append(
                        {
                            "filename": name,
                            "size_bytes": int(facts.get("size", 0)),
                            "modified_at": modified_at,
                            "ftp_path": full_path,
                        }
                    )

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
        return await asyncio.to_thread(self._list_meeting_files_sync, meeting_path)

    async def sync_directory(
        self,
        directory_path: str,
        path_pattern: str | None = None,
        include_non_contributions: bool = True,
        progress_callback: Callable[[str, int, int], None] | None = None,
    ) -> dict:
        """
        Sync metadata for all documents in a directory (recursively).

        Works for any FTP directory - meeting docs, specs, or other paths.

        Args:
            directory_path: Path to FTP directory (e.g., /Meetings/SA2/SA2_162/Docs).
            path_pattern: Optional regex pattern to filter files.
            include_non_contributions: If True, include files without contribution numbers.
            progress_callback: Optional callback(message, current, total).

        Returns:
            Sync result with counts of found, new, and updated documents.
        """
        # Try to parse meeting info from path (only works for /Meetings/... paths)
        meeting = self._parse_meeting_path(directory_path)

        # List files from FTP (reusing the existing method)
        files = await self.list_meeting_files(directory_path)

        # Filter by pattern if provided
        if path_pattern:
            pattern = re.compile(path_pattern)
            files = [f for f in files if pattern.search(f["filename"])]

        result = {
            "meeting_id": meeting.id if meeting else None,
            "directory_path": directory_path,
            "documents_found": len(files),
            "documents_new": 0,
            "documents_updated": 0,
            "documents_skipped": 0,
            "errors": [],
        }

        total = len(files)
        for i, file_info in enumerate(files):
            try:
                if progress_callback:
                    progress_callback(f"Processing {file_info['filename']}", i + 1, total)

                # Extract contribution number (may be None for non-contribution files)
                contrib_num = self._parse_contribution_number(file_info["filename"])

                # Skip non-contribution files if not included
                if not contrib_num and not include_non_contributions:
                    logger.info(f"Skipped (no contribution number): {file_info['filename']}")
                    result["documents_skipped"] += 1
                    continue

                # Determine document type and generate ID
                doc_type = self._determine_document_type(file_info["filename"])
                doc_id = self._generate_document_id(file_info["ftp_path"], contrib_num)

                # Check if document exists
                existing = await self.firestore.get_document(doc_id)

                if existing:
                    # Update if file has changed
                    existing_modified = existing.get("source_file", {}).get("modified_at")
                    if existing_modified != file_info["modified_at"].isoformat():
                        # Preserve existing GCS paths when updating metadata
                        existing_source = existing.get("source_file", {})
                        source_file = SourceFile(
                            filename=file_info["filename"],
                            ftp_path=file_info["ftp_path"],
                            size_bytes=file_info["size_bytes"],
                            modified_at=file_info["modified_at"],
                            gcs_original_path=existing_source.get("gcs_original_path"),
                            gcs_normalized_path=existing_source.get("gcs_normalized_path"),
                        )
                        await self.firestore.update_document(
                            doc_id,
                            {
                                "source_file": source_file.model_dump(mode="json"),
                                "updated_at": datetime.utcnow().isoformat(),
                            },
                        )
                        result["documents_updated"] += 1
                else:
                    # Create new document - no existing GCS paths to preserve
                    source_file = SourceFile(
                        filename=file_info["filename"],
                        ftp_path=file_info["ftp_path"],
                        size_bytes=file_info["size_bytes"],
                        modified_at=file_info["modified_at"],
                    )
                    # Create new document with metadata only
                    doc = Document(
                        id=doc_id,
                        contribution_number=contrib_num,
                        document_type=doc_type,
                        meeting=meeting,
                        source_file=source_file,
                        status=DocumentStatus.METADATA_ONLY,
                    )
                    await self.firestore.create_document(doc_id, doc.to_firestore())
                    result["documents_new"] += 1

            except Exception as e:
                result["errors"].append(f"Error processing {file_info['filename']}: {e}")

        return result

    async def record_sync(
        self,
        directory_path: str,
        result: dict,
    ) -> None:
        """
        Record a sync operation in sync_history collection.

        Creates or updates the sync history entry for the given directory.
        """
        doc_id = SyncHistory.generate_id(directory_path)
        synced_count = await self._count_synced_documents(directory_path)

        history = SyncHistory(
            id=doc_id,
            directory_path=directory_path,
            last_synced_at=datetime.utcnow(),
            documents_found=result.get("documents_found", 0),
            documents_new=result.get("documents_new", 0),
            documents_updated=result.get("documents_updated", 0),
            synced_count=synced_count,
        )

        doc_ref = self.firestore.client.collection(self.SYNC_HISTORY_COLLECTION).document(doc_id)
        doc_ref.set(history.to_firestore())
        logger.info(f"Recorded sync history for {directory_path}")

    async def get_sync_history(self, limit: int = 20) -> list[SyncHistory]:
        """
        Get list of previously synced directories.

        Returns entries sorted by last_synced_at descending.
        """
        query = (
            self.firestore.client.collection(self.SYNC_HISTORY_COLLECTION)
            .order_by("last_synced_at", direction="DESCENDING")
            .limit(limit)
        )

        entries = []
        for doc in query.stream():
            entries.append(SyncHistory.from_firestore(doc.id, doc.to_dict()))

        return entries

    async def sync_meeting(
        self,
        meeting_path: str,
        path_pattern: str | None = None,
        progress_callback: Callable[[str, int, int], None] | None = None,
    ) -> dict:
        """
        Sync metadata for all documents in a meeting (legacy method for backward compatibility).

        This method is a wrapper around sync_directory for backward compatibility.
        New code should use sync_directory directly.

        Args:
            meeting_path: Path to meeting docs folder.
            path_pattern: Optional regex pattern to filter files.
            progress_callback: Optional callback(message, current, total).

        Returns:
            Sync result with counts of found, new, and updated documents.
        """
        # For backward compatibility, validate that this is a meeting path
        meeting = self._parse_meeting_path(meeting_path)
        if not meeting:
            raise ValueError(f"Could not parse meeting from path: {meeting_path}")

        return await self.sync_directory(
            directory_path=meeting_path,
            path_pattern=path_pattern,
            include_non_contributions=True,
            progress_callback=progress_callback,
        )

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
        await self.firestore.update_document(
            document_id,
            {
                "status": DocumentStatus.DOWNLOADING.value,
                "updated_at": datetime.utcnow().isoformat(),
            },
        )

        try:
            # Download from FTP (run in thread pool)
            data = await asyncio.to_thread(self._download_file_sync, ftp_path)

            # Upload to GCS
            meeting_id = doc_data.get("meeting", {}).get("id", "unknown")
            filename = source_file.get("filename")
            gcs_path = self.storage.get_original_path(meeting_id, filename)

            await self.storage.upload_bytes(bytes(data), gcs_path)

            # Update document with GCS path
            await self.firestore.update_document(
                document_id,
                {
                    "source_file.gcs_original_path": gcs_path,
                    "status": DocumentStatus.DOWNLOADED.value,
                    "updated_at": datetime.utcnow().isoformat(),
                },
            )

            return gcs_path

        except Exception as e:
            await self.firestore.update_document(
                document_id,
                {
                    "status": DocumentStatus.ERROR.value,
                    "error_message": f"Download failed: {e}",
                    "updated_at": datetime.utcnow().isoformat(),
                },
            )
            raise
