"""Heading-based chunking strategy (P1-03)."""

import uuid
from pathlib import Path

from analyzer.chunking.base import ChunkingStrategy
from analyzer.chunking.extractor import DocxExtractor, StructureElement
from analyzer.models.chunk import Chunk, ChunkMetadata, StructureType


class HeadingBasedChunking(ChunkingStrategy):
    """
    Chunking strategy that splits documents by headings.

    Creates chunks that:
    - Respect heading boundaries (never split in middle of section)
    - Stay within token limits (split large sections)
    - Preserve heading hierarchy in metadata
    """

    # Approximate tokens per character (conservative estimate)
    CHARS_PER_TOKEN = 4

    def __init__(self, max_tokens: int = 1000):
        """
        Initialize the chunking strategy.

        Args:
            max_tokens: Maximum tokens per chunk (default 1000).
        """
        self.max_tokens = max_tokens
        self.max_chars = max_tokens * self.CHARS_PER_TOKEN
        self.extractor = DocxExtractor()

    def estimate_token_count(self, text: str) -> int:
        """Estimate token count from character count."""
        return len(text) // self.CHARS_PER_TOKEN

    async def chunk_document(
        self,
        file_path: Path | str,
        document_id: str,
        contribution_number: str,
        meeting_id: str | None = None,
    ) -> list[Chunk]:
        """Split a document into chunks based on headings."""
        file_path = Path(file_path)

        # Extract document structure
        elements = self.extractor.extract_structure(file_path)

        # Group elements by sections
        sections = self._group_by_sections(elements)

        # Convert sections to chunks
        chunks = []
        for section in sections:
            section_chunks = self._create_chunks_from_section(
                section,
                document_id,
                contribution_number,
                meeting_id,
            )
            chunks.extend(section_chunks)

        return chunks

    def _group_by_sections(
        self,
        elements: list[StructureElement],
    ) -> list[list[StructureElement]]:
        """
        Group elements into sections based on headings.

        A section starts with a heading and includes all content
        until the next heading of equal or higher level.
        """
        if not elements:
            return []

        sections = []
        current_section = []

        for element in elements:
            # Check if this is a heading
            is_heading = element.heading_level is not None

            if is_heading:
                # Start a new section
                if current_section:
                    sections.append(current_section)
                current_section = [element]
            else:
                # Add to current section
                current_section.append(element)

        # Don't forget the last section
        if current_section:
            sections.append(current_section)

        return sections

    def _create_chunks_from_section(
        self,
        section: list[StructureElement],
        document_id: str,
        contribution_number: str,
        meeting_id: str | None,
    ) -> list[Chunk]:
        """
        Create chunks from a section of elements.

        If section is too large, split while preserving context.
        """
        if not section:
            return []

        # Get section heading info
        heading_element = section[0] if section[0].heading_level is not None else None
        clause_number = None
        clause_title = None
        heading_hierarchy = []

        if heading_element:
            clause_number = heading_element.clause_number
            clause_title = heading_element.content
            heading_hierarchy = heading_element.parent_headings + [heading_element.content]
        elif section:
            # Use parent headings from first element
            heading_hierarchy = section[0].parent_headings

        # Combine content
        content_parts = [el.content for el in section]
        full_content = "\n\n".join(content_parts)

        # Check if we need to split
        if len(full_content) <= self.max_chars:
            # Single chunk
            return [
                self._create_chunk(
                    content=full_content,
                    document_id=document_id,
                    contribution_number=contribution_number,
                    meeting_id=meeting_id,
                    clause_number=clause_number,
                    clause_title=clause_title,
                    heading_hierarchy=heading_hierarchy,
                    structure_type=self._get_primary_structure_type(section),
                )
            ]

        # Split into multiple chunks
        return self._split_large_section(
            elements=section,
            document_id=document_id,
            contribution_number=contribution_number,
            meeting_id=meeting_id,
            clause_number=clause_number,
            clause_title=clause_title,
            heading_hierarchy=heading_hierarchy,
        )

    def _split_large_section(
        self,
        elements: list[StructureElement],
        document_id: str,
        contribution_number: str,
        meeting_id: str | None,
        clause_number: str | None,
        clause_title: str | None,
        heading_hierarchy: list[str],
    ) -> list[Chunk]:
        """Split a large section into multiple chunks."""
        chunks = []
        current_content = []
        current_length = 0

        for element in elements:
            element_length = len(element.content)

            # If single element is too large, split it
            if element_length > self.max_chars:
                # Flush current content
                if current_content:
                    chunks.append(
                        self._create_chunk(
                            content="\n\n".join(current_content),
                            document_id=document_id,
                            contribution_number=contribution_number,
                            meeting_id=meeting_id,
                            clause_number=clause_number,
                            clause_title=clause_title,
                            heading_hierarchy=heading_hierarchy,
                            structure_type=element.structure_type,
                        )
                    )
                    current_content = []
                    current_length = 0

                # Split the large element
                for part in self._split_text(element.content):
                    chunks.append(
                        self._create_chunk(
                            content=part,
                            document_id=document_id,
                            contribution_number=contribution_number,
                            meeting_id=meeting_id,
                            clause_number=clause_number,
                            clause_title=clause_title,
                            heading_hierarchy=heading_hierarchy,
                            structure_type=element.structure_type,
                        )
                    )
                continue

            # Check if adding this element exceeds limit
            if current_length + element_length > self.max_chars and current_content:
                # Flush current content
                chunks.append(
                    self._create_chunk(
                        content="\n\n".join(current_content),
                        document_id=document_id,
                        contribution_number=contribution_number,
                        meeting_id=meeting_id,
                        clause_number=clause_number,
                        clause_title=clause_title,
                        heading_hierarchy=heading_hierarchy,
                        structure_type=self._get_primary_structure_type_from_content(
                            current_content
                        ),
                    )
                )
                current_content = []
                current_length = 0

            current_content.append(element.content)
            current_length += element_length

        # Flush remaining content
        if current_content:
            chunks.append(
                self._create_chunk(
                    content="\n\n".join(current_content),
                    document_id=document_id,
                    contribution_number=contribution_number,
                    meeting_id=meeting_id,
                    clause_number=clause_number,
                    clause_title=clause_title,
                    heading_hierarchy=heading_hierarchy,
                    structure_type=StructureType.PARAGRAPH,
                )
            )

        return chunks

    def _split_text(self, text: str) -> list[str]:
        """Split text into chunks at sentence boundaries."""
        parts = []
        current = ""

        # Split by sentences (roughly)
        sentences = text.replace(". ", ".\n").split("\n")

        for sentence in sentences:
            if len(current) + len(sentence) > self.max_chars:
                if current:
                    parts.append(current.strip())
                current = sentence
            else:
                current = current + " " + sentence if current else sentence

        if current:
            parts.append(current.strip())

        return parts

    def _create_chunk(
        self,
        content: str,
        document_id: str,
        contribution_number: str,
        meeting_id: str | None,
        clause_number: str | None,
        clause_title: str | None,
        heading_hierarchy: list[str],
        structure_type: StructureType,
    ) -> Chunk:
        """Create a Chunk object."""
        chunk_id = str(uuid.uuid4())

        metadata = ChunkMetadata(
            document_id=document_id,
            contribution_number=contribution_number,
            meeting_id=meeting_id,
            clause_number=clause_number,
            clause_title=clause_title,
            structure_type=structure_type,
            heading_hierarchy=heading_hierarchy,
        )

        return Chunk(
            id=chunk_id,
            content=content,
            metadata=metadata,
            token_count=self.estimate_token_count(content),
        )

    def _get_primary_structure_type(
        self,
        elements: list[StructureElement],
    ) -> StructureType:
        """Determine the primary structure type of a section."""
        if not elements:
            return StructureType.PARAGRAPH

        # If starts with heading, use that
        if elements[0].heading_level is not None:
            return elements[0].structure_type

        # Otherwise, use most common type
        types = [el.structure_type for el in elements]
        return max(set(types), key=types.count)

    def _get_primary_structure_type_from_content(
        self,
        content: list[str],
    ) -> StructureType:
        """Get structure type from content list (fallback)."""
        return StructureType.PARAGRAPH
