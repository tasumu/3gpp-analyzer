"""Tools for Agentic Search mode agents."""

import asyncio
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
    include_non_indexed: bool = False,
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
        include_non_indexed: If True, include documents that haven't been indexed yet
            (e.g., Agenda files not yet processed, TDoc_List .xlsx files).
            Use this when searching for meeting reference documents like Agendas.
            Default: False (only indexed documents are returned).
        page: Page number (1-indexed). Use for pagination when many documents exist.
        page_size: Number of documents per page. Default: 50. Max recommended: 100.
        tool_context: ADK tool context (injected automatically by ADK).

    Returns:
        List of documents with metadata including document_id, contribution_number,
        title, source, filename, document_type, status, and analyzable.
        Also includes pagination info.
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
        status_filter = None if include_non_indexed else DocumentStatus.INDEXED
        documents, total = await ctx.document_service.list_documents(
            meeting_id=meeting_id,
            status=status_filter,
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
                    "status": doc.status.value if doc.status else "unknown",
                    "analyzable": doc.analyzable,
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
    contribution_number: str | None = None,
    document_title: str | None = None,
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
        contribution_number: The contribution number of the document (e.g., 'S2-2401234').
            Pass this from list_meeting_documents_enhanced results for progress display.
        document_title: The title of the document.
            Pass this from list_meeting_documents_enhanced results for progress display.
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
        # Get document metadata for context, merging with passed params
        doc_data = None
        looked_up_cn = None
        if ctx.firestore:
            doc_data = await ctx.firestore.get_document(document_id)
            if doc_data:
                looked_up_cn = doc_data.get("contribution_number")
                if not document_title:
                    document_title = doc_data.get("title")

        effective_cn = looked_up_cn or contribution_number

        if not doc_data:
            return {"error": f"Document not found: {document_id}"}

        # Create a sub-agent for document investigation
        sub_agent = create_document_investigation_agent(
            document_id=document_id,
            contribution_number=effective_cn,
            language=ctx.language,
        )

        # Create a separate context for the sub-agent
        sub_context = AgentToolContext(
            evidence_provider=ctx.evidence_provider,
            scope="document",
            scope_id=document_id,
            language=ctx.language,
            filters={"document_id": document_id},
            firestore=ctx.firestore,
            storage=ctx.storage,
        )

        # Run the sub-agent with a shorter timeout than the main agent
        from analyzer.agents.adk_agents import SUB_AGENT_TIMEOUT_SECONDS

        runner = ADKAgentRunner(
            agent=sub_agent,
            agent_context=sub_context,
            timeout_seconds=SUB_AGENT_TIMEOUT_SECONDS,
        )
        analysis_text, evidences = await runner.run(
            user_input=investigation_query,
            user_id="investigation_sub_agent",
            session_id=str(uuid.uuid4()),
        )

        # Track evidences from sub-agent in the main context
        ctx.used_evidences.extend(evidences)

        return {
            "document_id": document_id,
            "contribution_number": effective_cn,
            "analysis": analysis_text,
            "evidence_count": len(evidences),
        }

    except asyncio.TimeoutError:
        logger.warning(f"Sub-agent timed out investigating document {document_id}")
        return {
            "document_id": document_id,
            "contribution_number": effective_cn,
            "analysis": "Investigation timed out. Use get_document_summary for a quicker overview.",
            "evidence_count": 0,
        }
    except Exception as e:
        logger.error(f"Error investigating document {document_id}: {e}")
        return {"error": str(e)}


async def list_meeting_attachments(
    meeting_id: str,
    tool_context: ToolContext = None,
) -> dict[str, Any]:
    """
    List user-uploaded supplementary files for a meeting.

    These are files uploaded by users to provide additional context,
    such as Agenda documents, TDoc lists, or other reference materials
    that may not be available through the standard document pipeline.

    Args:
        meeting_id: The meeting ID to list attachments for.
            Format: 'SA2#162' or 'RAN1#100'.
        tool_context: ADK tool context (injected automatically by ADK).

    Returns:
        List of attachments with metadata including attachment_id, filename,
        content_type, file_size_bytes, and uploaded_by.
    """
    ctx: AgentToolContext | None = get_current_agent_context()
    if not ctx and tool_context and tool_context.state:
        ctx = tool_context.state.get("agent_context")

    if not ctx or not ctx.attachment_service:
        return {"error": "Attachment service not available", "attachments": [], "total": 0}

    logger.info(f"Listing attachments for meeting: {meeting_id}")

    try:
        attachments = await ctx.attachment_service.list_by_meeting(meeting_id)
        results = [
            {
                "attachment_id": a.id,
                "filename": a.filename,
                "content_type": a.content_type,
                "file_size_bytes": a.file_size_bytes,
                "uploaded_by": a.uploaded_by,
            }
            for a in attachments
        ]
        return {"meeting_id": meeting_id, "attachments": results, "total": len(results)}

    except Exception as e:
        logger.error(f"Error listing attachments for meeting {meeting_id}: {e}")
        return {"error": str(e), "attachments": [], "total": 0}


async def read_attachment(
    attachment_id: str,
    tool_context: ToolContext = None,
) -> dict[str, Any]:
    """
    Read the extracted text content of a user-uploaded attachment.

    Use this to read the content of supplementary files like Agenda documents
    or TDoc lists that users have uploaded for additional context.

    Args:
        attachment_id: The attachment ID to read (from list_meeting_attachments results).
        tool_context: ADK tool context (injected automatically by ADK).

    Returns:
        Extracted text content of the attachment, with filename and truncation info.
    """
    ctx: AgentToolContext | None = get_current_agent_context()
    if not ctx and tool_context and tool_context.state:
        ctx = tool_context.state.get("agent_context")

    if not ctx or not ctx.attachment_service:
        return {"error": "Attachment service not available"}

    logger.info(f"Reading attachment: {attachment_id}")

    try:
        attachment, text = await ctx.attachment_service.get_extracted_text_with_metadata(
            attachment_id
        )
        if attachment is None or text is None:
            return {"error": f"Attachment not found: {attachment_id}"}

        filename = attachment.filename

        # Truncate very large content
        max_len = 50000
        truncated = len(text) > max_len
        return {
            "attachment_id": attachment_id,
            "filename": filename,
            "content": text[:max_len],
            "truncated": truncated,
            "total_length": len(text),
        }

    except Exception as e:
        logger.error(f"Error reading attachment {attachment_id}: {e}")
        return {"error": str(e)}
