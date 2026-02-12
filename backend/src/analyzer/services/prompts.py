"""Prompt templates for analysis."""

# ruff: noqa: E501
# Prompt templates contain long lines by design

# Language-specific instructions for analysis output
LANGUAGE_INSTRUCTIONS = {
    "ja": """
Output Language: Japanese (日本語)
- Write the summary, change descriptions, and issue descriptions in Japanese
- Technical terms (3GPP terminology, clause numbers, specification references) should remain in English
- Evidence citations remain in the original document language (do not translate)
""",
    "en": """
Output Language: English
- Write the summary, change descriptions, and issue descriptions in English
- All technical terms should be in English
- Evidence citations remain in the original document language (do not translate)
""",
}


# Custom analysis prompts
def get_custom_analysis_system_prompt(language: str = "ja") -> str:
    """Get custom analysis system prompt with language instruction."""
    language_instruction = LANGUAGE_INSTRUCTIONS.get(language, LANGUAGE_INSTRUCTIONS["ja"])
    return f"""You are an expert analyst of 3GPP standardization documents.
Your task is to analyze a document based on the user's specific question or perspective.

Guidelines:
1. Focus on answering the user's specific question or analyzing from their requested perspective
2. Reference specific clause/section numbers when providing evidence
3. Be thorough but focused on what the user asked
4. Include relevant evidence from the document to support your answer
5. If the question cannot be answered from the document content, explain what information is missing
{language_instruction}
Provide a comprehensive answer that directly addresses the user's question.
"""


CUSTOM_ANALYSIS_USER_PROMPT = """Analyze the following 3GPP contribution document based on the user's question.

## Document Information
- Contribution Number: {contribution_number}
- Title: {title}
- Meeting: {meeting}
- Source: {source}

## User's Question/Perspective
{custom_prompt}

## Document Content (organized by sections)

{evidence_content}

---

Please provide a comprehensive answer to the user's question, citing relevant sections from the document.
"""
