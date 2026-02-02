"""Agent context for ADK tool functions."""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from analyzer.models.evidence import Evidence

if TYPE_CHECKING:
    from analyzer.providers.base import EvidenceProvider
    from analyzer.providers.firestore_client import FirestoreClient
    from analyzer.services.document_service import DocumentService


@dataclass
class AgentToolContext:
    """
    Context object passed to ADK tool functions via ToolContext.state.

    This class holds references to services and tracks state across
    tool invocations within a single agent run.
    """

    # Required: RAG search provider
    evidence_provider: "EvidenceProvider"

    # Scope configuration (for auto-filtering)
    scope: str = "global"  # "document", "meeting", or "global"
    scope_id: str | None = None

    # Track evidences used during execution
    used_evidences: list[Evidence] = field(default_factory=list)

    # Optional services (for meeting agent)
    document_service: "DocumentService | None" = None
    firestore: "FirestoreClient | None" = None

    # Language preference
    language: str = "ja"

    # Meeting ID for meeting-scoped agents
    meeting_id: str | None = None

    def reset_evidences(self) -> None:
        """Reset used evidences for a new run."""
        self.used_evidences = []

    def get_unique_evidences(self, limit: int = 20) -> list[Evidence]:
        """Get deduplicated evidences sorted by relevance."""
        seen_chunks: set[str] = set()
        unique: list[Evidence] = []

        for ev in self.used_evidences:
            if ev.chunk_id not in seen_chunks:
                seen_chunks.add(ev.chunk_id)
                unique.append(ev)

        unique.sort(key=lambda x: x.relevance_score, reverse=True)
        return unique[:limit]
