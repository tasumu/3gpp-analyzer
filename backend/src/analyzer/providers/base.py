"""Abstract base class for evidence providers - RAG abstraction layer (P1-05)."""

from abc import ABC, abstractmethod

from analyzer.models.evidence import Evidence


class EvidenceProvider(ABC):
    """
    Abstract base class for evidence retrieval.

    This interface abstracts the RAG implementation details, allowing the analysis
    code to work with any backend (Firestore, Dify, LangGraph, Elastic, etc.).

    All implementations must support:
    - Semantic search by query
    - Document-specific retrieval
    - Filtering by meeting, contribution number, etc.
    """

    @abstractmethod
    async def search(
        self,
        query: str,
        filters: dict | None = None,
        top_k: int = 10,
    ) -> list[Evidence]:
        """
        Search for relevant evidence using semantic similarity.

        Args:
            query: The search query text.
            filters: Optional filters to narrow results. Supported keys:
                - meeting_id: Filter by meeting
                - contribution_number: Filter by specific contribution
                - clause_number: Filter by clause/section
            top_k: Maximum number of results to return.

        Returns:
            List of Evidence objects sorted by relevance (highest first).
        """
        pass

    @abstractmethod
    async def get_by_document(
        self,
        document_id: str,
        top_k: int = 50,
    ) -> list[Evidence]:
        """
        Get all evidence chunks from a specific document.

        Args:
            document_id: The document ID to retrieve evidence from.
            top_k: Maximum number of chunks to return.

        Returns:
            List of Evidence objects from the document.
        """
        pass

    @abstractmethod
    async def get_by_contribution(
        self,
        contribution_number: str,
        top_k: int = 50,
    ) -> list[Evidence]:
        """
        Get all evidence chunks by contribution number.

        Args:
            contribution_number: The 3GPP contribution number (e.g., 'S2-2401234').
            top_k: Maximum number of chunks to return.

        Returns:
            List of Evidence objects from the contribution.
        """
        pass
