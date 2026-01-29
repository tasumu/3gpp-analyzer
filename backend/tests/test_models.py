"""Tests for data models."""

from datetime import datetime

import pytest

from analyzer.models.chunk import Chunk, ChunkMetadata, StructureType
from analyzer.models.document import Document, DocumentStatus, Meeting, SourceFile
from analyzer.models.evidence import Evidence


class TestDocumentModels:
    """Tests for document-related models."""

    def test_document_status_enum(self):
        """Test DocumentStatus enum values."""
        assert DocumentStatus.METADATA_ONLY.value == "metadata_only"
        assert DocumentStatus.INDEXED.value == "indexed"
        assert DocumentStatus.ERROR.value == "error"

    def test_meeting_creation(self):
        """Test Meeting model creation."""
        meeting = Meeting(
            id="SA2#162",
            name="SA2_162",
            working_group="SA2",
        )
        assert meeting.id == "SA2#162"
        assert meeting.working_group == "SA2"

    def test_source_file_creation(self):
        """Test SourceFile model creation."""
        source_file = SourceFile(
            filename="S2-2401234.doc",
            ftp_path="/Meetings/SA2/SA2_162/Docs/S2-2401234.doc",
            size_bytes=1024,
            modified_at=datetime.utcnow(),
        )
        assert source_file.filename == "S2-2401234.doc"
        assert source_file.size_bytes == 1024

    def test_document_creation(self):
        """Test Document model creation."""
        source_file = SourceFile(
            filename="S2-2401234.doc",
            ftp_path="/test/path",
            size_bytes=1024,
            modified_at=datetime.utcnow(),
        )
        doc = Document(
            id="S2-2401234",
            contribution_number="S2-2401234",
            source_file=source_file,
            status=DocumentStatus.METADATA_ONLY,
        )
        assert doc.id == "S2-2401234"
        assert doc.status == DocumentStatus.METADATA_ONLY

    def test_document_to_firestore(self):
        """Test Document serialization to Firestore format."""
        source_file = SourceFile(
            filename="S2-2401234.doc",
            ftp_path="/test/path",
            size_bytes=1024,
            modified_at=datetime.utcnow(),
        )
        doc = Document(
            id="S2-2401234",
            contribution_number="S2-2401234",
            source_file=source_file,
        )
        data = doc.to_firestore()
        assert data["id"] == "S2-2401234"
        assert data["contribution_number"] == "S2-2401234"


class TestChunkModels:
    """Tests for chunk-related models."""

    def test_structure_type_enum(self):
        """Test StructureType enum values."""
        assert StructureType.HEADING1.value == "heading1"
        assert StructureType.PARAGRAPH.value == "paragraph"
        assert StructureType.TABLE.value == "table"

    def test_chunk_metadata_creation(self):
        """Test ChunkMetadata model creation."""
        metadata = ChunkMetadata(
            document_id="doc-1",
            contribution_number="S2-2401234",
            clause_number="5.2.1",
            clause_title="Test Clause",
            structure_type=StructureType.HEADING2,
        )
        assert metadata.document_id == "doc-1"
        assert metadata.clause_number == "5.2.1"

    def test_chunk_creation(self):
        """Test Chunk model creation."""
        metadata = ChunkMetadata(
            document_id="doc-1",
            contribution_number="S2-2401234",
        )
        chunk = Chunk(
            id="chunk-1",
            content="Test content for chunk.",
            metadata=metadata,
            token_count=5,
        )
        assert chunk.id == "chunk-1"
        assert chunk.content == "Test content for chunk."
        assert chunk.embedding is None


class TestEvidenceModels:
    """Tests for evidence-related models."""

    def test_evidence_creation(self):
        """Test Evidence model creation."""
        evidence = Evidence(
            chunk_id="chunk-1",
            document_id="doc-1",
            contribution_number="S2-2401234",
            content="Test evidence content.",
            clause_number="5.2.1",
            relevance_score=0.95,
        )
        assert evidence.chunk_id == "chunk-1"
        assert evidence.relevance_score == 0.95

    def test_evidence_from_chunk(self):
        """Test Evidence.from_chunk factory method."""
        chunk_data = {
            "id": "chunk-1",
            "content": "Test content",
            "metadata": {
                "document_id": "doc-1",
                "contribution_number": "S2-2401234",
                "clause_number": "5.2.1",
                "clause_title": "Test Clause",
            },
        }
        evidence = Evidence.from_chunk(chunk_data, relevance_score=0.9)
        assert evidence.chunk_id == "chunk-1"
        assert evidence.document_id == "doc-1"
        assert evidence.relevance_score == 0.9

    def test_evidence_relevance_score_bounds(self):
        """Test that relevance score is bounded between 0 and 1."""
        with pytest.raises(ValueError):
            Evidence(
                chunk_id="chunk-1",
                document_id="doc-1",
                contribution_number="S2-2401234",
                content="Test",
                relevance_score=1.5,  # Invalid: > 1.0
            )
