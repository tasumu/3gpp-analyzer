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
    MultiMeetingSummary,
    MultiMeetingSummaryStreamEvent,
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
    MULTI_MEETING_SUMMARIES_COLLECTION = "multi_meeting_summaries"
    MAX_CONCURRENT_SUMMARIES = 10  # Limit parallel requests

    def __init__(
        self,
        document_service: DocumentService,
        analysis_service: AnalysisService,
        firestore: FirestoreClient,
        project_id: str,
        location: str = "asia-northeast1",
        pro_model: str = "gemini-3-pro-preview",
        pro_model_location: str = "global",
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
            pro_model_location: Location for pro model (e.g., "global" for gemini-3).
            strategy_version: Version identifier for caching.
        """
        self.document_service = document_service
        self.analysis_service = analysis_service
        self.firestore = firestore
        self.project_id = project_id
        self.location = location
        self.pro_model = pro_model
        self.pro_model_location = pro_model_location
        self.strategy_version = strategy_version

        # Initialize GenAI client for overall report generation (uses pro_model_location)
        self._pro_client = genai.Client(
            vertexai=True,
            project=project_id,
            location=pro_model_location,
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

        # Get all indexed documents
        documents, _ = await self.document_service.list_documents(
            meeting_id=meeting_id,
            status=DocumentStatus.INDEXED,
            page_size=1000,
        )

        if not documents:
            raise ValueError(f"No indexed documents found for meeting: {meeting_id}")

        logger.info(f"Found {len(documents)} indexed documents for {meeting_id}")

        # Summarize each document (uses document_summaries cache internally)
        # force=True will bypass the individual document cache
        valid_summaries = await self._summarize_documents(
            documents, analysis_prompt, language, force=force
        )
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
            custom_prompt=analysis_prompt,
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
                summary = await self._summarize_document(doc, analysis_prompt, language, force)
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
            custom_prompt=analysis_prompt,
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
        force: bool = False,
    ) -> DocumentSummary:
        """
        Summarize a single document using the unified analysis service.

        Uses the shared document summary cache for consistency between
        meeting summarization and individual document analysis.

        Args:
            document: Document to summarize.
            custom_prompt: Custom prompt for analysis.
            language: Output language.
            force: Force re-analysis even if cached.
        """
        return await self.analysis_service.generate_summary(
            document_id=document.id,
            language=language,
            custom_prompt=custom_prompt,
            force=force,
        )

    async def _summarize_documents(
        self,
        documents: list[Document],
        custom_prompt: str | None,
        language: str,
        force: bool = False,
    ) -> list[DocumentSummary]:
        """
        Summarize multiple documents with concurrency limit.

        Args:
            documents: List of documents to summarize.
            custom_prompt: Custom prompt for analysis.
            language: Output language.
            force: Force re-analysis even if cached.

        Returns:
            List of valid DocumentSummary objects (failed ones are filtered out).
        """
        if not documents:
            return []

        semaphore = asyncio.Semaphore(self.MAX_CONCURRENT_SUMMARIES)

        async def summarize_with_limit(doc: Document) -> DocumentSummary:
            async with semaphore:
                return await self._summarize_document(doc, custom_prompt, language, force)

        results = await asyncio.gather(
            *[summarize_with_limit(doc) for doc in documents],
            return_exceptions=True,
        )

        valid_summaries: list[DocumentSummary] = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Failed to summarize {documents[i].id}: {result}")
            else:
                valid_summaries.append(result)

        return valid_summaries

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

    async def summarize_meetings(
        self,
        meeting_ids: list[str],
        analysis_prompt: str | None = None,
        report_prompt: str | None = None,
        language: str = "ja",
        user_id: str | None = None,
        force: bool = False,
    ) -> MultiMeetingSummary:
        """
        Summarize multiple meetings together with integrated analysis.

        Args:
            meeting_ids: List of meeting IDs (e.g., ['SA2#162', 'SA2#163']).
            analysis_prompt: Custom prompt for individual document analysis.
            report_prompt: Custom prompt for integrated report generation.
            language: Output language (ja or en).
            user_id: User ID who initiated.
            force: Force re-analysis even if cached.

        Returns:
            MultiMeetingSummary with individual meeting summaries and integrated report.

        Raises:
            ValueError: If less than 2 meeting IDs provided.
        """
        if len(meeting_ids) < 2:
            raise ValueError("At least 2 meeting IDs required for multi-meeting summary")

        logger.info(f"Starting multi-meeting summarization: {meeting_ids}")

        # Check cache first (unless force=True)
        if not force:
            cached = await self._get_cached_multi_summary(meeting_ids, analysis_prompt, language)
            if cached:
                logger.info("Returning cached multi-meeting summary")
                return cached

        # Summarize each meeting individually (in parallel, with cache reuse)
        individual_summaries = await asyncio.gather(
            *[
                self.summarize_meeting(
                    meeting_id=mid,
                    analysis_prompt=analysis_prompt,
                    report_prompt=report_prompt,
                    language=language,
                    user_id=user_id,
                    force=force,
                )
                for mid in meeting_ids
            ],
            return_exceptions=True,
        )

        valid_summaries: list[MeetingSummary] = []
        for i, result in enumerate(individual_summaries):
            if isinstance(result, Exception):
                logger.error(f"Failed to summarize meeting {meeting_ids[i]}: {result}")
            else:
                valid_summaries.append(result)

        if not valid_summaries:
            raise ValueError("Failed to summarize any meeting")

        logger.info(f"Successfully summarized {len(valid_summaries)} meetings")

        # Generate integrated report
        integrated_report, all_key_topics = await self._generate_integrated_report(
            meeting_ids=[s.meeting_id for s in valid_summaries],
            meeting_summaries=valid_summaries,
            report_prompt=report_prompt,
            language=language,
        )

        # Create result
        result = MultiMeetingSummary(
            id=str(uuid.uuid4()),
            meeting_ids=[s.meeting_id for s in valid_summaries],
            custom_prompt=analysis_prompt,
            individual_meeting_summaries=valid_summaries,
            integrated_report=integrated_report,
            all_key_topics=all_key_topics,
            language=language,
            created_at=datetime.utcnow(),
            created_by=user_id,
        )

        # Save to Firestore
        await self._save_multi_summary(result)

        return result

    async def summarize_meetings_stream(
        self,
        meeting_ids: list[str],
        analysis_prompt: str | None = None,
        report_prompt: str | None = None,
        language: str = "ja",
        user_id: str | None = None,
        force: bool = False,
    ) -> AsyncGenerator[MultiMeetingSummaryStreamEvent, None]:
        """
        Summarize multiple meetings with streaming progress updates.

        Args:
            meeting_ids: List of meeting IDs (e.g., ['SA2#162', 'SA2#163']).
            analysis_prompt: Custom prompt for individual document analysis.
            report_prompt: Custom prompt for integrated report generation.
            language: Output language (ja or en).
            user_id: User ID who initiated.
            force: Force re-analysis even if cached.

        Yields events as meetings are processed.
        """
        if len(meeting_ids) < 2:
            yield MultiMeetingSummaryStreamEvent(
                type="error",
                error="At least 2 meeting IDs required for multi-meeting summary",
            )
            return

        logger.info(f"Starting streaming multi-meeting summarization: {meeting_ids}")

        # Check cache first (unless force=True)
        if not force:
            cached = await self._get_cached_multi_summary(meeting_ids, analysis_prompt, language)
            if cached:
                logger.info("Returning cached multi-meeting summary")
                yield MultiMeetingSummaryStreamEvent(
                    type="done",
                    result=cached,
                )
                return

        valid_summaries: list[MeetingSummary] = []

        # Process each meeting sequentially (to provide streaming feedback)
        for i, meeting_id in enumerate(meeting_ids):
            yield MultiMeetingSummaryStreamEvent(
                type="meeting_start",
                meeting_id=meeting_id,
                progress={
                    "current_meeting": i + 1,
                    "total_meetings": len(meeting_ids),
                },
            )

            try:
                # Use streaming version for real-time progress
                async for event in self.summarize_meeting_stream(
                    meeting_id=meeting_id,
                    analysis_prompt=analysis_prompt,
                    report_prompt=report_prompt,
                    language=language,
                    user_id=user_id,
                    force=force,
                ):
                    if event.type == "progress":
                        yield MultiMeetingSummaryStreamEvent(
                            type="meeting_progress",
                            meeting_id=meeting_id,
                            progress={
                                "current_meeting": i + 1,
                                "total_meetings": len(meeting_ids),
                                **event.progress,
                            },
                        )
                    elif event.type == "done":
                        valid_summaries.append(event.result)
                        yield MultiMeetingSummaryStreamEvent(
                            type="meeting_complete",
                            meeting_id=meeting_id,
                            meeting_summary=event.result,
                        )
            except Exception as e:
                logger.error(f"Failed to summarize meeting {meeting_id}: {e}")
                yield MultiMeetingSummaryStreamEvent(
                    type="error",
                    meeting_id=meeting_id,
                    error=f"Failed to summarize {meeting_id}: {str(e)}",
                )

        if not valid_summaries:
            yield MultiMeetingSummaryStreamEvent(
                type="error",
                error="Failed to summarize any meeting",
            )
            return

        # Generate integrated report
        yield MultiMeetingSummaryStreamEvent(
            type="meeting_progress",
            progress={
                "stage": "generating_integrated_report",
                "current_meeting": len(meeting_ids),
                "total_meetings": len(meeting_ids),
            },
        )

        integrated_report, all_key_topics = await self._generate_integrated_report(
            meeting_ids=[s.meeting_id for s in valid_summaries],
            meeting_summaries=valid_summaries,
            report_prompt=report_prompt,
            language=language,
        )

        yield MultiMeetingSummaryStreamEvent(
            type="integrated_report",
            integrated_report=integrated_report,
            all_key_topics=all_key_topics,
        )

        # Create and save result
        result = MultiMeetingSummary(
            id=str(uuid.uuid4()),
            meeting_ids=[s.meeting_id for s in valid_summaries],
            custom_prompt=analysis_prompt,
            individual_meeting_summaries=valid_summaries,
            integrated_report=integrated_report,
            all_key_topics=all_key_topics,
            language=language,
            created_at=datetime.utcnow(),
            created_by=user_id,
        )

        await self._save_multi_summary(result)

        yield MultiMeetingSummaryStreamEvent(
            type="done",
            result=result,
        )

    async def _generate_integrated_report(
        self,
        meeting_ids: list[str],
        meeting_summaries: list[MeetingSummary],
        report_prompt: str | None,
        language: str,
    ) -> tuple[str, list[str]]:
        """
        Generate integrated report from multiple meeting summaries.

        Uses Gemini Pro to synthesize insights across meetings.
        """
        if not meeting_summaries:
            return "No meetings available for analysis.", []

        # Prepare input from individual meeting reports
        meetings_text = "\n\n".join(
            [
                f"## {s.meeting_id}\n"
                f"Total Documents: {s.document_count}\n"
                f"Key Topics: {', '.join(s.key_topics) if s.key_topics else 'N/A'}\n\n"
                f"Meeting Summary:\n{s.overall_report}"
                for s in meeting_summaries
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
Create an integrated analysis report across multiple meetings.

Meetings Analyzed: {", ".join(meeting_ids)}
Total Meetings: {len(meeting_summaries)}

Individual Meeting Reports:
{meetings_text}

Instructions:
1. Provide an executive summary of key developments across all meetings
2. Identify common themes and trends across meetings
3. Highlight significant changes or evolution of topics between meetings
4. Note any differences in focus or approach between meetings
5. Identify notable contributions that span multiple meetings
6. {lang_instruction}
{custom_instruction}

Structure your report with clear sections. Focus on synthesis and cross-meeting insights, \
not just summarizing each meeting.
At the end, provide a JSON block with all key topics from all meetings: \
{{"key_topics": ["topic1", "topic2", ...]}}"""

        response = self._pro_client.models.generate_content(
            model=self.pro_model,
            contents=[types.Content(role="user", parts=[types.Part.from_text(text=prompt)])],
        )

        report_text = response.text or "Integrated report generation failed."

        # Try to extract key topics from the response
        all_key_topics: list[str] = []
        try:
            # Look for JSON block at the end
            json_match = re.search(r'\{[^{}]*"key_topics"\s*:\s*\[[^\]]*\][^{}]*\}', report_text)
            if json_match:
                topics_data = json.loads(json_match.group())
                all_key_topics = topics_data.get("key_topics", [])
                # Remove JSON from report
                report_text = report_text[: json_match.start()].strip()
        except Exception as e:
            logger.warning(f"Failed to extract key topics: {e}")

        # If extraction failed, collect from individual meetings
        if not all_key_topics:
            seen = set()
            for summary in meeting_summaries:
                for topic in summary.key_topics:
                    if topic not in seen:
                        all_key_topics.append(topic)
                        seen.add(topic)

        return report_text, all_key_topics

    async def _get_cached_multi_summary(
        self,
        meeting_ids: list[str],
        custom_prompt: str | None,
        language: str,
    ) -> MultiMeetingSummary | None:
        """Get cached multi-meeting summary if available."""
        try:
            # Sort meeting IDs for consistent cache key
            sorted_ids = sorted(meeting_ids)

            query = (
                self.firestore.client.collection(self.MULTI_MEETING_SUMMARIES_COLLECTION)
                .where("meeting_ids", "==", sorted_ids)
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
                return MultiMeetingSummary.from_firestore(docs[0].id, docs[0].to_dict())
        except Exception as e:
            logger.warning(f"Error fetching cached multi-meeting summary: {e}")
        return None

    async def _save_multi_summary(self, summary: MultiMeetingSummary) -> None:
        """Save multi-meeting summary to Firestore."""
        try:
            doc_ref = self.firestore.client.collection(
                self.MULTI_MEETING_SUMMARIES_COLLECTION
            ).document(summary.id)
            doc_ref.set(summary.to_firestore())
            logger.info(f"Saved multi-meeting summary: {summary.id}")
        except Exception as e:
            logger.error(f"Error saving multi-meeting summary: {e}")
