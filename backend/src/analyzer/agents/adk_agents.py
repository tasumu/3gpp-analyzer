"""ADK-based agent factory functions and runner."""

import asyncio
import logging
import uuid
from collections.abc import AsyncGenerator
from typing import Any

from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.tools.agent_tool import AgentTool
from google.genai.types import Content, Part
from pydantic import BaseModel, Field

from analyzer.agents.context import (
    AgentToolContext,
    reset_agent_context,
    set_current_agent_context,
)
from analyzer.agents.guardrails import create_iteration_limit_callback, validate_tool_args
from analyzer.agents.session_manager import (
    cleanup_expired_sessions,
    get_session_service,
    touch_session,
    track_session,
)
from analyzer.agents.tools.adk_agentic_tools import (
    list_meeting_attachments,
    list_meeting_documents_enhanced,
    read_attachment,
)
from analyzer.agents.tools.adk_document_tools import (
    get_document_content,
    get_document_summary,
)
from analyzer.agents.tools.adk_search_tool import search_evidence
from analyzer.models.evidence import Evidence

logger = logging.getLogger(__name__)

APP_NAME = "3gpp-analyzer"


class InvestigationInput(BaseModel):
    """Input schema for the document investigation sub-agent."""

    document_id: str = Field(description="The document ID to investigate.")
    investigation_query: str = Field(
        description=(
            "What to look for in this document. Be specific about what information you need. "
            "Example: 'What changes does this document propose to DRX parameters?'"
        ),
    )
    contribution_number: str | None = Field(
        default=None,
        description=(
            "The contribution number of the document (e.g., 'S2-2401234'). "
            "Pass this from list_meeting_documents_enhanced results."
        ),
    )
    document_title: str | None = Field(
        default=None,
        description=(
            "The title of the document. Pass this from list_meeting_documents_enhanced results."
        ),
    )


# Agent execution limits
MAIN_AGENT_MAX_LLM_CALLS = 25
SUB_AGENT_MAX_LLM_CALLS = 5
AGENT_TIMEOUT_SECONDS = 300  # 5 minutes


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
            "\n\n"
            "**CRITICAL: Search queries MUST be in English.**\n"
            "3GPP documents are written in English. When calling search_evidence, "
            "always translate the user's Japanese question into English technical terms.\n"
            "Example:\n"
            "- User question: '5Gのハンドオーバー手順について教えて'\n"
            "- Search query: 'handover procedure 5G NR mobility management'"
        ),
        "en": "Respond in English. Use standard 3GPP terminology.",
    }

    # Refusal instructions for insufficient search results
    lang_refusal_instructions = {
        "ja": """
検索結果が0件、または関連性が低い場合:
1. 「申し訳ございませんが、インデックス済みの寄書にはご質問に関する情報が
   見つかりませんでした。」と明示してください
2. 以下の提案を行ってください:
   - 異なる技術用語やシノニムを試す
   - より広い検索範囲を使用する
   - 具体的な仕様書番号がわかれば含める
3. **重要**: 事前学習知識から回答を生成しないでください
4. 見つかった情報が限定的な場合は、その旨を明示してください
""",
        "en": """
When search returns 0 results or low relevance:
1. State clearly: "I apologize, but I could not find information about this
   question in the indexed documents."
2. Provide these suggestions:
   - Try different technical terms or synonyms
   - Use a broader search scope
   - Include specific specification numbers if known
3. **CRITICAL**: Do NOT generate answers from pre-trained knowledge
4. If limited information is found, state this explicitly
""",
    }

    scope_text = scope_instructions.get(scope, scope_instructions["global"])
    lang_text = lang_instructions.get(language, lang_instructions["ja"])
    refusal_text = lang_refusal_instructions.get(language, lang_refusal_instructions["ja"])

    # Scope-specific search instruction
    scope_search_instruction = ""
    if scope == "meeting" and scope_id:
        scope_search_instruction = f"- Always include meeting_id='{scope_id}' in your searches"
    elif scope == "document" and scope_id:
        scope_search_instruction = f"- Always include document_id='{scope_id}' in your searches"

    instruction = f"""You are an expert analyst for 3GPP standardization documents.

{scope_text}

## CRITICAL CONSTRAINT: RAG-Only Responses

**YOU MUST ONLY answer based on search results returned by the search_evidence tool.**

This system has access to a specific set of indexed 3GPP documents. You MUST NOT:
- Use pre-trained knowledge to answer questions about 3GPP specifications
- Make assumptions about standards based on general knowledge
- Provide technical information that was not found in the search results

YOU MUST:
- Base ALL answers exclusively on search_evidence results
- Refuse to answer when search returns no results (count: 0) or insufficient results
- Clearly state when information is not available in the indexed documents

## Instructions

1. **ALWAYS call search_evidence** at least once for every question.
   This ensures your answer is grounded in the actual document content.
2. **ALWAYS cite sources with bold markdown citations**
   - Format: **[S2-2401234, Clause 5.2.1]** or **[S2-2401234]**
   - Every paragraph with facts MUST include at least one citation
   - Multiple sources: **[S2-2401234]**, **[S2-2401235]**
3. If you cannot find sufficient information, clearly state that
4. Be precise and technical in your answers
5. If the question is ambiguous, make reasonable assumptions and state them

## Search Guidelines

**IMPORTANT: Search Query Optimization**

1. **Always use English technical terms** for the search query
2. **Extract key 3GPP terminology**: spec numbers, acronyms (RRC, NAS, PDU), release info
3. **Formulate queries as technical descriptions**:
   - Bad: "What is power saving?"
   - Good: "UE power saving DRX configuration connected mode"
4. **If initial search returns few results**: try synonyms, broader terms, or spec numbers
5. For complex questions, break them down into multiple searches
{scope_search_instruction}

## Handling Insufficient Search Results

{refusal_text}

## Response Format

{lang_text}

Structure your response as:
1. Direct answer to the question (ONLY if search results are sufficient)
2. Supporting evidence with citations
3. Any caveats or limitations in the available information

"""

    return LlmAgent(
        model=model,
        name="qa_agent",
        description="Q&A agent for answering questions about 3GPP documents",
        instruction=instruction,
        tools=[search_evidence],
    )


