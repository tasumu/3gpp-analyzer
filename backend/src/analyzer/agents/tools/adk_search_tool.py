"""Search tool for ADK-based agents."""

import logging
from typing import Any

from google.adk.tools import ToolContext

from analyzer.agents.context import AgentToolContext, get_current_agent_context

logger = logging.getLogger(__name__)


async def search_evidence(
    query: str,
    meeting_id: str | None = None,
    contribution_number: str | None = None,
    document_id: str | None = None,
    top_k: int = 10,
    tool_context: ToolContext = None,
) -> dict[str, Any]:
    """
    Search for relevant evidence from 3GPP contribution documents.

    Use this tool to find information related to a specific question or topic.
    Returns excerpts from documents with citation information.

    Args:
        query: The search query. Be specific and include relevant technical terms.
            Example: 'UE power saving requirements for 5G NR'
        meeting_id: Optional filter for a specific meeting.
            Format: 'SA2#162' or 'RAN1#100'.
            Use this to narrow search to a particular meeting's documents.
        contribution_number: Optional filter for a specific contribution.
            Format: 'S2-2401234'.
            Use this when searching within a known document.
        document_id: Optional filter by document ID.
            Use when you have the exact document identifier.
        top_k: Number of results to return. Default: 10.
            Increase for broader searches, decrease for focused queries.
        tool_context: ADK tool context (injected automatically by ADK).

    Returns:
        Search results with evidence list and count.
    """
    # Get our custom context from contextvar (preferred) or ADK's state (fallback)
    ctx: AgentToolContext | None = get_current_agent_context()
    if not ctx and tool_context and tool_context.state:
        ctx = tool_context.state.get("agent_context")

    if not ctx:
        return {"error": "Agent context not initialized", "results": [], "count": 0}

    # Build filters
    filters: dict[str, Any] = {}

    # Merge ctx.filters first (contains additional filters like meeting.id__in for multi-meeting Q&A)
    if ctx.filters:
        filters.update(ctx.filters)

    # Apply scope filters (auto-inject based on agent configuration)
    # Don't override meeting.id__in if it's already set from ctx.filters
    if ctx.scope_id:
        if ctx.scope == "meeting" and "meeting.id__in" not in filters:
            filters["meeting_id"] = ctx.scope_id
        elif ctx.scope == "document":
            filters["document_id"] = ctx.scope_id

    # Apply meeting_id from context if set (for meeting-scoped agents)
    # Don't override meeting.id__in if it's already set
    if ctx.meeting_id and "meeting.id__in" not in filters:
        filters["meeting_id"] = ctx.meeting_id

    # Override with explicit filters if provided
    if meeting_id:
        filters["meeting_id"] = meeting_id
    if contribution_number:
        filters["contribution_number"] = contribution_number
    if document_id:
        filters["document_id"] = document_id

    logger.info(
        f"Executing search_evidence: query='{query[:50]}...', filters={filters}, top_k={top_k}"
    )

    try:
        evidences = await ctx.evidence_provider.search(
            query=query,
            filters=filters if filters else None,
            top_k=top_k,
        )

        # Track used evidences
        ctx.used_evidences.extend(evidences)

        # Handle no results case
        if len(evidences) == 0:
            return {
                "results": [],
                "count": 0,
                "query": query,
                "message": (
                    "No relevant documents found for this query. Consider: "
                    "1) Using different technical terms or synonyms, "
                    "2) Trying a broader search scope, "
                    "3) Searching for specific specification numbers if known."
                ),
            }

        # Convert to serializable format
        results = []
        for ev in evidences:
            results.append(
                {
                    "chunk_id": ev.chunk_id,
                    "contribution_number": ev.contribution_number,
                    "content": ev.content[:500] + "..." if len(ev.content) > 500 else ev.content,
                    "clause_number": ev.clause_number,
                    "clause_title": ev.clause_title,
                    "page_number": ev.page_number,
                    "relevance_score": ev.relevance_score,
                }
            )

        return {
            "results": results,
            "count": len(results),
            "query": query,
        }

    except Exception as e:
        logger.error(f"Error in search_evidence: {e}")
        return {"error": str(e), "results": [], "count": 0}
