"""Q&A Agent for RAG-based question answering (P3-05)."""

import logging
from enum import Enum

from google.genai import types

from analyzer.agents.base import BaseAgent
from analyzer.agents.tools.search_tool import create_search_tool
from analyzer.providers.base import EvidenceProvider

logger = logging.getLogger(__name__)


class QAScope(str, Enum):
    """Scope for Q&A searches."""

    DOCUMENT = "document"  # Single document
    MEETING = "meeting"  # All documents in a meeting
    GLOBAL = "global"  # All indexed documents


class QAAgent(BaseAgent):
    """
    Q&A Agent for answering questions about 3GPP documents.

    Supports three scopes:
    - DOCUMENT: Questions about a specific document
    - MEETING: Questions across all documents in a meeting
    - GLOBAL: Questions across all indexed documents
    """

    def __init__(
        self,
        evidence_provider: EvidenceProvider,
        project_id: str,
        scope: QAScope = QAScope.GLOBAL,
        scope_id: str | None = None,
        language: str = "ja",
        location: str = "asia-northeast1",
        model: str = "gemini-2.5-pro",
    ):
        """
        Initialize QAAgent.

        Args:
            evidence_provider: Provider for RAG search operations.
            project_id: GCP project ID.
            scope: Search scope (document, meeting, or global).
            scope_id: ID for the scope (document_id or meeting_id).
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
        self.scope = scope
        self.scope_id = scope_id
        self.language = language

    def get_tools(self) -> list[types.Tool]:
        """Return search tool for Q&A."""
        return [create_search_tool()]

    def get_system_prompt(self, context: dict | None = None) -> str:
        """
        Generate system prompt based on scope.

        Args:
            context: Optional context with additional parameters.
        """
        # Scope-specific instructions
        scope_instructions = {
            QAScope.DOCUMENT: (
                f"You are answering questions about a specific 3GPP contribution document "
                f"(ID: {self.scope_id}). "
                f"Focus your search and answers on this document only."
            ),
            QAScope.MEETING: (
                f"You are answering questions about 3GPP meeting {self.scope_id}. "
                f"Your search scope includes all contributions submitted to this meeting. "
                f"When searching, always include the meeting_id filter."
            ),
            QAScope.GLOBAL: (
                "You are answering questions about 3GPP standardization documents. "
                "You have access to all indexed contributions across multiple meetings. "
                "Search broadly to find relevant information."
            ),
        }

        # Language instructions
        lang_instructions = {
            "ja": (
                "回答は日本語で行ってください。"
                "技術用語（3GPP用語、仕様書番号、条項番号など）は英語のまま使用してください。"
            ),
            "en": (
                "Respond in English. "
                "Use standard 3GPP terminology."
            ),
        }

        scope_text = scope_instructions.get(self.scope, scope_instructions[QAScope.GLOBAL])
        lang_text = lang_instructions.get(self.language, lang_instructions["ja"])

        return f"""You are an expert analyst for 3GPP standardization documents.

{scope_text}

## Instructions

1. Use the search_evidence tool to find relevant information from the documents
2. Always cite your sources with contribution numbers and clause numbers
3. If you cannot find sufficient information, clearly state that
4. Be precise and technical in your answers
5. If the question is ambiguous, make reasonable assumptions and state them

## Search Guidelines

- Use specific technical terms in your search queries
- If initial search doesn't yield results, try alternative phrasings
- For complex questions, break them down into multiple searches
{self._get_scope_search_instruction()}

## Response Format

{lang_text}

Structure your response as:
1. Direct answer to the question
2. Supporting evidence with citations
3. Any caveats or limitations in the available information

Example citation format: [S2-2401234, Clause 5.2.1]
"""

    def _get_scope_search_instruction(self) -> str:
        """Get scope-specific search instruction for the prompt."""
        if self.scope == QAScope.MEETING and self.scope_id:
            return f"- Always include meeting_id='{self.scope_id}' in your searches"
        elif self.scope == QAScope.DOCUMENT and self.scope_id:
            return f"- Always include document_id='{self.scope_id}' in your searches"
        return ""

    async def execute_tool(self, name: str, args: dict) -> dict:
        """
        Execute tool with scope-aware filtering.

        Automatically applies scope filters to search queries.
        """
        if name == "search_evidence":
            # Inject scope filters
            if self.scope == QAScope.DOCUMENT and self.scope_id:
                args["document_id"] = self.scope_id
            elif self.scope == QAScope.MEETING and self.scope_id:
                args["meeting_id"] = self.scope_id
            # GLOBAL scope: no additional filters

        return await super().execute_tool(name, args)
