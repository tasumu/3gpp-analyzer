"""Document tools for ADK-based meeting analysis agents."""

import io
import logging
from typing import Any

from google.adk.tools import ToolContext

from analyzer.agents.context import AgentToolContext, get_current_agent_context

logger = logging.getLogger(__name__)


def _extract_docx_text(content: bytes) -> str:
    """Extract text from .docx bytes using python-docx.

    Returns paragraphs and tables formatted as markdown.
    """
    from docx import Document as DocxDocument

    doc = DocxDocument(io.BytesIO(content))
    parts: list[str] = []

    for para in doc.paragraphs:
        if para.text.strip():
            parts.append(para.text)

    for table in doc.tables:
        rows_text: list[str] = []
        for i, row in enumerate(table.rows):
            cells = [cell.text.strip() for cell in row.cells]
            rows_text.append("| " + " | ".join(cells) + " |")
            if i == 0:
                rows_text.append("| " + " | ".join(["---"] * len(cells)) + " |")
        if rows_text:
            parts.append("\n".join(rows_text))

    return "\n\n".join(parts)


async def list_meeting_documents(
    meeting_id: str,
    limit: int = 100,
    tool_context: ToolContext = None,
) -> dict[str, Any]:
    """
    List all indexed documents (contributions) in a specific meeting.

    Use this to get an overview of what documents are available for analysis.

    Args:
        meeting_id: The meeting ID to list documents for.
            Format: 'SA2#162' or 'RAN1#100'.
        limit: Maximum number of documents to return. Default: 100.
            Use a lower number if you only need a sample.
        tool_context: ADK tool context (injected automatically by ADK).

    Returns:
        List of documents with metadata including document_id, contribution_number,
        title, and source.
    """
    # Get context from contextvar (preferred) or ADK's state (fallback)
    ctx: AgentToolContext | None = get_current_agent_context()
    if not ctx and tool_context and tool_context.state:
        ctx = tool_context.state.get("agent_context")

    if not ctx or not ctx.document_service:
        return {"error": "Document service not available", "documents": [], "total": 0}

    logger.info(f"Listing documents for meeting: {meeting_id}")

    try:
        documents, total = await ctx.document_service.list_documents(
            meeting_id=meeting_id,
            status="indexed",
            page_size=limit,
        )

        results = []
        for doc in documents:
            results.append(
                {
                    "document_id": doc.id,
                    "contribution_number": doc.contribution_number,
                    "title": doc.title or "Untitled",
                    "source": doc.source or "Unknown",
                }
            )

        return {
            "meeting_id": meeting_id,
            "documents": results,
            "total": total,
            "returned": len(results),
        }

    except Exception as e:
        logger.error(f"Error listing documents for meeting {meeting_id}: {e}")
        return {"error": str(e), "documents": [], "total": 0}


async def get_document_summary(
    document_id: str,
    tool_context: ToolContext = None,
) -> dict[str, Any]:
    """
    Get the summary of a specific document.

    Returns the pre-computed analysis summary if available,
    or basic document metadata if not analyzed yet.

    Args:
        document_id: The document ID to get summary for.
            This is typically the contribution number.
        tool_context: ADK tool context (injected automatically by ADK).

    Returns:
        Document summary and metadata including contribution_number, title,
        source, status, and summary text.
    """
    # Get context from contextvar (preferred) or ADK's state (fallback)
    ctx: AgentToolContext | None = get_current_agent_context()
    if not ctx and tool_context and tool_context.state:
        ctx = tool_context.state.get("agent_context")

    if not ctx or not ctx.firestore:
        return {"error": "Firestore not available"}

    logger.info(f"Getting summary for document: {document_id}")

    try:
        # Get document metadata
        doc_data = await ctx.firestore.get_document(document_id)
        if not doc_data:
            return {"error": f"Document not found: {document_id}"}

        result = {
            "document_id": document_id,
            "contribution_number": doc_data.get("contribution_number", ""),
            "title": doc_data.get("title", "Untitled"),
            "source": doc_data.get("source", "Unknown"),
            "status": doc_data.get("status", "unknown"),
        }

        # Try to get analysis result
        try:
            query = (
                ctx.firestore.client.collection("analysis_results")
                .where("document_id", "==", document_id)
                .where("type", "==", "single")
                .where("status", "==", "completed")
                .order_by("created_at", direction="DESCENDING")
                .limit(1)
            )
            docs = list(query.stream())
            if docs:
                analysis_data = docs[0].to_dict()
                analysis_result = analysis_data.get("result", {})
                result["summary"] = analysis_result.get("summary", "No summary available")
                result["has_analysis"] = True
            else:
                result["summary"] = "No analysis available for this document"
                result["has_analysis"] = False
        except Exception as e:
            logger.warning(f"Error fetching analysis for {document_id}: {e}")
            result["summary"] = "Unable to retrieve analysis"
            result["has_analysis"] = False

        return result

    except Exception as e:
        logger.error(f"Error getting summary for document {document_id}: {e}")
        return {"error": str(e)}


