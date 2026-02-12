"""Tools for Agentic Search mode agents."""

import logging
import uuid
from typing import Any

from google.adk.tools import ToolContext

from analyzer.agents.context import AgentToolContext, get_current_agent_context
from analyzer.models.document import DocumentStatus

logger = logging.getLogger(__name__)


async def list_meeting_documents_enhanced(
    meeting_id: str,
    search_text: str | None = None,
    page: int = 1,
    page_size: int = 50,
    tool_context: ToolContext = None,
) -> dict[str, Any]:
    """
    List documents in a meeting with optional title/filename keyword search.

    Use this to discover what documents are available in a meeting.
    You can search by keywords in the title or filename to find relevant contributions.

    Args:
        meeting_id: The meeting ID to list documents for.
            Format: 'SA2#162' or 'RAN1#100'.
        search_text: Optional keyword to search in document titles and filenames.
            Use this to find documents about specific topics.
            Example: 'power saving', 'handover', 'PDU session'.
        page: Page number (1-indexed). Use for pagination when many documents exist.
        page_size: Number of documents per page. Default: 50. Max recommended: 100.
        tool_context: ADK tool context (injected automatically by ADK).

    Returns:
        List of documents with metadata including document_id, contribution_number,
        title, source, filename, and document_type. Also includes pagination info.
    """
    ctx: AgentToolContext | None = get_current_agent_context()
    if not ctx and tool_context and tool_context.state:
        ctx = tool_context.state.get("agent_context")

    if not ctx or not ctx.document_service:
        return {"error": "Document service not available", "documents": [], "total": 0}

    logger.info(
        f"Listing documents for meeting: {meeting_id}, "
        f"search_text={search_text}, page={page}, page_size={page_size}"
    )

    try:
        documents, total = await ctx.document_service.list_documents(
            meeting_id=meeting_id,
            status=DocumentStatus.INDEXED,
            search_text=search_text,
            page=page,
            page_size=page_size,
        )

        results = []
        for doc in documents:
            results.append(
                {
                    "document_id": doc.id,
                    "contribution_number": doc.contribution_number,
                    "title": doc.title or "Untitled",
                    "source": doc.source or "Unknown",
                    "filename": doc.source_file.filename if doc.source_file else "",
                    "document_type": doc.document_type.value if doc.document_type else "unknown",
                }
            )

        return {
            "meeting_id": meeting_id,
            "documents": results,
            "total": total,
            "page": page,
            "page_size": page_size,
            "returned": len(results),
        }

    except Exception as e:
        logger.error(f"Error listing documents for meeting {meeting_id}: {e}")
        return {"error": str(e), "documents": [], "total": 0}


async def investigate_document(
    document_id: str,
    investigation_query: str,
    tool_context: ToolContext = None,
) -> dict[str, Any]:
    """
    Deeply investigate a specific document to answer a question.

    This tool delegates to a sub-agent that reads the document content
    and analyzes it in context of the investigation query. Use this when
    you need detailed understanding of a specific document.

    This is more thorough than get_document_summary but takes longer.
    Use it for documents you've identified as particularly relevant.

    Args:
        document_id: The document ID to investigate.
        investigation_query: What to look for in this document.
            Be specific about what information you need.
            Example: 'What changes does this document propose to DRX parameters?'
        tool_context: ADK tool context (injected automatically by ADK).

    Returns:
        Analysis of the document focused on the investigation query,
        including the contribution number and evidence count.
    """
    from analyzer.agents.adk_agents import ADKAgentRunner, create_document_investigation_agent

    ctx: AgentToolContext | None = get_current_agent_context()
    if not ctx and tool_context and tool_context.state:
        ctx = tool_context.state.get("agent_context")

    if not ctx:
        return {"error": "Agent context not initialized"}

    logger.info(f"Investigating document {document_id}: query='{investigation_query[:50]}...'")

    try:
        # Get document metadata for context
        doc_data = None
        contribution_number = None
        if ctx.firestore:
            doc_data = await ctx.firestore.get_document(document_id)
            if doc_data:
                contribution_number = doc_data.get("contribution_number")

        if not doc_data:
            return {"error": f"Document not found: {document_id}"}

        # Create a sub-agent for document investigation
        sub_agent = create_document_investigation_agent(
            document_id=document_id,
            contribution_number=contribution_number,
            language=ctx.language,
        )

        # Create a separate context for the sub-agent
        sub_context = AgentToolContext(
            evidence_provider=ctx.evidence_provider,
            scope="document",
            scope_id=document_id,
            language=ctx.language,
            filters={"document_id": document_id},
        )

        # Run the sub-agent
        runner = ADKAgentRunner(agent=sub_agent, agent_context=sub_context)
        analysis_text, evidences = await runner.run(
            user_input=investigation_query,
            user_id="investigation_sub_agent",
            session_id=str(uuid.uuid4()),
        )

        # Track evidences from sub-agent in the main context
        ctx.used_evidences.extend(evidences)

        return {
            "document_id": document_id,
            "contribution_number": contribution_number,
            "analysis": analysis_text,
            "evidence_count": len(evidences),
        }

    except Exception as e:
        logger.error(f"Error investigating document {document_id}: {e}")
        return {"error": str(e)}
