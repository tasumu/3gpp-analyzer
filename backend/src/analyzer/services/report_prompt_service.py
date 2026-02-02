"""Service for managing report generation prompts."""

import logging
import uuid
from datetime import datetime

from analyzer.models.report_prompt import ReportPrompt
from analyzer.providers.firestore_client import FirestoreClient

logger = logging.getLogger(__name__)


class ReportPromptService:
    """Manages user-saved report generation prompts."""

    COLLECTION = "report_prompts"

    def __init__(self, firestore: FirestoreClient):
        """Initialize ReportPromptService."""
        self.firestore = firestore

    async def create(self, user_id: str, name: str, prompt_text: str) -> ReportPrompt:
        """Create a new report prompt."""
        prompt_id = str(uuid.uuid4())
        now = datetime.utcnow()

        prompt = ReportPrompt(
            id=prompt_id,
            user_id=user_id,
            name=name,
            prompt_text=prompt_text,
            created_at=now,
            updated_at=now,
        )

        doc_ref = self.firestore.client.collection(self.COLLECTION).document(prompt_id)
        doc_ref.set(prompt.to_firestore())

        logger.info(f"Created report prompt {prompt_id} for user {user_id}")
        return prompt

    async def get(self, prompt_id: str) -> ReportPrompt | None:
        """Get a report prompt by ID."""
        doc_ref = self.firestore.client.collection(self.COLLECTION).document(prompt_id)
        doc = doc_ref.get()

        if not doc.exists:
            return None

        return ReportPrompt.from_firestore(doc.id, doc.to_dict())

    async def list_by_user(self, user_id: str) -> list[ReportPrompt]:
        """List all report prompts for a user."""
        query = (
            self.firestore.client.collection(self.COLLECTION)
            .where("user_id", "==", user_id)
            .order_by("created_at", direction="DESCENDING")
        )

        prompts = []
        for doc in query.stream():
            prompts.append(ReportPrompt.from_firestore(doc.id, doc.to_dict()))

        return prompts

    async def update(
        self,
        prompt_id: str,
        user_id: str,
        name: str | None = None,
        prompt_text: str | None = None,
    ) -> ReportPrompt | None:
        """Update a report prompt."""
        doc_ref = self.firestore.client.collection(self.COLLECTION).document(prompt_id)
        doc = doc_ref.get()

        if not doc.exists:
            return None

        data = doc.to_dict()
        if data.get("user_id") != user_id:
            raise PermissionError("Cannot update another user's prompt")

        updates = {"updated_at": datetime.utcnow().isoformat()}
        if name is not None:
            updates["name"] = name
        if prompt_text is not None:
            updates["prompt_text"] = prompt_text

        doc_ref.update(updates)
        logger.info(f"Updated report prompt {prompt_id}")

        return await self.get(prompt_id)

    async def delete(self, prompt_id: str, user_id: str) -> bool:
        """Delete a report prompt."""
        doc_ref = self.firestore.client.collection(self.COLLECTION).document(prompt_id)
        doc = doc_ref.get()

        if not doc.exists:
            return False

        data = doc.to_dict()
        if data.get("user_id") != user_id:
            raise PermissionError("Cannot delete another user's prompt")

        doc_ref.delete()
        logger.info(f"Deleted report prompt {prompt_id}")

        return True
