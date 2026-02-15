"""Firestore client wrapper for database operations."""

import os
from typing import Any

from google.cloud import firestore
from google.cloud.firestore_v1.base_vector_query import DistanceMeasure
from google.cloud.firestore_v1.vector import Vector


class FirestoreClient:
    """
    Wrapper for Firestore operations.

    Handles connection management, emulator support, and common operations.
    """

    DOCUMENTS_COLLECTION = "documents"
    CHUNKS_COLLECTION = "chunks"

    def __init__(
        self,
        project_id: str,
        use_emulator: bool = False,
        emulator_host: str = "localhost:8080",
    ):
        """
        Initialize Firestore client.

        Args:
            project_id: GCP project ID.
            use_emulator: Whether to use Firebase Emulator.
            emulator_host: Emulator host:port.
        """
        self.project_id = project_id
        self.use_emulator = use_emulator

        if use_emulator:
            os.environ["FIRESTORE_EMULATOR_HOST"] = emulator_host

        self._client = firestore.Client(project=project_id)

    @property
    def client(self) -> firestore.Client:
        """Get the Firestore client instance."""
        return self._client

    # Document operations

    async def get_document(self, doc_id: str) -> dict | None:
        """Get a document by ID."""
        doc_ref = self._client.collection(self.DOCUMENTS_COLLECTION).document(doc_id)
        doc = doc_ref.get()
        if doc.exists:
            return {"id": doc.id, **doc.to_dict()}
        return None

    async def create_document(self, doc_id: str, data: dict) -> str:
        """Create a new document."""
        doc_ref = self._client.collection(self.DOCUMENTS_COLLECTION).document(doc_id)
        doc_ref.set(data)
        return doc_id

    async def update_document(self, doc_id: str, data: dict) -> None:
        """Update an existing document."""
        doc_ref = self._client.collection(self.DOCUMENTS_COLLECTION).document(doc_id)
        doc_ref.update(data)

    async def delete_document(self, doc_id: str) -> None:
        """Delete a document."""
        doc_ref = self._client.collection(self.DOCUMENTS_COLLECTION).document(doc_id)
        doc_ref.delete()

    async def list_documents(
        self,
        filters: dict | None = None,
        range_filters: dict | None = None,
        order_by: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict]:
        """
        List documents with optional filtering.

        Args:
            filters: Equality filters as {field: value}.
            range_filters: Range filter as {field, start, end} for prefix matching.
            order_by: Field to order by.
            limit: Maximum results.
            offset: Number of results to skip.

        Returns:
            List of document dicts.
        """
        query = self._client.collection(self.DOCUMENTS_COLLECTION)

        if filters:
            for field, value in filters.items():
                # Support __in suffix for "in" queries (e.g., "meeting.id__in")
                if field.endswith("__in"):
                    actual_field = field.replace("__in", "")
                    query = query.where(actual_field, "in", value)
                else:
                    query = query.where(field, "==", value)

        if range_filters:
            field = range_filters["field"]
            query = query.where(field, ">=", range_filters["start"])
            query = query.where(field, "<", range_filters["end"])

        if order_by:
            query = query.order_by(order_by)

        query = query.limit(limit).offset(offset)
        docs = query.stream()

        return [{"id": doc.id, **doc.to_dict()} for doc in docs]

    async def count_documents(
        self,
        filters: dict | None = None,
        range_filters: dict | None = None,
    ) -> int:
        """
        Count documents matching filters.

        Args:
            filters: Equality filters as {field: value} or {field__in: [values]} for "in" queries.
            range_filters: Range filter as {field, start, end} for prefix matching.

        Returns:
            Count of matching documents.
        """
        query = self._client.collection(self.DOCUMENTS_COLLECTION)

        if filters:
            for field, value in filters.items():
                # Support __in suffix for "in" queries (e.g., "meeting.id__in")
                if field.endswith("__in"):
                    actual_field = field.replace("__in", "")
                    query = query.where(actual_field, "in", value)
                else:
                    query = query.where(field, "==", value)

        if range_filters:
            field = range_filters["field"]
            query = query.where(field, ">=", range_filters["start"])
            query = query.where(field, "<", range_filters["end"])

        # Use aggregation query for count
        count_query = query.count()
        results = count_query.get()
        return results[0][0].value

    # Chunk operations

    async def create_chunk(self, chunk_id: str, data: dict) -> str:
        """Create a new chunk document."""
        doc_ref = self._client.collection(self.CHUNKS_COLLECTION).document(chunk_id)
        doc_ref.set(data)
        return chunk_id

    async def create_chunks_batch(self, chunks: list[dict]) -> int:
        """Create multiple chunks in a batch."""
        batch = self._client.batch()
        count = 0

        for chunk in chunks:
            chunk_id = chunk.pop("id", None)
            if not chunk_id:
                continue
            doc_ref = self._client.collection(self.CHUNKS_COLLECTION).document(chunk_id)
            batch.set(doc_ref, chunk)
            count += 1

            # Firestore batch limit is 500
            if count % 500 == 0:
                batch.commit()
                batch = self._client.batch()

        if count % 500 != 0:
            batch.commit()

        return count

    async def get_chunks_by_document(self, document_id: str, limit: int = 100) -> list[dict]:
        """Get all chunks for a document."""
        query = (
            self._client.collection(self.CHUNKS_COLLECTION)
            .where("metadata.document_id", "==", document_id)
            .limit(limit)
        )
        docs = query.stream()
        return [{"id": doc.id, **doc.to_dict()} for doc in docs]

    async def delete_chunks_by_document(self, document_id: str) -> int:
        """Delete all chunks for a document."""
        query = self._client.collection(self.CHUNKS_COLLECTION).where(
            "metadata.document_id", "==", document_id
        )
        docs = query.stream()

        batch = self._client.batch()
        count = 0

        for doc in docs:
            batch.delete(doc.reference)
            count += 1

            if count % 500 == 0:
                batch.commit()
                batch = self._client.batch()

        if count % 500 != 0:
            batch.commit()

        return count

    async def update_chunks_meeting_id(self, document_id: str, new_meeting_id: str) -> int:
        """Update meeting_id in metadata for all chunks of a document."""
        query = self._client.collection(self.CHUNKS_COLLECTION).where(
            "metadata.document_id", "==", document_id
        )
        docs = query.stream()

        batch = self._client.batch()
        count = 0

        for doc in docs:
            batch.update(doc.reference, {"metadata.meeting_id": new_meeting_id})
            count += 1

            if count % 500 == 0:
                batch.commit()
                batch = self._client.batch()

        if count > 0 and count % 500 != 0:
            batch.commit()

        return count

    # Vector search operations

    async def vector_search(
        self,
        query_embedding: list[float],
        filters: dict[str, Any] | None = None,
        top_k: int = 10,
    ) -> list[dict]:
        """
        Perform vector similarity search on chunks.

        Args:
            query_embedding: The query vector embedding.
            filters: Optional metadata filters (applied server-side via .where()).
            top_k: Number of results to return.

        Returns:
            List of chunks with similarity scores.
        """
        collection = self._client.collection(self.CHUNKS_COLLECTION)

        # Apply filters as Firestore .where() BEFORE vector search
        # This ensures the vector search only considers matching documents,
        # rather than filtering after retrieving top_k results globally.
        query = collection
        if filters:
            for key, value in filters.items():
                if key.endswith("__in"):
                    actual_field = key.replace("__in", "")
                    query = query.where(f"metadata.{actual_field}", "in", value)
                else:
                    query = query.where(f"metadata.{key}", "==", value)

        # Build the vector query on pre-filtered results
        vector_query = query.find_nearest(
            vector_field="embedding",
            query_vector=Vector(query_embedding),
            distance_measure=DistanceMeasure.COSINE,
            limit=top_k,
            distance_result_field="vector_distance",
        )

        # Execute and collect results
        results = []
        for doc in vector_query.stream():
            data = doc.to_dict()
            results.append({"id": doc.id, **data})

        return results
