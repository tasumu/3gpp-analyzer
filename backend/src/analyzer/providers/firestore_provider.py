"""Firestore implementation of EvidenceProvider."""

from google import genai

from analyzer.models.evidence import Evidence
from analyzer.providers.base import EvidenceProvider
from analyzer.providers.firestore_client import FirestoreClient


class FirestoreEvidenceProvider(EvidenceProvider):
    """
    Firestore-based implementation of EvidenceProvider.

    Uses Firestore Vector Search for semantic similarity and
    Google's text-embedding model for query embedding.
    """

    def __init__(
        self,
        firestore: FirestoreClient,
        project_id: str,
        location: str = "asia-northeast1",
        embedding_model: str = "gemini-embedding-001",
        embedding_dimensions: int = 768,
    ):
        """
        Initialize the provider.

        Args:
            firestore: FirestoreClient instance.
            project_id: GCP project ID for Vertex AI.
            location: GCP region for Vertex AI.
            embedding_model: Model name for query embedding.
            embedding_dimensions: Embedding vector dimensions.
        """
        self.firestore = firestore
        self.embedding_model = embedding_model
        self.embedding_dimensions = embedding_dimensions
        self._genai_client = genai.Client(
            vertexai=True,
            project=project_id,
            location=location,
            http_options=genai.types.HttpOptions(
                retry_options=genai.types.HttpRetryOptions(
                    attempts=3,
                    initial_delay=1.0,
                    max_delay=30.0,
                    exp_base=2.0,
                    http_status_codes=[429, 503],
                ),
            ),
        )

    async def _get_query_embedding(self, query: str) -> list[float]:
        """Generate embedding for a query string."""
        response = self._genai_client.models.embed_content(
            model=self.embedding_model,
            contents=query,
            config={"output_dimensionality": self.embedding_dimensions},
        )
        return response.embeddings[0].values

    async def search(
        self,
        query: str,
        filters: dict | None = None,
        top_k: int = 10,
    ) -> list[Evidence]:
        """Search for relevant evidence using semantic similarity."""
        # Generate query embedding
        query_embedding = await self._get_query_embedding(query)

        # Perform vector search
        results = await self.firestore.vector_search(
            query_embedding=query_embedding,
            filters=filters,
            top_k=top_k,
        )

        # Convert to Evidence objects
        # Note: Firestore vector search returns results sorted by similarity
        evidence_list = []
        for i, chunk_data in enumerate(results):
            # Use real cosine distance from Firestore if available
            vector_distance = chunk_data.pop("vector_distance", None)
            if vector_distance is not None:
                # COSINE distance: 0 = identical, 2 = opposite
                # Convert to similarity: 1.0 = identical, 0.0 = opposite
                relevance_score = max(0.0, min(1.0, 1.0 - (vector_distance / 2.0)))
            else:
                # Fallback: position-based score (for backward compatibility)
                relevance_score = 1.0 - (i / max(len(results), 1)) * 0.5
            evidence = Evidence.from_chunk(chunk_data, relevance_score)
            evidence_list.append(evidence)

        return evidence_list

    async def get_by_document(
        self,
        document_id: str,
        top_k: int = 50,
    ) -> list[Evidence]:
        """Get all evidence chunks from a specific document."""
        chunks = await self.firestore.get_chunks_by_document(document_id, limit=top_k)

        evidence_list = []
        for chunk_data in chunks:
            # For document retrieval, use a default relevance score
            evidence = Evidence.from_chunk(chunk_data, relevance_score=1.0)
            evidence_list.append(evidence)

        return evidence_list

    async def get_by_contribution(
        self,
        contribution_number: str,
        top_k: int = 50,
    ) -> list[Evidence]:
        """Get all evidence chunks by contribution number."""
        # Query chunks by contribution number
        query = (
            self.firestore.client.collection(FirestoreClient.CHUNKS_COLLECTION)
            .where("metadata.contribution_number", "==", contribution_number)
            .limit(top_k)
        )
        docs = query.stream()

        evidence_list = []
        for doc in docs:
            chunk_data = {"id": doc.id, **doc.to_dict()}
            evidence = Evidence.from_chunk(chunk_data, relevance_score=1.0)
            evidence_list.append(evidence)

        return evidence_list
