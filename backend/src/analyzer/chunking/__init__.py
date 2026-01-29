"""Document chunking module for the 3GPP Analyzer."""

from analyzer.chunking.base import ChunkingStrategy
from analyzer.chunking.extractor import DocxExtractor
from analyzer.chunking.heading_based import HeadingBasedChunking

__all__ = [
    "ChunkingStrategy",
    "DocxExtractor",
    "HeadingBasedChunking",
]