def create_agentic_search_agent(
    meeting_id: str,
    model: str = "gemini-3-pro-preview",
    language: str = "ja",
) -> LlmAgent:
    """
    Create an agentic search agent for multi-step document investigation.

    Unlike the RAG-only Q&A agent, this agent plans its investigation,
    discovers relevant documents from meeting metadata, and delegates
    detailed document analysis to a sub-agent.

    Args:
        meeting_id: Target meeting ID (e.g., 'SA2#162').
        model: LLM model name.
        language: Response language (ja or en).

    Returns:
        Configured LlmAgent instance with planning capabilities.
    """
    lang_instructions = {
        "ja": (
            "回答は日本語で行ってください。"
            "技術用語（3GPP用語、仕様書番号、条項番号など）は英語のまま使用してください。"
            "\n\n"
            "**CRITICAL: search_evidence や list_meeting_documents の検索クエリは"
            "必ず英語で行ってください。**\n"
            "3GPP文書は英語で書かれています。ユーザーの日本語の質問を"
            "英語の技術用語に変換してから検索してください。"
        ),
        "en": "Respond in English. Use standard 3GPP terminology.",
    }

    lang_refusal = {
        "ja": (
            "調査の結果、関連する情報が見つからなかった場合は、"
            "その旨を明示し、別のアプローチを提案してください。"
            "事前学習知識からの回答は生成しないでください。"
        ),
        "en": (
            "If investigation yields no relevant results, state this clearly "
            "and suggest alternative approaches. "
            "Do NOT generate answers from pre-trained knowledge."
        ),
    }

    lang_text = lang_instructions.get(language, lang_instructions["ja"])
    refusal_text = lang_refusal.get(language, lang_refusal["ja"])

    instruction = f"""You are an expert investigative analyst for 3GPP standardization \
documents in meeting {meeting_id}.

## Your Role

You are an **agentic researcher** — you don't just search, you **plan and investigate**.
Your goal is to provide thorough, well-researched answers by exploring the meeting's
documents systematically.

## Investigation Workflow

Follow this workflow for each question:

### 1. Analyze the Query
- Understand what the user is asking
- Identify key topics, technical terms, and the type of answer needed
- Determine if the user wants: specific technical details, decision outcomes,
  document comparisons, trend analysis, etc.

### 2. Check Meeting Reference Documents
Before planning, gather structural context about the meeting:
- Use **list_meeting_documents_enhanced** with search_text="Agenda" and \
include_non_indexed=True to find Agenda documents
- Use **list_meeting_documents_enhanced** with search_text="TDoc_List" and \
include_non_indexed=True to find TDoc List spreadsheets
- Use **list_meeting_attachments** to check for user-uploaded supplementary files

For documents found:
- If the document is a .docx (indexed or not): use **investigate_document** to read and \
understand the meeting structure. It works for both indexed and non-indexed .docx documents.
- If the document is .xlsx or other non-.docx format: check user attachments for this data
- If user attachments exist: use **read_attachment** to read their content

Use the Agenda information to identify which agenda items relate to the user's question.

### 3. Plan Your Investigation
Briefly state your investigation plan before executing it. Consider:
- Which agenda items relate to the user's question (from Step 2)
- Which documents might be relevant (by topic, by agenda item, by source company)
- Whether to search broadly first or target specific documents
- Whether decision status matters (Agreed, Approved, Revised documents)

### 4. Discover Relevant Documents
Use **list_meeting_documents_enhanced** to explore the meeting's contributions:
- First call without search_text to get an overview (page_size=50, check total count)
- Use search_text to filter by topic keywords in titles/filenames
- Note contribution numbers, titles, and sources of relevant documents

### 5. Investigate Key Documents
For documents you've identified as highly relevant:
- First use **get_document_summary** to quickly check the overview. If `has_analysis` is false
  or you need deeper investigation, use **investigate_document** for detailed analysis
  (this delegates to a specialized sub-agent that reads the full content).

### 6. Supplement with RAG Search
Use **search_evidence** to:
- Find information that might not be obvious from document titles
- Verify findings from document investigation
- Discover connections between documents
- Fill gaps in your investigation

### 7. Synthesize and Respond
- Combine findings from all sources into a comprehensive response
- Do NOT over-summarize: include important details, specific proposals, \
and technical specifics found during investigation
- Omit only information that is clearly irrelevant to the question
- **ALWAYS cite sources with bold markdown citations**
- Format: **[S2-2401234, Clause 5.2.1]** or **[S2-2401234]**
- Every paragraph with facts MUST include at least one citation
- Multiple sources: **[S2-2401234]**, **[S2-2401235]**
- If documents contain conflicting information, note the discrepancies
- Distinguish between agreed/approved outcomes and proposals

## Available Tools

1. **list_meeting_documents_enhanced**: List/search documents in the meeting
   - Use search_text for keyword filtering (always in English)
   - Use include_non_indexed=True to discover Agenda and TDoc_List documents
   - Supports pagination (page, page_size)
   - Always use meeting_id='{meeting_id}'

2. **search_evidence**: RAG vector search across document content
   - Useful for semantic similarity search
   - Always use meeting_id='{meeting_id}' filter
   - Search queries MUST be in English

3. **get_document_summary**: Get pre-computed summary of a document
   - Quick overview without reading full content
   - Use for initial assessment of relevance

4. **investigate_document**: Deep investigation of a specific document
   - Delegates to a specialized sub-agent
   - Provide a focused investigation_query
   - **Always pass contribution_number and document_title from list results**
   - Use for documents requiring detailed analysis

5. **list_meeting_attachments**: List user-uploaded supplementary files
   - Returns uploaded files for the meeting (e.g., Agenda, TDoc lists)
   - Always use meeting_id='{meeting_id}'

6. **read_attachment**: Read content of an uploaded attachment
   - Use attachment_id from list_meeting_attachments results
   - Useful for reading Agenda files, TDoc lists, or other supplementary documents

## Decision Status Inference

3GPP documents don't have explicit decision status in metadata. Infer from:
- Document titles may contain indicators (e.g., "Agreed", "Approved", "Revised")
- Content may describe decisions or conclusions
- Revision chains: later contribution numbers may supersede earlier ones
- When the user asks about agreed/approved outcomes, prioritize finding such indicators

## Constraints

{refusal_text}

## Response Format

{lang_text}

Structure your response clearly with sufficient detail:
1. Summary of your investigation approach (which documents you examined)
2. Main findings with citations — include specific proposals, \
parameter values, and technical details from the documents
3. Detailed analysis organized by topic — cover each relevant \
document's contribution, not just the overall conclusion
4. Comparison or relationships between documents if multiple are relevant
5. Conclusions and any caveats

IMPORTANT: Your answer should reflect the depth of your investigation. \
If you investigated 5 documents, the answer should cover findings from \
each relevant one, not just a 3-sentence summary. Include specific \
clauses, proposed changes, and technical details that users would find \
valuable. Avoid being overly brief.
"""

    # Create the document investigation sub-agent wrapped as an AgentTool.
    # Named "investigate_document" for backward compatibility with frontend tool name checks.
    investigation_agent = create_document_investigation_agent(
        language=language,
        model="gemini-3-flash-preview",
    )
    investigation_tool = AgentTool(agent=investigation_agent, skip_summarization=False)

    return LlmAgent(
        model=model,
        name="agentic_search_agent",
        description="Agentic search agent for multi-step document investigation",
        instruction=instruction,
        tools=[
            list_meeting_documents_enhanced,
            search_evidence,
            get_document_summary,
            investigation_tool,
            list_meeting_attachments,
            read_attachment,
        ],
        before_model_callback=create_iteration_limit_callback(MAIN_AGENT_MAX_LLM_CALLS),
        before_tool_callback=validate_tool_args,
    )


