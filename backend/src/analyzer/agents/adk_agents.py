"""ADK-based agent factory functions and runner."""

import logging
import uuid
from collections.abc import AsyncGenerator
from typing import Any

from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai.types import Content, Part

from analyzer.agents.context import AgentToolContext, set_current_agent_context
from analyzer.agents.tools.adk_document_tools import (
    get_document_content,
    get_document_summary,
    list_meeting_documents,
)
from analyzer.agents.tools.adk_search_tool import search_evidence
from analyzer.models.evidence import Evidence

logger = logging.getLogger(__name__)

APP_NAME = "3gpp-analyzer"


def create_qa_agent(
    model: str = "gemini-3-pro-preview",
    scope: str = "global",
    scope_id: str | None = None,
    language: str = "ja",
) -> LlmAgent:
    """
    Create a Q&A agent for answering questions about 3GPP documents.

    Args:
        model: LLM model name.
        scope: Search scope (document, meeting, or global).
        scope_id: Scope identifier (document_id or meeting_id).
        language: Response language (ja or en).

    Returns:
        Configured LlmAgent instance.
    """
    # Build system instruction
    scope_instructions = {
        "document": (
            f"You are answering questions about a specific 3GPP contribution document "
            f"(ID: {scope_id}). Focus your search and answers on this document only."
        ),
        "meeting": (
            f"You are answering questions about 3GPP meeting {scope_id}. "
            f"Your search scope includes all contributions submitted to this meeting. "
            f"When searching, always include the meeting_id filter."
        ),
        "global": (
            "You are answering questions about 3GPP standardization documents. "
            "You have access to all indexed contributions across multiple meetings. "
            "Search broadly to find relevant information."
        ),
    }

    lang_instructions = {
        "ja": (
            "回答は日本語で行ってください。"
            "技術用語（3GPP用語、仕様書番号、条項番号など）は英語のまま使用してください。"
        ),
        "en": "Respond in English. Use standard 3GPP terminology.",
    }

    scope_text = scope_instructions.get(scope, scope_instructions["global"])
    lang_text = lang_instructions.get(language, lang_instructions["ja"])

    # Scope-specific search instruction
    scope_search_instruction = ""
    if scope == "meeting" and scope_id:
        scope_search_instruction = f"- Always include meeting_id='{scope_id}' in your searches"
    elif scope == "document" and scope_id:
        scope_search_instruction = f"- Always include document_id='{scope_id}' in your searches"

    instruction = f"""You are an expert analyst for 3GPP standardization documents.

{scope_text}

## Instructions

1. Use the search_evidence tool to find relevant information from the documents
2. Always cite your sources with contribution numbers and clause numbers
3. If you cannot find sufficient information, clearly state that
4. Be precise and technical in your answers
5. If the question is ambiguous, make reasonable assumptions and state them

## Search Guidelines

- Use specific technical terms in your search queries
- If initial search doesn't yield results, try alternative phrasings
- For complex questions, break them down into multiple searches
{scope_search_instruction}

## Response Format

{lang_text}

Structure your response as:
1. Direct answer to the question
2. Supporting evidence with citations
3. Any caveats or limitations in the available information

Example citation format: [S2-2401234, Clause 5.2.1]
"""

    return LlmAgent(
        model=model,
        name="qa_agent",
        description="Q&A agent for answering questions about 3GPP documents",
        instruction=instruction,
        tools=[search_evidence],
    )


def create_meeting_report_agent(
    meeting_id: str,
    model: str = "gemini-3-pro-preview",
    language: str = "ja",
    custom_prompt: str | None = None,
) -> LlmAgent:
    """
    Create a meeting report agent for comprehensive meeting analysis.

    Args:
        meeting_id: Target meeting ID.
        model: LLM model name.
        language: Response language (ja or en).
        custom_prompt: Optional custom analysis focus.

    Returns:
        Configured LlmAgent instance.
    """
    lang_instructions = {
        "ja": (
            "レポートは日本語で作成してください。"
            "技術用語（3GPP用語、仕様書番号、条項番号など）は英語のまま使用してください。"
        ),
        "en": "Write the report in English. Use standard 3GPP terminology.",
    }
    lang_text = lang_instructions.get(language, lang_instructions["ja"])

    custom_instruction = ""
    if custom_prompt:
        custom_instruction = f"""
## Custom Analysis Focus
The user has requested the following specific focus for this report:
"{custom_prompt}"

Incorporate this perspective throughout your analysis.
"""

    instruction = f"""You are an expert 3GPP standardization analyst \
creating a comprehensive meeting report.

## Meeting: {meeting_id}

## Your Task
Analyze the meeting's contributions and create a comprehensive report covering:
1. **Overview**: High-level summary of the meeting's focus and outcomes
2. **Key Topics**: Major themes and discussion points
3. **Notable Contributions**: Documents that are particularly important or controversial
4. **Technical Trends**: Emerging patterns or directions
5. **Potential Conflicts**: Competing proposals or disagreements
{custom_instruction}

## Available Tools

1. **search_evidence**: Search for specific topics across all meeting documents
   - Use for: Finding information about specific technical topics
   - Always search with meeting_id='{meeting_id}'

2. **list_meeting_documents**: Get the list of all contributions in the meeting
   - Use for: Getting an overview of submissions

3. **get_document_summary**: Get the summary of a specific contribution
   - Use for: Understanding individual document proposals

4. **get_document_content**: Get the full content of a document
   - Use for: Deep-diving into specific documents

## Guidelines

- Start by listing the meeting documents to understand the scope
- Use search_evidence to explore specific topics of interest
- Cross-reference multiple documents when analyzing trends
- Cite specific contributions when making claims
- Be objective and balanced in your analysis

## Output Format

{lang_text}

Structure your analysis clearly with sections and bullet points.
Always include contribution numbers when referencing documents: [S2-2401234]
"""

    return LlmAgent(
        model=model,
        name="meeting_report_agent",
        description="Agent for generating comprehensive meeting reports",
        instruction=instruction,
        tools=[
            search_evidence,
            list_meeting_documents,
            get_document_summary,
            get_document_content,
        ],
    )


