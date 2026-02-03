"""Abstract base class for chunking strategies."""

from abc import ABC, abstractmethod
from pathlib import Path

from analyzer.models.chunk import Chunk


class ChunkingStrategy(ABC):
    """
    Abstract base class for document chunking strategies.

    Different strategies can be implemented:
    - HeadingBasedChunking: Split by document headings
    - FixedSizeChunking: Split by token count
    - SemanticChunking: Split by semantic boundaries
    """

    @abstractmethod
    async def chunk_document(
        self,
        file_path: Path | str,
        document_id: str,
        contribution_number: str | None,
        meeting_id: str | None = None,
    ) -> list[Chunk]:
        """
        Split a document into chunks.

        Args:
            file_path: Path to the normalized docx file.
            document_id: Parent document ID.
            contribution_number: 3GPP contribution number (may be None for non-contribution docs).
            meeting_id: Optional meeting identifier.

        Returns:
            List of Chunk objects with content and metadata.
        """
        pass

    @abstractmethod
    def estimate_token_count(self, text: str) -> int:
        """
        Estimate the token count for a text string.

        Args:
            text: Text to estimate.

        Returns:
            Estimated token count.
        """
        pass
