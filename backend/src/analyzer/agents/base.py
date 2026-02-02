"""Base agent class with Function Calling support for Phase 3."""

import logging
from abc import ABC, abstractmethod
from typing import Any

from google import genai
from google.genai import types

from analyzer.models.evidence import Evidence
from analyzer.providers.base import EvidenceProvider

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    Abstract base class for LLM agents with Function Calling.

    Uses Google GenAI SDK for Function Calling loop execution.
    Subclasses must implement get_tools() and get_system_prompt().
    """

    MAX_TOOL_CALLS = 10  # Maximum number of tool call iterations

    def __init__(
        self,
        evidence_provider: EvidenceProvider,
        project_id: str,
        location: str = "asia-northeast1",
        model: str = "gemini-2.5-pro",
    ):
        """
        Initialize BaseAgent.

        Args:
            evidence_provider: Provider for RAG search operations.
            project_id: GCP project ID.
            location: GCP region for Vertex AI.
            model: LLM model name.
        """
        self.evidence_provider = evidence_provider
        self.project_id = project_id
        self.location = location
        self.model = model

        # Initialize GenAI client
        self._client = genai.Client(
            vertexai=True,
            project=project_id,
            location=location,
        )

        # Track used evidences during execution
        self._used_evidences: list[Evidence] = []

    @abstractmethod
    def get_tools(self) -> list[types.Tool]:
        """Return list of tools available to the agent."""
        pass

    @abstractmethod
    def get_system_prompt(self, context: dict | None = None) -> str:
        """
        Return the system prompt for the agent.

        Args:
            context: Optional context dictionary for dynamic prompt generation.
        """
        pass

    def get_used_evidences(self) -> list[Evidence]:
        """Return list of evidences used during the last execution."""
        return self._used_evidences.copy()

    async def execute_tool(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        """
        Execute a tool by name with given arguments.

        Override in subclasses to add custom tools.

        Args:
            name: Tool name to execute.
            args: Tool arguments.

        Returns:
            Tool execution result as a dictionary.

        Raises:
            ValueError: If tool name is unknown.
        """
        if name == "search_evidence":
            return await self._execute_search(args)
        raise ValueError(f"Unknown tool: {name}")

    async def _execute_search(self, args: dict[str, Any]) -> dict[str, Any]:
        """
        Execute search_evidence tool.

        Args:
            args: Tool arguments containing query and optional filters.

        Returns:
            Search results with evidence list and count.
        """
        query = args.get("query", "")
        top_k = args.get("top_k", 10)

        # Build filters from optional arguments
        filters: dict[str, Any] = {}
        if args.get("meeting_id"):
            filters["meeting_id"] = args["meeting_id"]
        if args.get("contribution_number"):
            filters["contribution_number"] = args["contribution_number"]
        if args.get("document_id"):
            filters["document_id"] = args["document_id"]

        logger.info(
            f"Executing search_evidence: query='{query[:50]}...', "
            f"filters={filters}, top_k={top_k}"
        )

        evidences = await self.evidence_provider.search(
            query=query,
            filters=filters if filters else None,
            top_k=top_k,
        )

        # Track used evidences
        self._used_evidences.extend(evidences)

        # Convert to serializable format
        results = []
        for ev in evidences:
            results.append({
                "chunk_id": ev.chunk_id,
                "contribution_number": ev.contribution_number,
                "content": ev.content[:500] + "..." if len(ev.content) > 500 else ev.content,
                "clause_number": ev.clause_number,
                "clause_title": ev.clause_title,
                "page_number": ev.page_number,
                "relevance_score": ev.relevance_score,
            })

        return {
            "results": results,
            "count": len(results),
            "query": query,
        }

    async def run(
        self,
        user_input: str,
        context: dict | None = None,
    ) -> str:
        """
        Run the agent with Function Calling loop.

        Args:
            user_input: User's input/question.
            context: Optional context for dynamic system prompt.

        Returns:
            Agent's final text response.
        """
        # Reset used evidences
        self._used_evidences = []

        # Build initial content
        contents: list[types.Content] = [
            types.Content(
                role="user",
                parts=[types.Part.from_text(user_input)],
            )
        ]

        tools = self.get_tools()
        system_prompt = self.get_system_prompt(context)

        iteration = 0
        while iteration < self.MAX_TOOL_CALLS:
            iteration += 1

            logger.debug(f"Agent iteration {iteration}, model={self.model}")

            # Generate response
            response = self._client.models.generate_content(
                model=self.model,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    tools=tools if tools else None,
                ),
            )

            # Check for function calls
            candidate = response.candidates[0] if response.candidates else None
            if not candidate or not candidate.content:
                logger.warning("No content in response")
                return "Unable to generate response."

            content = candidate.content

            # Check if there are function calls
            function_calls = []
            for part in content.parts:
                if part.function_call:
                    function_calls.append(part.function_call)

            if not function_calls:
                # No function calls, return the text response
                text_parts = [p.text for p in content.parts if p.text]
                return "\n".join(text_parts) if text_parts else "No response generated."

            # Execute function calls and add results
            contents.append(content)

            tool_responses: list[types.Part] = []
            for fc in function_calls:
                try:
                    logger.info(f"Executing tool: {fc.name}")
                    result = await self.execute_tool(fc.name, dict(fc.args))
                    tool_responses.append(
                        types.Part.from_function_response(
                            name=fc.name,
                            response={"result": result},
                        )
                    )
                except Exception as e:
                    logger.error(f"Tool execution error: {fc.name} - {e}")
                    tool_responses.append(
                        types.Part.from_function_response(
                            name=fc.name,
                            response={"error": str(e)},
                        )
                    )

            contents.append(
                types.Content(
                    role="user",
                    parts=tool_responses,
                )
            )

        logger.warning(f"Max tool calls ({self.MAX_TOOL_CALLS}) reached")
        return "Maximum number of tool calls reached. Please try a simpler query."

    async def run_stream(
        self,
        user_input: str,
        context: dict | None = None,
    ):
        """
        Run the agent with streaming response.

        Yields text chunks as they become available.
        Note: Function calling may still happen internally before streaming final response.

        Args:
            user_input: User's input/question.
            context: Optional context for dynamic system prompt.

        Yields:
            Text chunks of the agent's response.
        """
        # For now, use non-streaming implementation and yield the full result
        # TODO: Implement proper streaming with function calling
        result = await self.run(user_input, context)
        yield result
