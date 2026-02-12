"""Vectorization service for embedding generation (P1-04)."""

from datetime import datetime
from typing import Callable

from google import genai
from google.cloud.firestore_v1.vector import Vector

from analyzer.models.chunk import Chunk
from analyzer.models.document import DocumentStatus
from analyzer.providers.firestore_client import FirestoreClient


class VectorizerService:
    """
    Service for generating embeddings and indexing chunks.

    Uses Google's text-embedding model via the genai SDK.
    Chunks are stored in Firestore with vector embeddings for similarity search.
    """

    def __init__(
        self,
        firestore: FirestoreClient,
        project_id: str,
        location: str = "asia-northeast1",
        model: str = "gemini-embedding-001",
        dimensions: int = 768,
        batch_size: int = 100,
    ):
        """
        Initialize vectorizer service.

        Args:
            firestore: Firestore client for chunk storage.
            project_id: GCP project ID for Vertex AI.
            location: GCP region for Vertex AI.
            model: Embedding model name.
            dimensions: Embedding vector dimensions.
            batch_size: Number of chunks to embed per API call.
        """
        self.firestore = firestore
        self.model = model
        self.dimensions = dimensions
        self.batch_size = batch_size
        self._client = genai.Client(
            vertexai=True,
            project=project_id,
            location=location,
        )

    async def embed_text(self, text: str) -> list[float]:
        """
        Generate embedding for a single text.

        Args:
            text: Text to embed.

        Returns:
            Embedding vector.
        """
        response = self._client.models.embed_content(
            model=self.model,
            contents=text,
            config={"output_dimensionality": self.dimensions},
        )
        return response.embeddings[0].values

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Generate embeddings for multiple texts.

        Args:
            texts: List of texts to embed.

        Returns:
            List of embedding vectors.
        """
        if not texts:
            return []

        response = self._client.models.embed_content(
            model=self.model,
            contents=texts,
            config={"output_dimensionality": self.dimensions},
        )
        return [emb.values for emb in response.embeddings]

    async def vectorize_chunks(
        self,
        chunks: list[Chunk],
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> list[Chunk]:
        """
        Generate embeddings for a list of chunks.

        Args:
            chunks: Chunks to vectorize.
            progress_callback: Optional callback(current, total).

        Returns:
            Chunks with embeddings populated.
        """
        total = len(chunks)

        for i in range(0, total, self.batch_size):
            batch = chunks[i : i + self.batch_size]
            texts = [chunk.content for chunk in batch]

            # Generate embeddings
            embeddings = await self.embed_batch(texts)

            # Assign embeddings to chunks
            for chunk, embedding in zip(batch, embeddings):
                chunk.embedding = embedding

            if progress_callback:
                progress_callback(min(i + self.batch_size, total), total)

        return chunks

    async def index_document(
        self,
        document_id: str,
        chunks: list[Chunk],
        progress_callback: Callable[[str, float], None] | None = None,
    ) -> int:
        """
        Vectorize and index chunks for a document.

        Args:
            document_id: Parent document ID.
            chunks: Chunks to index.
            progress_callback: Optional callback(message, progress 0-1).

        Returns:
            Number of chunks indexed.
        """
        if not chunks:
            return 0

        # Update document status
        await self.firestore.update_document(
            document_id,
            {
                "status": DocumentStatus.INDEXING.value,
                "updated_at": datetime.utcnow().isoformat(),
            },
        )

        try:
            # Delete existing chunks for this document
            if progress_callback:
                progress_callback("Removing old chunks", 0.1)
            await self.firestore.delete_chunks_by_document(document_id)

            # Generate embeddings
            if progress_callback:
                progress_callback("Generating embeddings", 0.2)

            def embed_progress(current: int, total: int):
                if progress_callback:
                    # Progress from 0.2 to 0.8 during embedding
                    progress = 0.2 + (current / total) * 0.6
                    progress_callback(f"Embedding {current}/{total}", progress)

            chunks = await self.vectorize_chunks(chunks, embed_progress)

            # Store chunks in Firestore
            if progress_callback:
                progress_callback("Storing chunks", 0.85)

            chunk_docs = []
            for chunk in chunks:
                chunk_data = chunk.to_firestore()
                # Convert embedding to Firestore Vector
                if chunk.embedding:
                    chunk_data["embedding"] = Vector(chunk.embedding)
                chunk_data["id"] = chunk.id
                chunk_docs.append(chunk_data)

            count = await self.firestore.create_chunks_batch(chunk_docs)

            # Update document status and chunk count
            if progress_callback:
                progress_callback("Finalizing", 0.95)

            await self.firestore.update_document(
                document_id,
                {
                    "status": DocumentStatus.INDEXED.value,
                    "chunk_count": count,
                    "updated_at": datetime.utcnow().isoformat(),
                },
            )

            if progress_callback:
                progress_callback("Complete", 1.0)

            return count

        except Exception as e:
            await self.firestore.update_document(
                document_id,
                {
                    "status": DocumentStatus.ERROR.value,
                    "error_message": f"Indexing failed: {e}",
                    "updated_at": datetime.utcnow().isoformat(),
                },
            )
            raise

    async def reindex_document(
        self,
        document_id: str,
        chunks: list[Chunk],
    ) -> int:
        """
        Re-index a document (delete old chunks and create new ones).

        Args:
            document_id: Document ID.
            chunks: New chunks to index.

        Returns:
            Number of chunks indexed.
        """
        # Delete existing chunks
        await self.firestore.delete_chunks_by_document(document_id)

        # Index new chunks
        return await self.index_document(document_id, chunks)
