"""Tests for document chunking module."""

import pytest

from analyzer.chunking.heading_based import HeadingBasedChunking
from analyzer.models.chunk import StructureType


class TestHeadingBasedChunking:
    """Tests for HeadingBasedChunking strategy."""

    def test_estimate_token_count(self):
        """Test token count estimation."""
        chunker = HeadingBasedChunking(max_tokens=1000)

        # ~4 chars per token
        text = "a" * 400  # Should be ~100 tokens
        count = chunker.estimate_token_count(text)
        assert 90 <= count <= 110  # Allow some variance

    def test_max_chars_calculation(self):
        """Test that max_chars is calculated from max_tokens."""
        chunker = HeadingBasedChunking(max_tokens=500)
        assert chunker.max_chars == 500 * 4  # CHARS_PER_TOKEN = 4

    def test_split_text(self):
        """Test text splitting at sentence boundaries."""
        chunker = HeadingBasedChunking(max_tokens=100)

        # Long text that should be split
        text = "First sentence. " * 100  # Much longer than max_chars

        parts = chunker._split_text(text)
        assert len(parts) > 1

        # Each part should be within limits
        for part in parts:
            assert len(part) <= chunker.max_chars


class TestStructureType:
    """Tests for StructureType enum."""

    def test_heading_types(self):
        """Test that all heading types exist."""
        assert StructureType.HEADING1.value == "heading1"
        assert StructureType.HEADING2.value == "heading2"
        assert StructureType.HEADING3.value == "heading3"
        assert StructureType.HEADING4.value == "heading4"
        assert StructureType.HEADING5.value == "heading5"
        assert StructureType.HEADING6.value == "heading6"

    def test_content_types(self):
        """Test content structure types."""
        assert StructureType.PARAGRAPH.value == "paragraph"
        assert StructureType.LIST_ITEM.value == "list_item"
        assert StructureType.TABLE.value == "table"
        assert StructureType.FIGURE.value == "figure"