def create_document_investigation_agent(
    language: str = "ja",
    model: str = "gemini-3-flash-preview",
) -> LlmAgent:
    """
    Create a lightweight agent for investigating a specific document.

    This agent is wrapped with AgentTool by the agentic search agent.
    It receives document_id and investigation_query via input_schema,
    reads document content, and provides focused analysis.

    Args:
        language: Response language.
        model: LLM model name.

    Returns:
        Configured LlmAgent instance for document investigation.
    """
    lang_text = {
        "ja": "分析結果は日本語で回答してください。技術用語は英語のまま使用してください。",
        "en": "Respond in English with standard 3GPP terminology.",
    }.get(language, "分析結果は日本語で回答してください。技術用語は英語のまま使用してください。")

    instruction = f"""You are a document analyst investigating 3GPP contributions.

## Your Task
You will receive a JSON message containing:
- document_id: The document to investigate
- investigation_query: What to look for in the document
- contribution_number: (optional) The contribution reference
- document_title: (optional) The document title

Read and analyze the document content to answer the investigation query.
Focus on extracting specific, relevant information.

## Available Tools
1. **get_document_content**: Read the full document content (organized by sections)
   - Use the document_id from the input message
   - For indexed documents, returns all chunks with clause/page metadata
   - For non-indexed documents, falls back to reading the original .docx from storage

## Guidelines
- Read the full document content with get_document_content using the document_id from your input
- Provide specific details: clause numbers, page numbers, exact proposals
- Be thorough — include all relevant findings, not just a brief summary
- Report specific proposed changes, parameter values, and key technical \
points found in the document
- Only omit information that is clearly irrelevant to the query
- Cite clauses and page numbers: [Clause 5.2.1, Page 3]

## Response Format
{lang_text}
Provide a focused analysis answering the investigation query.
"""

    return LlmAgent(
        model=model,
        name="investigate_document",
        description=(
            "Deeply investigate a specific document to answer a question. "
            "Delegates to a sub-agent that reads the full document content and analyzes it. "
            "More thorough than get_document_summary but takes longer. "
            "Use for documents identified as particularly relevant. "
            "Always pass contribution_number and document_title from list results."
        ),
        instruction=instruction,
        input_schema=InvestigationInput,
        tools=[get_document_content],
        before_model_callback=create_iteration_limit_callback(SUB_AGENT_MAX_LLM_CALLS),
    )


