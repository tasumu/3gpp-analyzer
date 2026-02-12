"""Q&A Service for RAG-based question answering (P3-05)."""

import json
import logging
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime
from typing import Any

from analyzer.agents.adk_agents import (
    ADKAgentRunner,
    create_agentic_search_agent,
    create_qa_agent,
)
from analyzer.agents.context import AgentToolContext
from analyzer.models.evidence import Evidence
from analyzer.models.qa import QAMode, QAResult, QAScope, QAStreamEvent
from analyzer.providers.base import EvidenceProvider
from analyzer.providers.firestore_client import FirestoreClient
from analyzer.services.document_service import DocumentService

logger = logging.getLogger(__name__)


class QAService:
    """
    Service for handling Q&A requests using RAG.

    Supports three search scopes:
    - document: Single document Q&A
    - meeting: Meeting-wide Q&A
    - global: Cross-meeting Q&A

    Uses Google ADK for agent execution.
    """

    QA_RESULTS_COLLECTION = "qa_results"

    def __init__(
        self,
        evidence_provider: EvidenceProvider,
        firestore: FirestoreClient,
        project_id: str,
        location: str = "asia-northeast1",
        model: str = "gemini-3-pro-preview",
        save_results: bool = True,
        document_service: DocumentService | None = None,
    ):
        """
        Initialize QAService.

        Args:
            evidence_provider: Provider for RAG search operations.
            firestore: Firestore client for persistence.
            project_id: GCP project ID.
            location: GCP region for Vertex AI.
            model: LLM model name for Q&A.
            save_results: Whether to save Q&A results to Firestore.
            document_service: Document service (required for agentic mode).
        """
        self.evidence_provider = evidence_provider
        self.firestore = firestore
        self.project_id = project_id
        self.location = location
        self.model = model
        self.save_results = save_results
        self.document_service = document_service

    async def answer(
        self,
        question: str,
        scope: QAScope = QAScope.GLOBAL,
        scope_id: str | None = None,
        scope_ids: list[str] | None = None,
        filters: dict[str, Any] | None = None,
        language: str = "ja",
        user_id: str | None = None,
        session_id: str | None = None,
        mode: QAMode = QAMode.RAG,
    ) -> QAResult:
        """
        Answer a question using RAG or agentic search.

        Args:
            question: The user's question.
            scope: Search scope (document, meeting, or global).
            scope_id: Scope identifier (document_id or meeting_id).
            scope_ids: Multiple scope identifiers (takes precedence over scope_id).
            filters: Additional metadata filters.
            language: Response language (ja or en).
            user_id: User ID who initiated the Q&A.
            session_id: Session ID for conversation continuity.
            mode: Q&A mode (rag or agentic).

        Returns:
            QAResult with the answer and supporting evidence.

        Raises:
            ValueError: If scope requires scope_id but none provided.
        """
        # Support multiple scope IDs (takes precedence)
        effective_scope_id = scope_id
        multi_meeting_mode = False
        if scope_ids and len(scope_ids) > 1:
            effective_scope_id = None
            multi_meeting_mode = True
            if filters is None:
                filters = {}
            filters["meeting_id__in"] = scope_ids
        elif scope_ids and len(scope_ids) == 1:
            effective_scope_id = scope_ids[0]

        # Validate scope_id
        if (
            scope in (QAScope.DOCUMENT, QAScope.MEETING)
            and not effective_scope_id
            and not multi_meeting_mode
        ):
            raise ValueError(f"scope_id or scope_ids is required for scope={scope.value}")

        # Agentic mode requires meeting scope
        if mode == QAMode.AGENTIC and scope != QAScope.MEETING:
            raise ValueError("Agentic search mode requires meeting scope")
        if mode == QAMode.AGENTIC and not effective_scope_id:
            raise ValueError("Agentic search mode requires a meeting_id (scope_id)")

        logger.info(
            f"Processing Q&A ({mode.value}): question='{question[:50]}...', "
            f"scope={scope.value}, scope_id={effective_scope_id}, "
            f"scope_ids={scope_ids}, multi_meeting_mode={multi_meeting_mode}"
        )

        # Create agent based on mode
        if mode == QAMode.AGENTIC:
            agent = create_agentic_search_agent(
                meeting_id=effective_scope_id,
                model=self.model,
                language=language,
            )
            agent_context = AgentToolContext(
                evidence_provider=self.evidence_provider,
                scope=scope.value,
                scope_id=effective_scope_id,
                language=language,
                filters=filters,
                document_service=self.document_service,
                firestore=self.firestore,
                meeting_id=effective_scope_id,
            )
        else:
            agent_scope = "global" if multi_meeting_mode else scope.value
            agent = create_qa_agent(
                model=self.model,
                scope=agent_scope,
                scope_id=effective_scope_id,
                language=language,
            )
            agent_context = AgentToolContext(
                evidence_provider=self.evidence_provider,
                scope=scope.value,
                scope_id=effective_scope_id,
                language=language,
                filters=filters,
            )

        # Create runner and execute
        runner = ADKAgentRunner(agent=agent, agent_context=agent_context)

        try:
            answer_text, unique_evidences = await runner.run(
                user_input=question,
                user_id=user_id or "anonymous",
                session_id=session_id,
            )
        except Exception as e:
            logger.error(f"Error running Q&A agent: {e}")
            raise

        # Create result
        result = QAResult(
            id=str(uuid.uuid4()),
            question=question,
            answer=answer_text,
            scope=scope,
            scope_id=effective_scope_id,
            mode=mode,
            evidences=unique_evidences,
            created_at=datetime.utcnow(),
            created_by=user_id,
        )

        # Save result if enabled
        if self.save_results:
            await self._save_result(result)

        return result

    async def answer_stream(
        self,
        question: str,
        scope: QAScope = QAScope.GLOBAL,
        scope_id: str | None = None,
        scope_ids: list[str] | None = None,
        filters: dict[str, Any] | None = None,
        language: str = "ja",
        user_id: str | None = None,
        session_id: str | None = None,
        mode: QAMode = QAMode.RAG,
    ) -> AsyncGenerator[QAStreamEvent, None]:
        """
        Answer a question with streaming response.

        Args:
            question: The user's question.
            scope: Search scope (document, meeting, or global).
            scope_id: Scope identifier (document_id or meeting_id).
            scope_ids: Multiple scope identifiers (takes precedence over scope_id).
            filters: Additional metadata filters.
            language: Response language (ja or en).
            user_id: User ID who initiated the Q&A.
            session_id: Session ID for conversation continuity.
            mode: Q&A mode (rag or agentic).

        Yields:
            QAStreamEvent objects with answer chunks and evidence.
        """
        # Support multiple scope IDs (takes precedence)
        effective_scope_id = scope_id
        multi_meeting_mode = False
        if scope_ids and len(scope_ids) > 1:
            effective_scope_id = None
            multi_meeting_mode = True
            if filters is None:
                filters = {}
            filters["meeting_id__in"] = scope_ids
        elif scope_ids and len(scope_ids) == 1:
            effective_scope_id = scope_ids[0]

        # Validate scope_id
        if (
            scope in (QAScope.DOCUMENT, QAScope.MEETING)
            and not effective_scope_id
            and not multi_meeting_mode
        ):
            yield QAStreamEvent(
                type="error",
                error=f"scope_id or scope_ids is required for scope={scope.value}",
            )
            return

        # Agentic mode requires meeting scope
        if mode == QAMode.AGENTIC and scope != QAScope.MEETING:
            yield QAStreamEvent(
                type="error",
                error="Agentic search mode requires meeting scope",
            )
            return
        if mode == QAMode.AGENTIC and not effective_scope_id:
            yield QAStreamEvent(
                type="error",
                error="Agentic search mode requires a meeting_id",
            )
            return

        logger.info(
            f"Processing streaming Q&A ({mode.value}): question='{question[:50]}...', "
            f"scope={scope.value}, scope_id={effective_scope_id}, "
            f"scope_ids={scope_ids}, multi_meeting_mode={multi_meeting_mode}"
        )

        # Create agent based on mode
        if mode == QAMode.AGENTIC:
            agent = create_agentic_search_agent(
                meeting_id=effective_scope_id,
                model=self.model,
                language=language,
            )
            agent_context = AgentToolContext(
                evidence_provider=self.evidence_provider,
                scope=scope.value,
                scope_id=effective_scope_id,
                language=language,
                filters=filters,
                document_service=self.document_service,
                firestore=self.firestore,
                meeting_id=effective_scope_id,
            )
        else:
            agent_scope = "global" if multi_meeting_mode else scope.value
            agent = create_qa_agent(
                model=self.model,
                scope=agent_scope,
                scope_id=effective_scope_id,
                language=language,
            )
            agent_context = AgentToolContext(
                evidence_provider=self.evidence_provider,
                scope=scope.value,
                scope_id=effective_scope_id,
                language=language,
                filters=filters,
            )

        # Create runner
        runner = ADKAgentRunner(agent=agent, agent_context=agent_context)

        try:
            full_answer = ""
            evidences: list[Evidence] = []

            async for event in runner.run_stream(
                user_input=question,
                user_id=user_id or "anonymous",
                session_id=session_id,
            ):
                if event["type"] == "chunk":
                    full_answer += event.get("content", "")
                    yield QAStreamEvent(type="chunk", content=event.get("content", ""))
                elif event["type"] == "tool_call":
                    yield QAStreamEvent(
                        type="tool_call",
                        content=json.dumps(
                            {
                                "tool": event.get("tool", ""),
                                "args": event.get("args", {}),
                            }
                        ),
                    )
                elif event["type"] == "tool_result":
                    yield QAStreamEvent(
                        type="tool_result",
                        content=json.dumps(
                            {
                                "tool": event.get("tool", ""),
                                "summary": event.get("summary", ""),
                            }
                        ),
                    )
                elif event["type"] == "done":
                    full_answer = event.get("content", full_answer)
                    evidences = event.get("evidences", [])

            # Yield evidence events
            for ev in evidences:
                yield QAStreamEvent(type="evidence", evidence=ev)

            # Create result
            result = QAResult(
                id=str(uuid.uuid4()),
                question=question,
                answer=full_answer,
                scope=scope,
                scope_id=scope_id,
                mode=mode,
                evidences=evidences,
                created_at=datetime.utcnow(),
                created_by=user_id,
            )

            # Save result if enabled
            if self.save_results:
                await self._save_result(result)

            # Yield done event
            yield QAStreamEvent(type="done", result=result)

        except Exception as e:
            logger.error(f"Error in streaming Q&A: {e}")
            yield QAStreamEvent(type="error", error=str(e))

    async def _save_result(self, result: QAResult) -> None:
        """Save Q&A result to Firestore."""
        try:
            doc_ref = self.firestore.client.collection(self.QA_RESULTS_COLLECTION).document(
                result.id
            )
            doc_ref.set(result.to_firestore())
            logger.info(f"Saved Q&A result: {result.id}")
        except Exception as e:
            logger.error(f"Error saving Q&A result: {e}")
            # Don't raise - saving is not critical

    async def get_result(self, result_id: str) -> QAResult | None:
        """Get a saved Q&A result by ID."""
        try:
            doc_ref = self.firestore.client.collection(self.QA_RESULTS_COLLECTION).document(
                result_id
            )
            doc = doc_ref.get()
            if doc.exists:
                return QAResult.from_firestore(doc.id, doc.to_dict())
        except Exception as e:
            logger.error(f"Error fetching Q&A result: {e}")
        return None

    async def list_results(
        self,
        user_id: str | None = None,
        scope: QAScope | None = None,
        limit: int = 50,
    ) -> list[QAResult]:
        """
        List Q&A results with optional filters.

        Args:
            user_id: Filter by user ID.
            scope: Filter by scope.
            limit: Maximum number of results.

        Returns:
            List of QAResult objects.
        """
        try:
            query = self.firestore.client.collection(self.QA_RESULTS_COLLECTION)

            if user_id:
                query = query.where("created_by", "==", user_id)
            if scope:
                query = query.where("scope", "==", scope.value)

            query = query.order_by("created_at", direction="DESCENDING").limit(limit)

            results = []
            for doc in query.stream():
                results.append(QAResult.from_firestore(doc.id, doc.to_dict()))

            return results

        except Exception as e:
            logger.error(f"Error listing Q&A results: {e}")
            return []
