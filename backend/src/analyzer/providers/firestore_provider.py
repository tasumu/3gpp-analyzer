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
        embedding_model: str = "text-embedding-004",
    ):
        """
        Initialize the provider.

        Args:
            firestore: FirestoreClient instance.
            embedding_model: Model name for query embedding.
        """
        self.firestore = firestore
        self.embedding_model = embedding_model
        self._genai_client = genai.Client()

    async def _get_query_embedding(self, query: str) -> list[float]:
        """Generate embedding for a query string."""
        response = self._genai_client.models.embed_content(
            model=self.embedding_model,
            contents=query,
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
            # Calculate relevance score (1.0 for most relevant, decreasing)
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
