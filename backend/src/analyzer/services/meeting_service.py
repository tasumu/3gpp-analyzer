"""Meeting Service for summarizing meeting contributions (P3-02)."""

import asyncio
import json
import logging
import re
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime

from google import genai
from google.genai import types

from analyzer.models.document import Document, DocumentStatus
from analyzer.models.meeting_analysis import (
    DocumentSummary,
    MeetingSummary,
    MeetingSummaryStreamEvent,
)
from analyzer.providers.firestore_client import FirestoreClient
from analyzer.services.analysis_service import AnalysisService
from analyzer.services.document_service import DocumentService

logger = logging.getLogger(__name__)


class MeetingService:
    """
    Service for summarizing meeting contributions.

    Implements P3-02: summarize_meeting()
    - Retrieves all indexed documents for a meeting
    - Summarizes each document individually (lightweight model)
    - Generates overall meeting report (high-performance model)
    """

    MEETING_SUMMARIES_COLLECTION = "meeting_summaries"
    MAX_CONCURRENT_SUMMARIES = 10  # Limit parallel requests

    def __init__(
        self,
        document_service: DocumentService,
        analysis_service: AnalysisService,
        firestore: FirestoreClient,
        project_id: str,
        location: str = "asia-northeast1",
        pro_model: str = "gemini-3-pro-preview",
        strategy_version: str = "v1",
    ):
        """
        Initialize MeetingService.

        Args:
            document_service: Service for document operations.
            analysis_service: Service for individual document analysis (and summarization).
            firestore: Firestore client for persistence.
            project_id: GCP project ID.
            location: GCP region for Vertex AI.
            pro_model: High-performance model for overall reports.
            strategy_version: Version identifier for caching.
        """
        self.document_service = document_service
        self.analysis_service = analysis_service
        self.firestore = firestore
        self.project_id = project_id
        self.location = location
        self.pro_model = pro_model
        self.strategy_version = strategy_version

        # Initialize GenAI client for overall report generation
        self._pro_client = genai.Client(
            vertexai=True,
            project=project_id,
            location=location,
        )

    async def summarize_meeting(
        self,
        meeting_id: str,
        analysis_prompt: str | None = None,
        report_prompt: str | None = None,
        language: str = "ja",
        user_id: str | None = None,
        force: bool = False,
    ) -> MeetingSummary:
        """
        Summarize all contributions in a meeting.

        Args:
            meeting_id: Meeting ID (e.g., 'SA2#162').
            analysis_prompt: Custom prompt for individual document analysis.
            report_prompt: Custom prompt for overall report generation.
            language: Output language (ja or en).
            user_id: User ID who initiated.
            force: Force re-analysis even if cached.

        Returns:
            MeetingSummary with individual and overall summaries.

        Raises:
            ValueError: If no indexed documents found.
        """
        logger.info(f"Starting meeting summarization: {meeting_id}")

        # Check cache unless forced
        if not force:
            cached = await self._get_cached_summary(meeting_id, report_prompt, language)
            if cached:
                logger.info(f"Returning cached summary for meeting {meeting_id}")
                return cached

        # Get all indexed documents
        documents, total = await self.document_service.list_documents(
            meeting_id=meeting_id,
            status=DocumentStatus.INDEXED,
            page_size=1000,
        )

        if not documents:
            raise ValueError(f"No indexed documents found for meeting: {meeting_id}")

        logger.info(f"Found {len(documents)} indexed documents for {meeting_id}")

        # Summarize each document (with concurrency limit)
        semaphore = asyncio.Semaphore(self.MAX_CONCURRENT_SUMMARIES)

        async def summarize_with_limit(doc: Document) -> DocumentSummary:
            async with semaphore:
                return await self._summarize_document(doc, analysis_prompt, language)

        individual_summaries = await asyncio.gather(
            *[summarize_with_limit(doc) for doc in documents],
            return_exceptions=True,
        )

        # Filter out failed summaries
        valid_summaries: list[DocumentSummary] = []
        for i, result in enumerate(individual_summaries):
            if isinstance(result, Exception):
                logger.error(f"Failed to summarize {documents[i].id}: {result}")
            else:
                valid_summaries.append(result)

        logger.info(f"Successfully summarized {len(valid_summaries)} documents")

        # Generate overall report
        overall_report, key_topics = await self._generate_overall_report(
            meeting_id=meeting_id,
            summaries=valid_summaries,
            report_prompt=report_prompt,
            language=language,
        )

        # Create result
        result = MeetingSummary(
            id=str(uuid.uuid4()),
            meeting_id=meeting_id,
            custom_prompt=report_prompt,
            individual_summaries=valid_summaries,
            overall_report=overall_report,
            key_topics=key_topics,
            document_count=len(valid_summaries),
            language=language,
            created_at=datetime.utcnow(),
            created_by=user_id,
        )

        # Save to Firestore
        await self._save_summary(result)

        return result

    async def summarize_meeting_stream(
        self,
        meeting_id: str,
        analysis_prompt: str | None = None,
        report_prompt: str | None = None,
        language: str = "ja",
        user_id: str | None = None,
        force: bool = False,
    ) -> AsyncGenerator[MeetingSummaryStreamEvent, None]:
        """
        Summarize meeting with streaming progress updates.

        Args:
            meeting_id: Meeting ID (e.g., 'SA2#162').
            analysis_prompt: Custom prompt for individual document analysis.
            report_prompt: Custom prompt for overall report generation.
            language: Output language (ja or en).
            user_id: User ID who initiated.
            force: Force re-analysis even if cached.

        Yields events as documents are processed.
        """
        logger.info(f"Starting streaming meeting summarization: {meeting_id}")

        # Get all indexed documents
        documents, total = await self.document_service.list_documents(
            meeting_id=meeting_id,
            status=DocumentStatus.INDEXED,
            page_size=1000,
        )

        if not documents:
            yield MeetingSummaryStreamEvent(
                type="error",
                error=f"No indexed documents found for meeting: {meeting_id}",
            )
            return

        yield MeetingSummaryStreamEvent(
            type="progress",
            progress={
                "stage": "starting",
                "total_documents": len(documents),
                "processed": 0,
            },
        )

        # Summarize each document
        valid_summaries: list[DocumentSummary] = []
        processed = 0

        for doc in documents:
            try:
                summary = await self._summarize_document(doc, analysis_prompt, language)
                valid_summaries.append(summary)
                processed += 1

                yield MeetingSummaryStreamEvent(
                    type="document_summary",
                    document_summary=summary,
                    progress={
                        "stage": "summarizing",
                        "total_documents": len(documents),
                        "processed": processed,
                        "current_document": doc.contribution_number,
                    },
                )
            except Exception as e:
                logger.error(f"Failed to summarize {doc.id}: {e}")
                processed += 1
                yield MeetingSummaryStreamEvent(
                    type="progress",
                    progress={
                        "stage": "summarizing",
                        "total_documents": len(documents),
                        "processed": processed,
                        "error": f"Failed to process {doc.contribution_number}",
                    },
                )

        # Generate overall report
        yield MeetingSummaryStreamEvent(
            type="progress",
            progress={
                "stage": "generating_report",
                "total_documents": len(documents),
                "processed": processed,
            },
        )

        overall_report, key_topics = await self._generate_overall_report(
            meeting_id=meeting_id,
            summaries=valid_summaries,
            report_prompt=report_prompt,
            language=language,
        )

        yield MeetingSummaryStreamEvent(
            type="overall_report",
            overall_report=overall_report,
        )

        # Create and save result
        result = MeetingSummary(
            id=str(uuid.uuid4()),
            meeting_id=meeting_id,
            custom_prompt=report_prompt,
            individual_summaries=valid_summaries,
            overall_report=overall_report,
            key_topics=key_topics,
            document_count=len(valid_summaries),
            language=language,
            created_at=datetime.utcnow(),
            created_by=user_id,
        )

        await self._save_summary(result)

        yield MeetingSummaryStreamEvent(
            type="done",
            result=result,
        )

    async def _summarize_document(
        self,
        document: Document,
        custom_prompt: str | None,
        language: str,
    ) -> DocumentSummary:
        """
        Summarize a single document using the unified analysis service.

        Uses the shared document summary cache for consistency between
        meeting summarization and individual document analysis.
        """
        return await self.analysis_service.generate_summary(
            document_id=document.id,
            language=language,
            custom_prompt=custom_prompt,
            force=False,  # Use cache when available
        )

    async def _generate_overall_report(
        self,
        meeting_id: str,
        summaries: list[DocumentSummary],
        report_prompt: str | None,
        language: str,
    ) -> tuple[str, list[str]]:
        """
        Generate overall meeting report from individual summaries.

        Uses the high-performance model for synthesis.
        """
        if not summaries:
            return "No documents available for analysis.", []

        # Prepare summary input
        summaries_text = "\n\n".join(
            [
                f"### {s.contribution_number}: {s.title}\n"
                f"Source: {s.source or 'Unknown'}\n"
                f"Summary: {s.summary}\n"
                f"Key Points: {', '.join(s.key_points) if s.key_points else 'N/A'}"
                for s in summaries
            ]
        )

        lang_instruction = (
            "Write the report in Japanese. Keep technical terms in English."
            if language == "ja"
            else "Write the report in English."
        )

        custom_instruction = ""
        if report_prompt:
            custom_instruction = f"\n\nSpecial focus requested: {report_prompt}"

        prompt = f"""You are an expert 3GPP standardization analyst. \
Create a comprehensive meeting report.

Meeting: {meeting_id}
Total Contributions: {len(summaries)}

Individual Document Summaries:
{summaries_text}

Instructions:
1. Provide an executive summary of the meeting
2. Identify and discuss key themes/topics
3. Highlight notable or important contributions
4. Note any potential areas of debate or controversy
5. {lang_instruction}
{custom_instruction}

Structure your report with clear sections and bullet points where appropriate.
At the end, provide a JSON block with key topics: {{"key_topics": ["topic1", "topic2", ...]}}"""

        response = self._pro_client.models.generate_content(
            model=self.pro_model,
            contents=[types.Content(role="user", parts=[types.Part.from_text(text=prompt)])],
        )

        report_text = response.text or "Report generation failed."

        # Try to extract key topics from the response
        key_topics: list[str] = []
        try:
            # Look for JSON block at the end
            json_match = re.search(r'\{[^{}]*"key_topics"\s*:\s*\[[^\]]*\][^{}]*\}', report_text)
            if json_match:
                topics_data = json.loads(json_match.group())
                key_topics = topics_data.get("key_topics", [])
                # Remove JSON from report
                report_text = report_text[: json_match.start()].strip()
        except Exception as e:
            logger.warning(f"Failed to extract key topics: {e}")

        return report_text, key_topics

    async def _get_cached_summary(
        self,
        meeting_id: str,
        custom_prompt: str | None,
        language: str,
    ) -> MeetingSummary | None:
        """Get cached meeting summary if available."""
        try:
            query = (
                self.firestore.client.collection(self.MEETING_SUMMARIES_COLLECTION)
                .where("meeting_id", "==", meeting_id)
                .where("language", "==", language)
            )

            # Custom prompt matching
            if custom_prompt:
                query = query.where("custom_prompt", "==", custom_prompt)
            else:
                query = query.where("custom_prompt", "==", None)

            query = query.order_by("created_at", direction="DESCENDING").limit(1)

            docs = list(query.stream())
            if docs:
                return MeetingSummary.from_firestore(docs[0].id, docs[0].to_dict())
        except Exception as e:
            logger.warning(f"Error fetching cached summary: {e}")
        return None

    async def _save_summary(self, summary: MeetingSummary) -> None:
        """Save meeting summary to Firestore."""
        try:
            doc_ref = self.firestore.client.collection(self.MEETING_SUMMARIES_COLLECTION).document(
                summary.id
            )
            doc_ref.set(summary.to_firestore())
            logger.info(f"Saved meeting summary: {summary.id}")
        except Exception as e:
            logger.error(f"Error saving meeting summary: {e}")

    async def get_summary(self, summary_id: str) -> MeetingSummary | None:
        """Get a meeting summary by ID."""
        try:
            doc_ref = self.firestore.client.collection(self.MEETING_SUMMARIES_COLLECTION).document(
                summary_id
            )
            doc = doc_ref.get()
            if doc.exists:
                return MeetingSummary.from_firestore(doc.id, doc.to_dict())
        except Exception as e:
            logger.error(f"Error fetching meeting summary: {e}")
        return None

    async def list_summaries(
        self,
        meeting_id: str | None = None,
        user_id: str | None = None,
        limit: int = 50,
    ) -> list[MeetingSummary]:
        """List meeting summaries with optional filters."""
        try:
            query = self.firestore.client.collection(self.MEETING_SUMMARIES_COLLECTION)

            if meeting_id:
                query = query.where("meeting_id", "==", meeting_id)
            if user_id:
                query = query.where("created_by", "==", user_id)

            query = query.order_by("created_at", direction="DESCENDING").limit(limit)

            results = []
            for doc in query.stream():
                results.append(MeetingSummary.from_firestore(doc.id, doc.to_dict()))
            return results
        except Exception as e:
            logger.error(f"Error listing meeting summaries: {e}")
            return []
