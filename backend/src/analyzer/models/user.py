"""User model for admin approval flow."""

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, EmailStr, Field


class UserStatus(str, Enum):
    """User approval status."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class UserRole(str, Enum):
    """User role."""

    USER = "user"
    ADMIN = "admin"


class User(BaseModel):
    """User information model."""

    uid: str = Field(..., description="Firebase Auth UID")
    email: EmailStr = Field(..., description="User email address")
    display_name: str | None = Field(None, description="Display name")
    status: UserStatus = Field(default=UserStatus.PENDING, description="Approval status")
    role: UserRole = Field(default=UserRole.USER, description="User role")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), description="Registration date"
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), description="Last update date"
    )
    approved_by: str | None = Field(None, description="UID of approving admin")
    approved_at: datetime | None = Field(None, description="Approval date")
    last_login_at: datetime | None = Field(None, description="Last login date")

    def to_firestore(self) -> dict:
        """Convert to Firestore document."""
        return self.model_dump(mode="json")

    @classmethod
    def from_firestore(cls, uid: str, data: dict) -> "User":
        """Create from Firestore document."""
        data["uid"] = uid
        return cls.model_validate(data)
