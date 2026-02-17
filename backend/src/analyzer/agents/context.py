"""Agent context for ADK tool functions."""

import contextvars
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from analyzer.models.evidence import Evidence

if TYPE_CHECKING:
    from analyzer.providers.base import EvidenceProvider
    from analyzer.providers.firestore_client import FirestoreClient
    from analyzer.providers.storage_client import StorageClient
    from analyzer.services.attachment_service import AttachmentService
    from analyzer.services.document_service import DocumentService

# Context variable for storing AgentToolContext during agent execution.
# This avoids pickle issues with InMemorySessionService by keeping unpicklable
# objects (like Firestore clients) out of session state.
_agent_context_var: contextvars.ContextVar["AgentToolContext | None"] = contextvars.ContextVar(
    "agent_context", default=None
)


def get_current_agent_context() -> "AgentToolContext | None":
    """Get the current AgentToolContext from contextvar."""
    return _agent_context_var.get()


def set_current_agent_context(ctx: "AgentToolContext | None") -> contextvars.Token:
    """Set the current AgentToolContext in contextvar. Returns a token for reset."""
    return _agent_context_var.set(ctx)


def reset_agent_context(token: contextvars.Token) -> None:
    """Restore the previous AgentToolContext using a token from set_current_agent_context.

    This is safe for nested sub-agent calls: each level saves a token and
    restores the parent context when done.
    """
    _agent_context_var.reset(token)


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

    # Additional metadata filters for RAG search
    filters: dict | None = None

    # Track evidences used during execution
    used_evidences: list[Evidence] = field(default_factory=list)

    # Optional services (for meeting agent)
    document_service: "DocumentService | None" = None
    firestore: "FirestoreClient | None" = None
    storage: "StorageClient | None" = None
    attachment_service: "AttachmentService | None" = None

    # Language preference
    language: str = "ja"

    # Meeting ID for meeting-scoped agents
    meeting_id: str | None = None

    def reset_evidences(self) -> None:
        """Reset used evidences for a new run."""
        self.used_evidences = []

    def get_unique_evidences(self, limit: int = 50) -> list[Evidence]:
        """Get deduplicated evidences sorted by relevance."""
        seen_chunks: set[str] = set()
        unique: list[Evidence] = []

        for ev in self.used_evidences:
            if ev.chunk_id not in seen_chunks:
                seen_chunks.add(ev.chunk_id)
                unique.append(ev)

        unique.sort(key=lambda x: x.relevance_score, reverse=True)
        return unique[:limit]
