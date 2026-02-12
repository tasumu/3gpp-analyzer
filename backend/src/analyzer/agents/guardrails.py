"""Guardrail callbacks for ADK agents.

Provides safety mechanisms including:
- Iteration limits to prevent infinite tool-calling loops
- Tool argument validation
"""

import logging
from typing import Any

from google.adk.agents.callback_context import CallbackContext
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.adk.tools.base_tool import BaseTool
from google.adk.tools.tool_context import ToolContext
from google.genai.types import Content, Part

logger = logging.getLogger(__name__)

# State key used to track LLM call count within a session
_LLM_CALL_COUNT_KEY = "_llm_call_count"


def create_iteration_limit_callback(
    max_calls: int = 25,
) -> "callable":
    """Create a before_model_callback that limits LLM invocations.

    Prevents infinite loops by counting LLM calls and stopping the agent
    when the limit is reached.

    Args:
        max_calls: Maximum number of LLM calls allowed per run. Default: 25.

    Returns:
        A callback function compatible with LlmAgent.before_model_callback.
    """

    def _iteration_limit_callback(
        callback_context: CallbackContext,
        llm_request: LlmRequest,
    ) -> LlmResponse | None:
        count = callback_context.state.get(_LLM_CALL_COUNT_KEY, 0)
        count += 1
        callback_context.state[_LLM_CALL_COUNT_KEY] = count

        if count > max_calls:
            logger.warning(
                f"Agent '{callback_context.agent_name}' hit iteration limit "
                f"({max_calls} LLM calls). Forcing termination."
            )
            return LlmResponse(
                content=Content(
                    parts=[
                        Part(
                            text=(
                                "Investigation limit reached. "
                                "Synthesizing findings from evidence gathered so far."
                            )
                        )
                    ],
                    role="model",
                ),
                turn_complete=True,
            )

        return None

    return _iteration_limit_callback


def validate_tool_args(
    tool: BaseTool,
    args: dict[str, Any],
    tool_context: ToolContext,
) -> dict | None:
    """Validate tool arguments before execution.

    Checks:
    - page_size is within reasonable bounds
    - top_k is within reasonable bounds

    Args:
        tool: The tool about to be called.
        args: The arguments the LLM provided.
        tool_context: ADK tool context.

    Returns:
        None to allow the call, or a dict to block with an error message.
    """
    tool_name = tool.name

    # Validate page_size
    if "page_size" in args:
        page_size = args.get("page_size", 50)
        if isinstance(page_size, (int, float)) and page_size > 200:
            logger.warning(
                f"Tool '{tool_name}': page_size={page_size} exceeds maximum. Clamping to 200."
            )
            args["page_size"] = 200

    # Validate top_k
    if "top_k" in args:
        top_k = args.get("top_k", 10)
        if isinstance(top_k, (int, float)) and top_k > 50:
            logger.warning(f"Tool '{tool_name}': top_k={top_k} exceeds maximum. Clamping to 50.")
            args["top_k"] = 50

    return None