def _summarize_tool_result(tool_name: str, response: dict | None) -> str:
    """Create a brief human-readable summary of a tool result for streaming."""
    if not response:
        return "No result"

    resp = response if isinstance(response, dict) else {}

    if "error" in resp:
        return f"Error: {resp['error']}"

    if tool_name == "list_meeting_documents_enhanced":
        total = resp.get("total", 0)
        returned = resp.get("returned", 0)
        return f"Found {total} documents (showing {returned})"

    if tool_name == "search_evidence":
        count = resp.get("count", 0)
        return f"{count} relevant results found"

    if tool_name == "get_document_summary":
        has_analysis = resp.get("has_analysis", False)
        cn = resp.get("contribution_number", "")
        return f"{cn}: {'Summary available' if has_analysis else 'No analysis available'}"

    if tool_name == "investigate_document":
        # AgentTool returns merged text wrapped in {'result': text}
        result_text = resp.get("result")
        if result_text:
            return f"Investigation complete ({len(str(result_text))} chars)"
        return "Investigation complete"

    if tool_name == "get_document_content":
        chunks = resp.get("total_chunks", 0)
        return f"Read {chunks} content sections"

    if tool_name == "list_meeting_attachments":
        total = resp.get("total", 0)
        return f"Found {total} uploaded attachments"

    if tool_name == "read_attachment":
        filename = resp.get("filename", "")
        length = resp.get("total_length", 0)
        return f"{filename}: Read {length} characters"

    return f"Completed ({len(str(resp))} chars)"