async def get_document_content(
    document_id: str,
    max_chunks: int = 500,
    tool_context: ToolContext = None,
) -> dict[str, Any]:
    """
    Get the full content of a specific document.

    For indexed documents, returns all chunks organized by sections.
    For non-indexed documents with a .docx file in GCS, falls back to
    direct text extraction from the original file.

    Args:
        document_id: The document ID to get content for.
        max_chunks: Maximum number of chunks to return. Default: 500.
        tool_context: ADK tool context (injected automatically by ADK).

    Returns:
        Document content organized by sections with clause numbers,
        titles, content text, and page numbers.
    """
    # Get context from contextvar (preferred) or ADK's state (fallback)
    ctx: AgentToolContext | None = get_current_agent_context()
    if not ctx and tool_context and tool_context.state:
        ctx = tool_context.state.get("agent_context")

    if not ctx:
        return {"error": "Agent context not initialized", "sections": [], "total_chunks": 0}

    logger.info(f"Getting content for document: {document_id}")

    try:
        evidences = await ctx.evidence_provider.get_by_document(
            document_id=document_id,
            top_k=max_chunks,
        )

        # Fallback: if no chunks exist, try reading the original file from GCS
        if not evidences and ctx.storage and ctx.firestore:
            return await _get_document_content_from_gcs(ctx, document_id)

        # Organize by clause
        content_sections = []
        for ev in evidences:
            content_sections.append(
                {
                    "clause": ev.clause_number or "Unknown",
                    "title": ev.clause_title or "",
                    "content": ev.content,
                    "page": ev.page_number,
                }
            )

        # Track these as used evidences
        ctx.used_evidences.extend(evidences)

        return {
            "document_id": document_id,
            "sections": content_sections,
            "total_chunks": len(content_sections),
        }

    except Exception as e:
        logger.error(f"Error getting content for document {document_id}: {e}")
        return {"error": str(e), "sections": [], "total_chunks": 0}


async def _get_document_content_from_gcs(ctx: AgentToolContext, document_id: str) -> dict[str, Any]:
    """Fallback: read document content directly from GCS for non-indexed documents."""
    doc_data = await ctx.firestore.get_document(document_id)
    if not doc_data:
        return {
            "error": f"Document not found: {document_id}",
            "sections": [],
            "total_chunks": 0,
        }

    source_file = doc_data.get("source_file", {})
    gcs_path = source_file.get("gcs_normalized_path") or source_file.get("gcs_original_path")
    filename = source_file.get("filename", "")

    if not gcs_path:
        return {
            "error": "Document file not available in GCS (not yet downloaded)",
            "sections": [],
            "total_chunks": 0,
        }

    if not filename.lower().endswith(".docx"):
        return {
            "error": f"Direct reading not supported for {filename} (only .docx)",
            "sections": [],
            "total_chunks": 0,
        }

    logger.info(f"Reading non-indexed document from GCS: {gcs_path}")
    content_bytes = await ctx.storage.download_bytes(gcs_path)
    text = _extract_docx_text(content_bytes)

    return {
        "document_id": document_id,
        "sections": [{"clause": "Full Document", "title": "", "content": text, "page": None}],
        "total_chunks": 1,
        "source": "gcs_fallback",
    }
