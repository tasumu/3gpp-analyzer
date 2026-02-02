"""Review sheet generator for P2-03."""

from analyzer.models.analysis import AnalysisResult, SingleAnalysis
from analyzer.providers.storage_client import StorageClient
from analyzer.services.prompts import (
    CHANGE_ITEM_TEMPLATE,
    EVIDENCE_ITEM_TEMPLATE,
    ISSUE_ITEM_TEMPLATE,
    REVIEW_SHEET_TEMPLATE,
)


class ReviewSheetGenerator:
    """Generates Markdown review sheets from analysis results."""

    def __init__(self, storage: StorageClient):
        """
        Initialize the generator.

        Args:
            storage: StorageClient for saving review sheets.
        """
        self.storage = storage

    def generate(
        self,
        analysis: AnalysisResult,
        document_data: dict,
    ) -> str:
        """
        Generate Markdown review sheet from analysis result.

        Args:
            analysis: The analysis result.
            document_data: Document metadata.

        Returns:
            Markdown content as string.
        """
        if analysis.type != "single" or not isinstance(analysis.result, SingleAnalysis):
            raise ValueError("Only single analysis is supported for review sheets")

        result: SingleAnalysis = analysis.result

        # Format changes section
        if result.changes:
            changes_section = self._format_changes(result.changes)
        else:
            changes_section = "_No changes identified._"

        # Format issues section
        if result.issues:
            issues_section = self._format_issues(result.issues)
        else:
            issues_section = "_No issues identified._"

        # Format evidences section
        evidences_section = (
            self._format_evidences(result.evidences) if result.evidences else "_No evidence cited._"
        )

        # Get document info
        contribution_number = analysis.contribution_number
        meeting = document_data.get("meeting", {}).get("name", "Unknown")
        title = document_data.get("title", "Unknown")
        source = document_data.get("source", "Unknown")

        # Format the review sheet
        markdown = REVIEW_SHEET_TEMPLATE.format(
            contribution_number=contribution_number,
            meeting=meeting,
            title=title,
            source=source,
            analysis_date=analysis.created_at.strftime("%Y-%m-%d %H:%M UTC"),
            summary=result.summary,
            changes_section=changes_section,
            issues_section=issues_section,
            evidences_section=evidences_section,
            strategy_version=analysis.strategy_version,
        )

        return markdown

    def _format_changes(self, changes) -> str:
        """Format changes list to Markdown."""
        if not changes:
            return ""

        lines = []
        for i, change in enumerate(changes, 1):
            change_type = change.type.upper()
            lines.append(
                CHANGE_ITEM_TEMPLATE.format(
                    index=i,
                    change_type=change_type,
                    description=change.description,
                    clause=change.clause or "N/A",
                )
            )

        return "\n".join(lines)

    def _format_issues(self, issues) -> str:
        """Format issues list to Markdown."""
        if not issues:
            return ""

        lines = []
        for i, issue in enumerate(issues, 1):
            severity = issue.severity.upper()
            lines.append(
                ISSUE_ITEM_TEMPLATE.format(
                    index=i,
                    severity=severity,
                    description=issue.description,
                )
            )

        return "\n".join(lines)

    def _format_evidences(self, evidences) -> str:
        """Format evidences list to Markdown."""
        if not evidences:
            return ""

        lines = []
        for evidence in evidences[:10]:  # Limit to 10 for readability
            content_preview = evidence.content[:100].replace("\n", " ")
            lines.append(
                EVIDENCE_ITEM_TEMPLATE.format(
                    contribution_number=evidence.contribution_number,
                    clause=evidence.clause_number or "N/A",
                    page=evidence.page_number or "N/A",
                    content_preview=content_preview,
                )
            )

        return "\n".join(lines)

    async def save_and_get_url(
        self,
        analysis_id: str,
        content: str,
        expiration_minutes: int = 60,
    ) -> str:
        """
        Save review sheet to GCS and return signed URL.

        Args:
            analysis_id: Analysis ID for the filename.
            content: Markdown content.
            expiration_minutes: URL expiration time.

        Returns:
            Signed URL for downloading the review sheet.
        """
        # Save to GCS
        gcs_path = f"{StorageClient.OUTPUTS_PREFIX}/review-sheets/{analysis_id}.md"
        await self.storage.upload_bytes(
            data=content.encode("utf-8"),
            gcs_path=gcs_path,
            content_type="text/markdown",
        )

        # Generate signed URL
        url = await self.storage.generate_signed_url(gcs_path, expiration_minutes)
        return url
