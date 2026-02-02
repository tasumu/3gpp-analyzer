"""Meeting Report Agent for generating comprehensive meeting reports (P3-06)."""

import logging
from typing import Any

from google.genai import types

from analyzer.agents.base import BaseAgent
from analyzer.agents.tools.document_tool import create_document_tools
from analyzer.agents.tools.search_tool import create_search_tool
from analyzer.providers.base import EvidenceProvider
from analyzer.providers.firestore_client import FirestoreClient
from analyzer.services.document_service import DocumentService

logger = logging.getLogger(__name__)


class MeetingReportAgent(BaseAgent):
    """
    Agent for generating comprehensive meeting reports.

    Uses multiple tools to:
    - Search for specific information across meeting documents
    - List documents in the meeting
    - Retrieve document summaries and content
    """

    def __init__(
        self,
        evidence_provider: EvidenceProvider,
        document_service: DocumentService,
        firestore: FirestoreClient,
        project_id: str,
        meeting_id: str,
        language: str = "ja",
        location: str = "asia-northeast1",
        model: str = "gemini-2.5-pro",
    ):
        """
        Initialize MeetingReportAgent.

        Args:
            evidence_provider: Provider for RAG search operations.
            document_service: Service for document operations.
            firestore: Firestore client for analysis results.
            project_id: GCP project ID.
            meeting_id: Target meeting ID.
            language: Response language (ja or en).
            location: GCP region for Vertex AI.
            model: LLM model name.
        """
        super().__init__(
            evidence_provider=evidence_provider,
            project_id=project_id,
            location=location,
            model=model,
        )
        self.document_service = document_service
        self.firestore = firestore
        self.meeting_id = meeting_id
        self.language = language

    def get_tools(self) -> list[types.Tool]:
        """Return tools for meeting analysis."""
        return [
            create_search_tool(),
            create_document_tools(),
        ]

    def get_system_prompt(self, context: dict | None = None) -> str:
        """
        Generate system prompt for meeting report generation.

        Args:
            context: Optional context containing summary data.
        """
        context = context or {}
        custom_prompt = context.get("custom_prompt", "")

        # Language instructions
        lang_instructions = {
            "ja": (
                "レポートは日本語で作成してください。"
                "技術用語（3GPP用語、仕様書番号、条項番号など）は英語のまま使用してください。"
            ),
            "en": (
                "Write the report in English. "
                "Use standard 3GPP terminology."
            ),
        }
        lang_text = lang_instructions.get(self.language, lang_instructions["ja"])

        custom_instruction = ""
        if custom_prompt:
            custom_instruction = f"""
## Custom Analysis Focus
The user has requested the following specific focus for this report:
"{custom_prompt}"

Incorporate this perspective throughout your analysis.
"""

        return f"""You are an expert 3GPP standardization analyst \
creating a comprehensive meeting report.

## Meeting: {self.meeting_id}

## Your Task
Analyze the meeting's contributions and create a comprehensive report covering:
1. **Overview**: High-level summary of the meeting's focus and outcomes
2. **Key Topics**: Major themes and discussion points
3. **Notable Contributions**: Documents that are particularly important or controversial
4. **Technical Trends**: Emerging patterns or directions
5. **Potential Conflicts**: Competing proposals or disagreements
{custom_instruction}

## Available Tools

1. **search_evidence**: Search for specific topics across all meeting documents
   - Use for: Finding information about specific technical topics
   - Always search with meeting_id='{self.meeting_id}'

2. **list_meeting_documents**: Get the list of all contributions in the meeting
   - Use for: Getting an overview of submissions

3. **get_document_summary**: Get the summary of a specific contribution
   - Use for: Understanding individual document proposals

4. **get_document_content**: Get the full content of a document
   - Use for: Deep-diving into specific documents

## Guidelines

- Start by listing the meeting documents to understand the scope
- Use search_evidence to explore specific topics of interest
- Cross-reference multiple documents when analyzing trends
- Cite specific contributions when making claims
- Be objective and balanced in your analysis

## Output Format

{lang_text}

Structure your analysis clearly with sections and bullet points.
Always include contribution numbers when referencing documents: [S2-2401234]
"""

    async def execute_tool(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        """
        Execute tool with meeting-aware handling.

        Args:
            name: Tool name.
            args: Tool arguments.

        Returns:
            Tool execution result.
        """
        if name == "search_evidence":
            # Always inject meeting_id for this agent
            args["meeting_id"] = self.meeting_id
            return await super().execute_tool(name, args)

        elif name == "list_meeting_documents":
            return await self._list_meeting_documents(args)

        elif name == "get_document_summary":
            return await self._get_document_summary(args)

        elif name == "get_document_content":
            return await self._get_document_content(args)

        return await super().execute_tool(name, args)

    async def _list_meeting_documents(self, args: dict[str, Any]) -> dict[str, Any]:
        """List documents in the meeting."""
        meeting_id = args.get("meeting_id", self.meeting_id)
        limit = args.get("limit", 100)

        logger.info(f"Listing documents for meeting: {meeting_id}")

        documents, total = await self.document_service.list_documents(
            meeting_id=meeting_id,
            status="indexed",
            page_size=limit,
        )

        results = []
        for doc in documents:
            results.append({
                "document_id": doc.id,
                "contribution_number": doc.contribution_number,
                "title": doc.title or "Untitled",
                "source": doc.source or "Unknown",
            })

        return {
            "meeting_id": meeting_id,
            "documents": results,
            "total": total,
            "returned": len(results),
        }

    async def _get_document_summary(self, args: dict[str, Any]) -> dict[str, Any]:
        """Get summary of a specific document."""
        document_id = args.get("document_id", "")

        logger.info(f"Getting summary for document: {document_id}")

        # Get document metadata
        doc_data = await self.firestore.get_document(document_id)
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
                self.firestore.client.collection("analysis_results")
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

    async def _get_document_content(self, args: dict[str, Any]) -> dict[str, Any]:
        """Get full content of a document."""
        document_id = args.get("document_id", "")
        max_chunks = args.get("max_chunks", 50)

        logger.info(f"Getting content for document: {document_id}")

        evidences = await self.evidence_provider.get_by_document(
            document_id=document_id,
            top_k=max_chunks,
        )

        # Organize by clause
        content_sections = []
        for ev in evidences:
            content_sections.append({
                "clause": ev.clause_number or "Unknown",
                "title": ev.clause_title or "",
                "content": ev.content,
                "page": ev.page_number,
            })

        # Track these as used evidences
        self._used_evidences.extend(evidences)

        return {
            "document_id": document_id,
            "sections": content_sections,
            "total_chunks": len(content_sections),
        }