class ADKAgentRunner:
    """
    Runner wrapper for ADK agents with context management.

    Handles session creation, context injection, and evidence tracking.
    """

    def __init__(
        self,
        agent: LlmAgent,
        agent_context: AgentToolContext,
    ):
        """
        Initialize the runner.

        Args:
            agent: The LlmAgent to run.
            agent_context: Context with services and configuration.
        """
        self.agent = agent
        self.agent_context = agent_context
        self.session_service = InMemorySessionService()
        self.runner = Runner(
            agent=agent,
            app_name=APP_NAME,
            session_service=self.session_service,
        )

    async def run(
        self,
        user_input: str,
        user_id: str = "default_user",
        session_id: str | None = None,
    ) -> tuple[str, list[Evidence]]:
        """
        Run the agent and return response with evidences.

        Args:
            user_input: User's question or request.
            user_id: User identifier.
            session_id: Session identifier (auto-generated if not provided).

        Returns:
            Tuple of (response_text, used_evidences).
        """
        # Reset evidence tracking
        self.agent_context.reset_evidences()

        # Set context in contextvar (avoids pickle issues with session state)
        set_current_agent_context(self.agent_context)

        try:
            # Create session without unpicklable objects in state
            session_id = session_id or str(uuid.uuid4())
            await self.session_service.create_session(
                app_name=APP_NAME,
                user_id=user_id,
                session_id=session_id,
                state={},  # Empty state - context is in contextvar
            )

            # Build message
            user_message = Content(parts=[Part(text=user_input)])

            # Run agent
            full_text = ""
            async for event in self.runner.run_async(
                user_id=user_id,
                session_id=session_id,
                new_message=user_message,
            ):
                if event.is_final_response():
                    if event.content and event.content.parts:
                        for part in event.content.parts:
                            if hasattr(part, "text") and part.text:
                                full_text = part.text

            return full_text, self.agent_context.get_unique_evidences()
        finally:
            # Reset contextvar
            set_current_agent_context(None)

    async def run_stream(
        self,
        user_input: str,
        user_id: str = "default_user",
        session_id: str | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """
        Run the agent with streaming response.

        Yields events as they become available including partial responses
        and the final result.

        Args:
            user_input: User's question or request.
            user_id: User identifier.
            session_id: Session identifier.

        Yields:
            Event dictionaries with type and content.
        """
        # Reset evidence tracking
        self.agent_context.reset_evidences()

        # Set context in contextvar (avoids pickle issues with session state)
        set_current_agent_context(self.agent_context)

        try:
            # Create session without unpicklable objects in state
            session_id = session_id or str(uuid.uuid4())
            await self.session_service.create_session(
                app_name=APP_NAME,
                user_id=user_id,
                session_id=session_id,
                state={},  # Empty state - context is in contextvar
            )

            # Build message
            user_message = Content(parts=[Part(text=user_input)])

            # Run agent with streaming
            full_text = ""
            async for event in self.runner.run_async(
                user_id=user_id,
                session_id=session_id,
                new_message=user_message,
            ):
                # Yield partial text updates
                if hasattr(event, "partial") and event.partial:
                    if event.content and event.content.parts:
                        for part in event.content.parts:
                            if hasattr(part, "text") and part.text:
                                yield {"type": "chunk", "content": part.text}

                # Handle final response
                if event.is_final_response():
                    if event.content and event.content.parts:
                        for part in event.content.parts:
                            if hasattr(part, "text") and part.text:
                                full_text = part.text

            # Yield final result with evidences
            yield {
                "type": "done",
                "content": full_text,
                "evidences": self.agent_context.get_unique_evidences(),
            }
        finally:
            # Reset contextvar
            set_current_agent_context(None)
