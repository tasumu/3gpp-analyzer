"""Sync history model for tracking synced FTP directories."""

import hashlib
from datetime import datetime

from pydantic import BaseModel, Field


class SyncHistory(BaseModel):
    """Record of a synced FTP directory."""

    id: str = Field(..., description="Document ID (hash of directory_path)")
    directory_path: str = Field(..., description="FTP directory path that was synced")
    last_synced_at: datetime = Field(
        default_factory=datetime.utcnow, description="Timestamp of last sync"
    )
    documents_found: int = Field(0, description="Number of documents found in last sync")
    documents_new: int = Field(0, description="Number of new documents in last sync")
    documents_updated: int = Field(0, description="Number of updated documents in last sync")
    synced_count: int = Field(0, description="Current total synced document count")

    def to_firestore(self) -> dict:
        """Convert to Firestore document format."""
        return self.model_dump(mode="json")

    @classmethod
    def from_firestore(cls, doc_id: str, data: dict) -> "SyncHistory":
        """Create from Firestore document."""
        data["id"] = doc_id
        return cls.model_validate(data)

    @staticmethod
    def generate_id(directory_path: str) -> str:
        """Generate a deterministic document ID from the directory path."""
        return hashlib.sha256(directory_path.encode()).hexdigest()[:16]
