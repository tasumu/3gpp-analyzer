"""Analysis service for document analysis and summarization."""

import hashlib
import json
import logging
from datetime import datetime
from typing import Any

from google import genai
from google.genai import types

from analyzer.models.analysis import CustomAnalysisResult
from analyzer.models.document import Document
from analyzer.models.evidence import Evidence
from analyzer.models.meeting_analysis import DocumentSummary
from analyzer.providers.base import EvidenceProvider
from analyzer.providers.firestore_client import FirestoreClient
from analyzer.services.prompts import (
    CUSTOM_ANALYSIS_USER_PROMPT,
    get_custom_analysis_system_prompt,
)

logger = logging.getLogger(__name__)


class AnalysisService:
    """
    Orchestrates document analysis using LLM and EvidenceProvider.

    Implements:
    - generate_summary(): Unified document summary generation
    - analyze_custom(): Custom prompt analysis (stateless, no persistence)
    """

    DOCUMENT_SUMMARIES_COLLECTION = "document_summaries"

    def __init__(
        self,
        evidence_provider: EvidenceProvider,
        firestore: FirestoreClient,
        project_id: str,
        location: str = "asia-northeast1",
        model: str = "gemini-3-flash-preview",
        strategy_version: str = "v1",
    ):
        """
        Initialize AnalysisService.

        Args:
            evidence_provider: EvidenceProvider for retrieving document chunks.
            firestore: FirestoreClient for summary cache.
            project_id: GCP project ID.
            location: GCP region for Vertex AI.
            model: LLM model name.
            strategy_version: Version identifier for analysis strategy.
        """
        self.evidence_provider = evidence_provider
        self.firestore = firestore
        self.strategy_version = strategy_version
        self.model = model

        # Initialize GenAI client
        self._genai_client = genai.Client(
            vertexai=True,
            project=project_id,
            location=location,
        )

    async def generate_summary(
        self,
        document_id: str,
        language: str = "ja",
        custom_prompt: str | None = None,
        force: bool = False,
        user_id: str | None = None,
    ) -> DocumentSummary:
        """
        Generate a document summary in the unified DocumentSummary format.

        This is the standard method for document analysis, used by both
        individual document pages and meeting summarization.

        Args:
            document_id: Document ID to analyze.
            language: Output language (ja or en).
            custom_prompt: Optional custom focus for the summary.
            force: Force re-generation even if cached.
            user_id: User ID who initiated the request.

        Returns:
            DocumentSummary with summary and key_points.

        Raises:
            ValueError: If document not found or not indexed.
        """
        # Check cache unless forced
        if not force:
            cached = await self.get_cached_summary(document_id, language, custom_prompt)
            if cached:
                logger.info(f"Returning cached summary for document {document_id}")
                cached.from_cache = True
                return cached

        # Get document metadata
        doc_data = await self.firestore.get_document(document_id)
        if not doc_data:
            raise ValueError(f"Document not found: {document_id}")

        if doc_data.get("status") != "indexed":
            raise ValueError(f"Document is not indexed: {document_id}")

        # Extract document info
        contribution_number = doc_data.get("contribution_number") or ""
        title = doc_data.get("title") or "Unknown"
        source = doc_data.get("source")

        # Get document content via evidence provider
        evidences = await self.evidence_provider.get_by_document(document_id, top_k=30)

        if not evidences:
            return DocumentSummary(
                document_id=document_id,
                contribution_number=contribution_number,
                title=title,
                source=source,
                summary="No content available for this document.",
                key_points=[],
                from_cache=False,
            )

        # Build prompt
        content_text = self._format_evidence_for_summary(evidences)
        prompt = self._build_summary_prompt(
            contribution_number=contribution_number,
            title=title,
            source=source,
            content=content_text,
            custom_prompt=custom_prompt,
            language=language,
        )

        # Call LLM with JSON output
        response = self._genai_client.models.generate_content(
            model=self.model,
            contents=[types.Content(role="user", parts=[types.Part.from_text(text=prompt)])],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema={
                    "type": "object",
                    "properties": {
                        "summary": {"type": "string"},
                        "key_points": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                    "required": ["summary", "key_points"],
                },
            ),
        )

        try:
            result_data = json.loads(response.text)
            summary = DocumentSummary(
                document_id=document_id,
                contribution_number=contribution_number,
                title=title,
                source=source,
                summary=result_data.get("summary", ""),
                key_points=result_data.get("key_points", []),
                from_cache=False,
            )
        except Exception as e:
            logger.warning(f"Failed to parse summary response: {e}")
            summary = DocumentSummary(
                document_id=document_id,
                contribution_number=contribution_number,
                title=title,
                source=source,
                summary=response.text[:500] if response.text else "Summary generation failed",
                key_points=[],
                from_cache=False,
            )

        # Save to cache
        await self.save_summary(summary, language, custom_prompt)

        return summary

    async def generate_summary_from_document(
        self,
        document: Document,
        language: str = "ja",
        custom_prompt: str | None = None,
        force: bool = False,
    ) -> DocumentSummary:
        """
        Generate summary from a Document object (convenience method for MeetingService).

        Args:
            document: Document object with metadata.
            language: Output language.
            custom_prompt: Optional custom focus.
            force: Force re-generation.

        Returns:
            DocumentSummary.
        """
        return await self.generate_summary(
            document_id=document.id,
            language=language,
            custom_prompt=custom_prompt,
            force=force,
        )

    async def get_cached_summary(
        self,
        document_id: str,
        language: str = "ja",
        custom_prompt: str | None = None,
    ) -> DocumentSummary | None:
        """
        Get cached document summary from unified cache.

        Args:
            document_id: Document ID.
            language: Output language.
            custom_prompt: Custom prompt (if any).

        Returns:
            DocumentSummary if found, None otherwise.
        """
        try:
            cache_key = self._make_summary_cache_key(document_id, language, custom_prompt)
            doc_ref = self.firestore.client.collection(self.DOCUMENT_SUMMARIES_COLLECTION).document(
                cache_key
            )
            doc = doc_ref.get()
            if doc.exists:
                data = doc.to_dict()
                return DocumentSummary(
                    document_id=data.get("document_id", document_id),
                    contribution_number=data.get("contribution_number", ""),
                    title=data.get("title", ""),
                    source=data.get("source"),
                    summary=data.get("summary", ""),
                    key_points=data.get("key_points", []),
                    from_cache=True,
                )
        except Exception as e:
            logger.warning(f"Error fetching cached summary: {e}")
        return None

    async def save_summary(
        self,
        summary: DocumentSummary,
        language: str,
        custom_prompt: str | None = None,
    ) -> None:
        """
        Save document summary to unified cache.

        Args:
            summary: DocumentSummary to save.
            language: Output language.
            custom_prompt: Custom prompt (if any).
        """
        try:
            cache_key = self._make_summary_cache_key(summary.document_id, language, custom_prompt)
            doc_ref = self.firestore.client.collection(self.DOCUMENT_SUMMARIES_COLLECTION).document(
                cache_key
            )
            data: dict[str, Any] = {
                "document_id": summary.document_id,
                "contribution_number": summary.contribution_number,
                "title": summary.title,
                "source": summary.source,
                "summary": summary.summary,
                "key_points": summary.key_points,
                "language": language,
                "custom_prompt": custom_prompt,
                "strategy_version": self.strategy_version,
                "created_at": datetime.utcnow(),
            }
            doc_ref.set(data)
            logger.info(f"Saved document summary: {cache_key}")
        except Exception as e:
            logger.error(f"Error saving document summary: {e}")

    def _make_summary_cache_key(
        self,
        document_id: str,
        language: str,
        custom_prompt: str | None,
    ) -> str:
        """Generate cache key for document summary."""
        prompt_hash = ""
        if custom_prompt:
            prompt_hash = hashlib.md5(custom_prompt.encode()).hexdigest()[:8]
        if prompt_hash:
            return f"{document_id}_{language}_{prompt_hash}"
        return f"{document_id}_{language}"

    def _format_evidence_for_summary(self, evidences: list[Evidence]) -> str:
        """Format evidence chunks for summary prompt."""
        sections = []
        for ev in evidences:
            section = f"[{ev.clause_number or 'Content'}]"
            if ev.clause_title:
                section += f" {ev.clause_title}"
            section += f"\n{ev.content}"
            sections.append(section)
        return "\n\n".join(sections)

    def _build_summary_prompt(
        self,
        contribution_number: str,
        title: str,
        source: str | None,
        content: str,
        custom_prompt: str | None,
        language: str,
    ) -> str:
        """Build prompt for document summarization."""
        lang_instruction = (
            "Respond in Japanese. Keep technical terms in English."
            if language == "ja"
            else "Respond in English."
        )

        custom_instruction = ""
        if custom_prompt:
            custom_instruction = f"\n\nSpecial focus: {custom_prompt}"

        return f"""Summarize this 3GPP contribution document.

Document Information:
- Contribution Number: {contribution_number}
- Title: {title or "Unknown"}
- Source: {source or "Unknown"}

Document Content:
{content}

Instructions:
1. Provide a concise summary (2-4 sentences)
2. Extract 3-5 key points
3. {lang_instruction}
{custom_instruction}

Return JSON with "summary" and "key_points" fields."""

    async def analyze_custom(
        self,
        document_id: str,
        custom_prompt: str,
        prompt_id: str | None = None,
        language: str = "ja",
        user_id: str | None = None,
    ) -> CustomAnalysisResult:
        """
        Analyze a document with a custom user prompt.

        Results are returned directly without persistence.

        Args:
            document_id: Document ID to analyze.
            custom_prompt: User's custom prompt/question.
            prompt_id: ID of saved prompt if using one.
            language: Output language ("ja" or "en").
            user_id: User ID who initiated the analysis.

        Returns:
            CustomAnalysisResult with answer and evidences.
        """
        # Get document metadata
        doc_data = await self.firestore.get_document(document_id)
        if not doc_data:
            raise ValueError(f"Document not found: {document_id}")

        if doc_data.get("status") != "indexed":
            raise ValueError(f"Document is not indexed: {document_id}")

        contribution_number = doc_data.get("contribution_number") or ""

        # Get all evidence from the document
        evidences = await self.evidence_provider.get_by_document(document_id, top_k=100)
        if not evidences:
            raise ValueError(f"No content found for document: {document_id}")

        # Build content for LLM
        evidence_content = self._format_evidence_for_prompt(evidences)

        # Get document info
        title = doc_data.get("title", "Unknown")
        meeting_id = doc_data.get("meeting", {}).get("id", "")
        meeting_name = doc_data.get("meeting", {}).get("name", meeting_id)
        source = doc_data.get("source", "Unknown")

        # Build prompts
        system_prompt = get_custom_analysis_system_prompt(language)
        user_prompt = CUSTOM_ANALYSIS_USER_PROMPT.format(
            contribution_number=contribution_number,
            title=title,
            meeting=meeting_name,
            source=source,
            custom_prompt=custom_prompt,
            evidence_content=evidence_content,
        )

        # Call LLM (non-structured output for custom analysis)
        response = self._genai_client.models.generate_content(
            model=self.model,
            contents=[
                types.Content(
                    role="user",
                    parts=[types.Part(text=f"{system_prompt}\n\n{user_prompt}")],
                ),
            ],
        )

        return CustomAnalysisResult(
            prompt_text=custom_prompt,
            prompt_id=prompt_id,
            answer=response.text,
            evidences=self._select_supporting_evidence(evidences)[:5],
        )

    def _format_evidence_for_prompt(self, evidences: list[Evidence]) -> str:
        """Format evidence list for LLM prompt."""
        sections = []
        current_clause = None

        for evidence in evidences:
            clause = evidence.clause_number or "General"
            if clause != current_clause:
                current_clause = clause
                sections.append(f"\n### Section: {clause}")
                if evidence.clause_title:
                    sections.append(f"**{evidence.clause_title}**")

            page_info = f" (Page {evidence.page_number})" if evidence.page_number else ""
            sections.append(f"{evidence.content}{page_info}")

        return "\n".join(sections)

    def _select_supporting_evidence(
        self,
        all_evidence: list[Evidence],
    ) -> list[Evidence]:
        """Select most relevant evidence to include in result."""
        return all_evidence[:10]
