"""Meeting Report Generator for P3-06."""

import logging
import uuid
from datetime import datetime

from analyzer.agents.adk_agents import ADKAgentRunner, create_meeting_report_agent
from analyzer.agents.context import AgentToolContext
from analyzer.models.meeting_analysis import MeetingReport, MeetingSummary
from analyzer.providers.base import EvidenceProvider
from analyzer.providers.firestore_client import FirestoreClient
from analyzer.providers.storage_client import StorageClient
from analyzer.services.document_service import DocumentService
from analyzer.services.meeting_service import MeetingService

logger = logging.getLogger(__name__)


class MeetingReportGenerator:
    """
    Generator for comprehensive meeting reports (P3-06).

    Uses MeetingService for summarization and ADK agents
    for detailed analysis with RAG search capabilities.
    """

    MEETING_REPORTS_COLLECTION = "meeting_reports"
    REPORTS_PREFIX = "outputs/meeting-reports"

    def __init__(
        self,
        meeting_service: MeetingService,
        evidence_provider: EvidenceProvider,
        document_service: DocumentService,
        firestore: FirestoreClient,
        storage: StorageClient,
        project_id: str,
        location: str = "asia-northeast1",
        model: str = "gemini-2.5-pro",
        expiration_minutes: int = 60,
    ):
        """
        Initialize MeetingReportGenerator.

        Args:
            meeting_service: Service for meeting summarization.
            evidence_provider: Provider for RAG search.
            document_service: Service for document operations.
            firestore: Firestore client.
            storage: Storage client for report files.
            project_id: GCP project ID.
            location: GCP region.
            model: Model for report generation agent.
            expiration_minutes: Signed URL expiration time.
        """
        self.meeting_service = meeting_service
        self.evidence_provider = evidence_provider
        self.document_service = document_service
        self.firestore = firestore
        self.storage = storage
        self.project_id = project_id
        self.location = location
        self.model = model
        self.expiration_minutes = expiration_minutes

    async def generate(
        self,
        meeting_id: str,
        custom_prompt: str | None = None,
        language: str = "ja",
        user_id: str | None = None,
    ) -> MeetingReport:
        """
        Generate a comprehensive meeting report.

        Process:
        1. Call MeetingService.summarize_meeting() to get base summary
        2. Use MeetingReportAgent to perform detailed analysis with RAG
        3. Generate Markdown report
        4. Save to GCS and create signed URL

        Args:
            meeting_id: Meeting ID to generate report for.
            custom_prompt: Optional custom analysis focus.
            language: Output language.
            user_id: User ID who requested.

        Returns:
            MeetingReport with download URL.
        """
        logger.info(f"Generating meeting report for {meeting_id}")

        # Step 1: Get meeting summary
        summary = await self.meeting_service.summarize_meeting(
            meeting_id=meeting_id,
            custom_prompt=custom_prompt,
            language=language,
            user_id=user_id,
        )

        # Step 2: Use ADK agent for detailed analysis
        agent = create_meeting_report_agent(
            meeting_id=meeting_id,
            model=self.model,
            language=language,
            custom_prompt=custom_prompt,
        )

        # Create context with services
        agent_context = AgentToolContext(
            evidence_provider=self.evidence_provider,
            scope="meeting",
            scope_id=meeting_id,
            meeting_id=meeting_id,
            document_service=self.document_service,
            firestore=self.firestore,
            language=language,
        )

        # Create runner and execute
        runner = ADKAgentRunner(agent=agent, agent_context=agent_context)

        detailed_analysis, evidences = await runner.run(
            user_input=self._build_agent_prompt(meeting_id, summary, custom_prompt, language),
            user_id=user_id or "anonymous",
        )

        # Step 3: Generate Markdown report
        markdown_content = self._format_report(
            meeting_id=meeting_id,
            summary=summary,
            detailed_analysis=detailed_analysis,
            evidences=evidences,
            custom_prompt=custom_prompt,
            language=language,
        )

        # Step 4: Save to GCS
        report_id = str(uuid.uuid4())
        gcs_path = f"{self.REPORTS_PREFIX}/{meeting_id.replace('#', '_')}/{report_id}.md"

        await self.storage.upload_bytes(
            data=markdown_content.encode("utf-8"),
            gcs_path=gcs_path,
            content_type="text/markdown",
        )

        # Generate signed URL
        download_url = await self.storage.generate_signed_url(
            gcs_path=gcs_path,
            expiration_minutes=self.expiration_minutes,
        )

        # Create report object
        report = MeetingReport(
            id=report_id,
            meeting_id=meeting_id,
            summary_id=summary.id,
            content=markdown_content,
            gcs_path=gcs_path,
            download_url=download_url,
            created_at=datetime.utcnow(),
            created_by=user_id,
        )

        # Save metadata to Firestore
        await self._save_report(report)

        logger.info(f"Generated meeting report: {report_id}")
        return report

    def _build_agent_prompt(
        self,
        meeting_id: str,
        summary: MeetingSummary,
        custom_prompt: str | None,
        language: str,
    ) -> str:
        """Build prompt for the meeting report agent."""
        custom_instruction = ""
        if custom_prompt:
            custom_instruction = f"\n\nSpecial focus: {custom_prompt}"

        # Include key info from summary
        top_docs = summary.individual_summaries[:10]
        docs_preview = "\n".join(
            [f"- {s.contribution_number}: {s.title} ({s.source})" for s in top_docs]
        )

        return f"""Based on the meeting summary for {meeting_id}, perform detailed analysis.

Key Topics Identified: {", ".join(summary.key_topics) if summary.key_topics else "N/A"}

Sample Contributions:
{docs_preview}

Tasks:
1. Search for specific technical details on the key topics
2. Identify any competing proposals or conflicts
3. Find notable contributions that deserve special attention
4. Look for emerging trends or patterns
{custom_instruction}

Use the search_evidence tool to find specific details.
Provide a detailed analysis with citations."""

    def _format_report(
        self,
        meeting_id: str,
        summary: MeetingSummary,
        detailed_analysis: str,
        evidences: list,
        custom_prompt: str | None,
        language: str,
    ) -> str:
        """Format the final Markdown report."""
        # Header
        if language == "ja":
            title = f"# 会合レポート: {meeting_id}"
            overview_title = "## 概要"
            topics_title = "## 主要トピック"
            analysis_title = "## 詳細分析"
            contributions_title = "## 寄書一覧"
            references_title = "## 参考資料"
            custom_focus_label = "分析観点"
            doc_count_label = "分析対象寄書数"
            generated_label = "生成日時"
        else:
            title = f"# Meeting Report: {meeting_id}"
            overview_title = "## Overview"
            topics_title = "## Key Topics"
            analysis_title = "## Detailed Analysis"
            contributions_title = "## Contributions"
            references_title = "## References"
            custom_focus_label = "Analysis Focus"
            doc_count_label = "Documents Analyzed"
            generated_label = "Generated"

        # Build sections
        sections = [
            title,
            "",
            f"- **{doc_count_label}**: {summary.document_count}",
            f"- **{generated_label}**: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
        ]

        if custom_prompt:
            sections.append(f"- **{custom_focus_label}**: {custom_prompt}")

        sections.extend(
            [
                "",
                "---",
                "",
                overview_title,
                "",
                summary.overall_report,
                "",
            ]
        )

        # Key topics
        if summary.key_topics:
            sections.extend(
                [
                    topics_title,
                    "",
                ]
            )
            for topic in summary.key_topics:
                sections.append(f"- {topic}")
            sections.append("")

        # Detailed analysis from agent
        sections.extend(
            [
                analysis_title,
                "",
                detailed_analysis,
                "",
            ]
        )

        # Contribution summaries table
        sections.extend(
            [
                contributions_title,
                "",
                "| Contribution | Title | Source | Summary |",
                "|-------------|-------|--------|---------|",
            ]
        )

        for s in summary.individual_summaries[:50]:  # Limit to 50
            # Truncate summary for table
            short_summary = s.summary[:100] + "..." if len(s.summary) > 100 else s.summary
            short_summary = short_summary.replace("|", "\\|").replace("\n", " ")
            title_clean = (s.title or "Untitled")[:50].replace("|", "\\|")
            source_clean = s.source or "N/A"
            row = f"| {s.contribution_number} | {title_clean} | {source_clean} | {short_summary} |"
            sections.append(row)

        sections.append("")

        # References from RAG search
        if evidences:
            sections.extend(
                [
                    references_title,
                    "",
                ]
            )
            # Group by contribution
            by_contrib: dict[str, list] = {}
            for ev in evidences[:30]:  # Limit references
                contrib = ev.contribution_number
                if contrib not in by_contrib:
                    by_contrib[contrib] = []
                by_contrib[contrib].append(ev)

            for contrib, evs in by_contrib.items():
                sections.append(f"### {contrib}")
                sections.append("")
                for ev in evs[:3]:  # Max 3 per contribution
                    clause_info = f"[{ev.clause_number}]" if ev.clause_number else ""
                    sections.append(f"- {clause_info} {ev.content[:200]}...")
                sections.append("")

        # Footer
        sections.extend(
            [
                "---",
                "",
                "*This report was generated automatically by 3GPP Analyzer.*",
            ]
        )

        return "\n".join(sections)

    async def _save_report(self, report: MeetingReport) -> None:
        """Save report metadata to Firestore."""
        try:
            doc_ref = self.firestore.client.collection(self.MEETING_REPORTS_COLLECTION).document(
                report.id
            )
            doc_ref.set(report.to_firestore())
            logger.info(f"Saved meeting report metadata: {report.id}")
        except Exception as e:
            logger.error(f"Error saving meeting report: {e}")

    async def get_report(self, report_id: str) -> MeetingReport | None:
        """Get a report by ID."""
        try:
            doc_ref = self.firestore.client.collection(self.MEETING_REPORTS_COLLECTION).document(
                report_id
            )
            doc = doc_ref.get()
            if doc.exists:
                data = doc.to_dict()
                # Regenerate download URL
                download_url = await self.storage.generate_signed_url(
                    gcs_path=data["gcs_path"],
                    expiration_minutes=self.expiration_minutes,
                )
                return MeetingReport(
                    id=doc.id,
                    meeting_id=data["meeting_id"],
                    summary_id=data["summary_id"],
                    content="",  # Content not stored in Firestore
                    gcs_path=data["gcs_path"],
                    download_url=download_url,
                    created_at=data.get("created_at", datetime.utcnow()),
                    created_by=data.get("created_by"),
                )
        except Exception as e:
            logger.error(f"Error fetching meeting report: {e}")
        return None

    async def list_reports(
        self,
        meeting_id: str | None = None,
        limit: int = 20,
    ) -> list[MeetingReport]:
        """List reports with optional meeting filter."""
        try:
            query = self.firestore.client.collection(self.MEETING_REPORTS_COLLECTION)

            if meeting_id:
                query = query.where("meeting_id", "==", meeting_id)

            query = query.order_by("created_at", direction="DESCENDING").limit(limit)

            results = []
            for doc in query.stream():
                data = doc.to_dict()
                download_url = await self.storage.generate_signed_url(
                    gcs_path=data["gcs_path"],
                    expiration_minutes=self.expiration_minutes,
                )
                results.append(
                    MeetingReport(
                        id=doc.id,
                        meeting_id=data["meeting_id"],
                        summary_id=data["summary_id"],
                        content="",
                        gcs_path=data["gcs_path"],
                        download_url=download_url,
                        created_at=data.get("created_at", datetime.utcnow()),
                        created_by=data.get("created_by"),
                    )
                )
            return results
        except Exception as e:
            logger.error(f"Error listing meeting reports: {e}")
            return []
