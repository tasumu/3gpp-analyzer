"""Document CRUD service."""

from datetime import datetime

from analyzer.models.document import Document, DocumentStatus
from analyzer.providers.firestore_client import FirestoreClient
from analyzer.providers.storage_client import StorageClient


class DocumentService:
    """
    Service for document CRUD operations.

    Provides a clean interface for document management without
    exposing Firestore implementation details.
    """

    def __init__(
        self,
        firestore: FirestoreClient,
        storage: StorageClient,
    ):
        """
        Initialize document service.

        Args:
            firestore: Firestore client.
            storage: GCS storage client.
        """
        self.firestore = firestore
        self.storage = storage

    async def get(self, document_id: str) -> Document | None:
        """
        Get a document by ID.

        Args:
            document_id: Document ID.

        Returns:
            Document if found, None otherwise.
        """
        data = await self.firestore.get_document(document_id)
        if data:
            return Document.from_firestore(data["id"], data)
        return None

    async def list_documents(
        self,
        meeting_id: str | None = None,
        status: DocumentStatus | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[Document], int]:
        """
        List documents with optional filters.

        Args:
            meeting_id: Filter by meeting ID.
            status: Filter by processing status.
            page: Page number (1-indexed).
            page_size: Items per page.

        Returns:
            Tuple of (documents, total_count).
        """
        filters = {}
        if meeting_id:
            filters["meeting.id"] = meeting_id
        if status:
            filters["status"] = status.value

        # Get total count
        total = await self.firestore.count_documents(filters)

        # Get paginated results
        offset = (page - 1) * page_size
        docs_data = await self.firestore.list_documents(
            filters=filters,
            order_by="updated_at",
            limit=page_size,
            offset=offset,
        )

        documents = [
            Document.from_firestore(d["id"], d)
            for d in docs_data
        ]

        return documents, total

    async def create(self, document: Document) -> Document:
        """
        Create a new document.

        Args:
            document: Document to create.

        Returns:
            Created document.
        """
        await self.firestore.create_document(
            document.id,
            document.to_firestore(),
        )
        return document

    async def update(
        self,
        document_id: str,
        updates: dict,
    ) -> Document | None:
        """
        Update a document.

        Args:
            document_id: Document ID.
            updates: Fields to update.

        Returns:
            Updated document if found.
        """
        updates["updated_at"] = datetime.utcnow().isoformat()
        await self.firestore.update_document(document_id, updates)
        return await self.get(document_id)

    async def update_status(
        self,
        document_id: str,
        status: DocumentStatus,
        error_message: str | None = None,
    ) -> Document | None:
        """
        Update document processing status.

        Args:
            document_id: Document ID.
            status: New status.
            error_message: Optional error message for ERROR status.

        Returns:
            Updated document if found.
        """
        updates = {
            "status": status.value,
            "updated_at": datetime.utcnow().isoformat(),
        }
        if error_message:
            updates["error_message"] = error_message
        elif status != DocumentStatus.ERROR:
            updates["error_message"] = None

        await self.firestore.update_document(document_id, updates)
        return await self.get(document_id)

    async def delete(self, document_id: str) -> bool:
        """
        Delete a document and its associated data.

        Args:
            document_id: Document ID.

        Returns:
            True if deleted.
        """
        # Get document to find storage paths
        doc = await self.get(document_id)
        if not doc:
            return False

        # Delete chunks
        await self.firestore.delete_chunks_by_document(document_id)

        # Delete files from GCS
        if doc.source_file.gcs_original_path:
            try:
                await self.storage.delete(doc.source_file.gcs_original_path)
            except Exception:
                pass  # Ignore if file doesn't exist

        if doc.source_file.gcs_normalized_path:
            try:
                await self.storage.delete(doc.source_file.gcs_normalized_path)
            except Exception:
                pass

        # Delete document
        await self.firestore.delete_document(document_id)
        return True

    async def get_download_url(
        self,
        document_id: str,
        normalized: bool = True,
        expiration_minutes: int = 60,
    ) -> str | None:
        """
        Get a signed download URL for a document.

        Args:
            document_id: Document ID.
            normalized: If True, get normalized docx; otherwise original.
            expiration_minutes: URL expiration time.

        Returns:
            Signed URL or None if not available.
        """
        doc = await self.get(document_id)
        if not doc:
            return None

        path = (
            doc.source_file.gcs_normalized_path
            if normalized
            else doc.source_file.gcs_original_path
        )

        if not path:
            return None

        return await self.storage.generate_signed_url(path, expiration_minutes)

    async def get_meetings(self) -> list[dict]:
        """
        Get list of unique meetings with document counts.

        Returns:
            List of meeting info dicts.
        """
        # Get all documents and aggregate by meeting
        docs = await self.firestore.list_documents(limit=10000)

        meetings = {}
        for doc in docs:
            meeting = doc.get("meeting")
            if meeting:
                meeting_id = meeting.get("id")
                if meeting_id not in meetings:
                    meetings[meeting_id] = {
                        "id": meeting_id,
                        "name": meeting.get("name"),
                        "working_group": meeting.get("working_group"),
                        "document_count": 0,
                        "indexed_count": 0,
                    }
                meetings[meeting_id]["document_count"] += 1
                if doc.get("status") == DocumentStatus.INDEXED.value:
                    meetings[meeting_id]["indexed_count"] += 1

        return list(meetings.values())