class ADKAgentRunner:
    """
    Runner wrapper for ADK agents with context management.

    Handles session creation, context injection, evidence tracking,
    and execution timeouts.
    """

    def __init__(
        self,
        agent: LlmAgent,
        agent_context: AgentToolContext,
        timeout_seconds: int = AGENT_TIMEOUT_SECONDS,
    ):
        """
        Initialize the runner.

        Args:
            agent: The LlmAgent to run.
            agent_context: Context with services and configuration.
            timeout_seconds: Maximum execution time in seconds.
        """
        self.agent = agent
        self.agent_context = agent_context
        self.timeout_seconds = timeout_seconds
        self.session_service = get_session_service()
        self.runner = Runner(
            agent=agent,
            app_name=APP_NAME,
            session_service=self.session_service,
        )

    async def _ensure_session(
        self,
        user_id: str,
        session_id: str,
    ) -> str:
        """Ensure a session exists, creating one if needed.

        Args:
            user_id: User identifier.
            session_id: Session identifier.

        Returns:
            The session_id (same as input).
        """
        await cleanup_expired_sessions()

        existing_session = await self.session_service.get_session(
            app_name=APP_NAME,
            user_id=user_id,
            session_id=session_id,
        )
        if existing_session is None:
            await self.session_service.create_session(
                app_name=APP_NAME,
                user_id=user_id,
                session_id=session_id,
                state={},  # Empty state - context is in contextvar
            )
            track_session(session_id)
            logger.debug(f"Created new session: {session_id}")
        else:
            touch_session(session_id)
            logger.debug(
                f"Reusing existing session: {session_id} with {len(existing_session.events)} events"
            )
        return session_id

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

        Raises:
            asyncio.TimeoutError: If execution exceeds timeout_seconds.
        """
        # Reset evidence tracking
        self.agent_context.reset_evidences()

        # Save and set context (token-based restore for safe nesting)
        token = set_current_agent_context(self.agent_context)

        try:
            session_id = session_id or str(uuid.uuid4())
            await self._ensure_session(user_id, session_id)

            user_message = Content(parts=[Part(text=user_input)])

            async def _execute() -> str:
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
                return full_text

            full_text = await asyncio.wait_for(_execute(), timeout=self.timeout_seconds)
            return full_text, self.agent_context.get_unique_evidences()
        except asyncio.TimeoutError:
            logger.error(f"Agent '{self.agent.name}' timed out after {self.timeout_seconds}s")
            raise
        finally:
            # Restore previous context (safe for nested sub-agent calls)
            reset_agent_context(token)

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

        # Save and set context (token-based restore for safe nesting)
        token = set_current_agent_context(self.agent_context)

        try:
            session_id = session_id or str(uuid.uuid4())
            await self._ensure_session(user_id, session_id)

            user_message = Content(parts=[Part(text=user_input)])

            # Run agent with streaming
            full_text = ""
            async for event in self.runner.run_async(
                user_id=user_id,
                session_id=session_id,
                new_message=user_message,
            ):
                # Detect function call events (tool invocations)
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        if hasattr(part, "function_call") and part.function_call:
                            fc = part.function_call
                            # Summarize args to avoid flooding the stream
                            args_summary = {}
                            if fc.args:
                                for k, v in fc.args.items():
                                    val = str(v)
                                    args_summary[k] = val[:100] + "..." if len(val) > 100 else val
                            yield {
                                "type": "tool_call",
                                "tool": fc.name,
                                "args": args_summary,
                            }
                        if hasattr(part, "function_response") and part.function_response:
                            fr = part.function_response
                            # Build a brief summary of the tool result
                            summary = _summarize_tool_result(fr.name, fr.response)
                            yield {
                                "type": "tool_result",
                                "tool": fr.name,
                                "summary": summary,
                            }

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
            # Restore previous context (safe for nested sub-agent calls)
            reset_agent_context(token)
