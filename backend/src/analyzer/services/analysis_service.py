"""Analysis service for P2-01 (analyze_single) and P2-04 (persistence)."""

import logging
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime

from google import genai
from google.genai import types

from analyzer.models.analysis import (
    AnalysisOptions,
    AnalysisResult,
    AnalysisStreamEvent,
    SingleAnalysis,
)
from analyzer.models.evidence import Evidence
from analyzer.providers.base import EvidenceProvider
from analyzer.providers.firestore_client import FirestoreClient
from analyzer.providers.storage_client import StorageClient
from analyzer.services.prompts import (
    SINGLE_ANALYSIS_SYSTEM_PROMPT,
    SINGLE_ANALYSIS_USER_PROMPT,
)

logger = logging.getLogger(__name__)


class AnalysisService:
    """
    Orchestrates document analysis using LLM and EvidenceProvider.

    Implements:
    - analyze_single(): Single document analysis (P2-01)
    - Result caching and retrieval (P2-04)
    """

    ANALYSIS_RESULTS_COLLECTION = "analysis_results"

    def __init__(
        self,
        evidence_provider: EvidenceProvider,
        firestore: FirestoreClient,
        storage: StorageClient,
        project_id: str,
        location: str = "asia-northeast1",
        model: str = "gemini-3-flash-preview",
        strategy_version: str = "v1",
    ):
        """
        Initialize AnalysisService.

        Args:
            evidence_provider: EvidenceProvider for retrieving document chunks.
            firestore: FirestoreClient for persistence.
            storage: StorageClient for review sheet storage.
            project_id: GCP project ID.
            location: GCP region for Vertex AI.
            model: LLM model name.
            strategy_version: Version identifier for analysis strategy.
        """
        self.evidence_provider = evidence_provider
        self.firestore = firestore
        self.storage = storage
        self.strategy_version = strategy_version
        self.model = model

        # Initialize GenAI client
        self._genai_client = genai.Client(
            vertexai=True,
            project=project_id,
            location=location,
        )

    async def analyze_single(
        self,
        document_id: str,
        options: AnalysisOptions | None = None,
        force: bool = False,
        user_id: str | None = None,
    ) -> AnalysisResult:
        """
        Analyze a single document.

        Args:
            document_id: Document ID to analyze.
            options: Analysis options.
            force: Force re-analysis even if cached.
            user_id: User ID who initiated the analysis.

        Returns:
            AnalysisResult with completed analysis.
        """
        options = options or AnalysisOptions()

        # Check cache unless forced
        if not force:
            cached = await self.get_cached_result(document_id, "single")
            if cached and cached.status == "completed":
                logger.info(f"Returning cached analysis for document {document_id}")
                return cached

        # Get document metadata
        doc_data = await self.firestore.get_document(document_id)
        if not doc_data:
            raise ValueError(f"Document not found: {document_id}")

        if doc_data.get("status") != "indexed":
            raise ValueError(f"Document is not indexed: {document_id}")

        # Create analysis record
        analysis_id = str(uuid.uuid4())
        contribution_number = doc_data.get("contribution_number", "")

        analysis = AnalysisResult(
            id=analysis_id,
            document_id=document_id,
            document_ids=[document_id],
            contribution_number=contribution_number,
            type="single",
            status="processing",
            strategy_version=self.strategy_version,
            options=options,
            created_by=user_id,
        )

        # Save initial state
        await self._save_analysis(analysis)

        try:
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

            # Build prompt
            user_prompt = SINGLE_ANALYSIS_USER_PROMPT.format(
                contribution_number=contribution_number,
                title=title,
                meeting=meeting_name,
                source=source,
                evidence_content=evidence_content,
            )

            # Call LLM with structured output
            result = await self._call_llm_structured(
                system_prompt=SINGLE_ANALYSIS_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                output_schema=SingleAnalysis,
            )

            # Add evidence references to the result
            result.evidences = self._select_supporting_evidence(evidences, result)

            # Update analysis with result
            analysis.result = result
            analysis.status = "completed"
            analysis.completed_at = datetime.utcnow()

        except Exception as e:
            logger.exception(f"Analysis failed for document {document_id}")
            analysis.status = "failed"
            analysis.error_message = str(e)

        # Save final state
        await self._save_analysis(analysis)

        return analysis

    async def analyze_single_stream(
        self,
        document_id: str,
        options: AnalysisOptions | None = None,
        user_id: str | None = None,
    ) -> AsyncGenerator[AnalysisStreamEvent, None]:
        """
        Stream analysis progress for a single document.

        Yields AnalysisStreamEvent as analysis progresses.
        """
        options = options or AnalysisOptions()

        # Yield initial progress
        yield AnalysisStreamEvent(
            event="progress",
            stage="initializing",
            progress=0,
        )

        # Get document metadata
        doc_data = await self.firestore.get_document(document_id)
        if not doc_data:
            yield AnalysisStreamEvent(
                event="error",
                error=f"Document not found: {document_id}",
            )
            return

        if doc_data.get("status") != "indexed":
            yield AnalysisStreamEvent(
                event="error",
                error=f"Document is not indexed: {document_id}",
            )
            return

        contribution_number = doc_data.get("contribution_number", "")

        # Create analysis record
        analysis_id = str(uuid.uuid4())
        analysis = AnalysisResult(
            id=analysis_id,
            document_id=document_id,
            document_ids=[document_id],
            contribution_number=contribution_number,
            type="single",
            status="processing",
            strategy_version=self.strategy_version,
            options=options,
            created_by=user_id,
        )
        await self._save_analysis(analysis)

        yield AnalysisStreamEvent(
            event="progress",
            stage="fetching_evidence",
            progress=10,
        )

        try:
            # Get evidence
            evidences = await self.evidence_provider.get_by_document(document_id, top_k=100)
            if not evidences:
                yield AnalysisStreamEvent(
                    event="error",
                    error=f"No content found for document: {document_id}",
                )
                return

            yield AnalysisStreamEvent(
                event="progress",
                stage="analyzing",
                progress=30,
            )

            # Build prompt
            evidence_content = self._format_evidence_for_prompt(evidences)
            title = doc_data.get("title", "Unknown")
            meeting_id = doc_data.get("meeting", {}).get("id", "")
            meeting_name = doc_data.get("meeting", {}).get("name", meeting_id)
            source = doc_data.get("source", "Unknown")

            user_prompt = SINGLE_ANALYSIS_USER_PROMPT.format(
                contribution_number=contribution_number,
                title=title,
                meeting=meeting_name,
                source=source,
                evidence_content=evidence_content,
            )

            # Call LLM with streaming
            partial_text = ""
            async for chunk in self._call_llm_stream(
                system_prompt=SINGLE_ANALYSIS_SYSTEM_PROMPT,
                user_prompt=user_prompt,
            ):
                partial_text += chunk
                yield AnalysisStreamEvent(
                    event="partial",
                    stage="analyzing",
                    progress=50,
                    partial_result={"text": partial_text[:500]},  # Preview only
                )

            yield AnalysisStreamEvent(
                event="progress",
                stage="finalizing",
                progress=80,
            )

            # Parse the final result
            result = await self._parse_structured_response(partial_text, SingleAnalysis)
            result.evidences = self._select_supporting_evidence(evidences, result)

            # Update analysis
            analysis.result = result
            analysis.status = "completed"
            analysis.completed_at = datetime.utcnow()
            await self._save_analysis(analysis)

            yield AnalysisStreamEvent(
                event="complete",
                stage="completed",
                progress=100,
                analysis_id=analysis_id,
            )

        except Exception as e:
            logger.exception(f"Streaming analysis failed for document {document_id}")
            analysis.status = "failed"
            analysis.error_message = str(e)
            await self._save_analysis(analysis)

            yield AnalysisStreamEvent(
                event="error",
                error=str(e),
            )

    async def get_result(self, analysis_id: str) -> AnalysisResult | None:
        """Get analysis result by ID."""
        doc_ref = self.firestore.client.collection(self.ANALYSIS_RESULTS_COLLECTION).document(
            analysis_id
        )
        doc = doc_ref.get()
        if not doc.exists:
            return None

        return AnalysisResult.from_firestore(doc.id, doc.to_dict())

    async def get_cached_result(
        self,
        document_id: str,
        analysis_type: str,
    ) -> AnalysisResult | None:
        """Get cached analysis result for a document."""
        # Query by document_id, type, and strategy_version
        query = (
            self.firestore.client.collection(self.ANALYSIS_RESULTS_COLLECTION)
            .where("document_id", "==", document_id)
            .where("type", "==", analysis_type)
            .where("strategy_version", "==", self.strategy_version)
            .where("status", "==", "completed")
            .order_by("created_at", direction="DESCENDING")
            .limit(1)
        )

        docs = list(query.stream())
        if not docs:
            return None

        doc = docs[0]
        return AnalysisResult.from_firestore(doc.id, doc.to_dict())

    async def list_by_document(self, document_id: str) -> list[AnalysisResult]:
        """List all analyses for a document."""
        query = (
            self.firestore.client.collection(self.ANALYSIS_RESULTS_COLLECTION)
            .where("document_id", "==", document_id)
            .order_by("created_at", direction="DESCENDING")
        )

        results = []
        for doc in query.stream():
            results.append(AnalysisResult.from_firestore(doc.id, doc.to_dict()))

        return results

    async def _save_analysis(self, analysis: AnalysisResult) -> None:
        """Save analysis result to Firestore."""
        doc_ref = self.firestore.client.collection(self.ANALYSIS_RESULTS_COLLECTION).document(
            analysis.id
        )
        doc_ref.set(analysis.to_firestore())

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
        result: SingleAnalysis,
    ) -> list[Evidence]:
        """Select most relevant evidence to include in result."""
        # For now, include top evidence items
        # Could be enhanced to match evidence to specific findings
        return all_evidence[:10]

    async def _call_llm_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        output_schema: type,
    ):
        """Call LLM with structured output schema."""
        response = self._genai_client.models.generate_content(
            model=self.model,
            contents=[
                types.Content(
                    role="user",
                    parts=[types.Part(text=f"{system_prompt}\n\n{user_prompt}")],
                ),
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=output_schema,
            ),
        )

        # Parse the JSON response
        import json

        result_text = response.text
        result_data = json.loads(result_text)
        return output_schema.model_validate(result_data)

    async def _call_llm_stream(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> AsyncGenerator[str, None]:
        """Stream LLM response."""
        response = self._genai_client.models.generate_content_stream(
            model=self.model,
            contents=[
                types.Content(
                    role="user",
                    parts=[types.Part(text=f"{system_prompt}\n\n{user_prompt}")],
                ),
            ],
        )

        for chunk in response:
            if chunk.text:
                yield chunk.text

    async def _parse_structured_response(
        self,
        text: str,
        output_schema: type,
    ):
        """Parse streamed text into structured output."""
        import json

        # Try to parse as JSON directly
        try:
            data = json.loads(text)
            return output_schema.model_validate(data)
        except json.JSONDecodeError:
            # If not valid JSON, ask LLM to structure it
            prompt = f"Convert the following analysis into structured JSON:\n\n{text}"
            response = self._genai_client.models.generate_content(
                model=self.model,
                contents=[
                    types.Content(
                        role="user",
                        parts=[types.Part(text=prompt)],
                    ),
                ],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=output_schema,
                ),
            )
            data = json.loads(response.text)
            return output_schema.model_validate(data)
