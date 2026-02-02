"""Custom prompt model for user-saved analysis prompts."""

from datetime import datetime

from pydantic import BaseModel, Field


class CustomPrompt(BaseModel):
    """User-saved custom analysis prompt."""

    id: str = Field(..., description="Prompt ID")
    user_id: str = Field(..., description="Owner user ID")
    name: str = Field(..., description="Display name for the prompt")
    prompt_text: str = Field(..., description="The prompt text")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation time")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update time")

    def to_firestore(self) -> dict:
        """Convert to Firestore document format."""
        return self.model_dump(mode="json")

    @classmethod
    def from_firestore(cls, doc_id: str, data: dict) -> "CustomPrompt":
        """Create from Firestore document."""
        data["id"] = doc_id
        return cls.model_validate(data)
