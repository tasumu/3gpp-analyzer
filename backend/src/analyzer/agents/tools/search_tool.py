"""Search tool for RAG-based evidence retrieval."""

from google.genai import types


def create_search_tool() -> types.Tool:
    """
    Create search_evidence tool for RAG search.

    This tool wraps EvidenceProvider.search() for use in Function Calling.

    Returns:
        Tool definition for search_evidence.
    """
    return types.Tool(
        function_declarations=[
            types.FunctionDeclaration(
                name="search_evidence",
                description=(
                    "Search for relevant evidence from 3GPP contribution documents. "
                    "Use this tool to find information related to a specific question or topic. "
                    "Returns excerpts from documents with citation information."
                ),
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "query": types.Schema(
                            type=types.Type.STRING,
                            description=(
                                "The search query. Be specific and include relevant "
                                "technical terms. Example: 'UE power saving requirements for 5G NR'"
                            ),
                        ),
                        "meeting_id": types.Schema(
                            type=types.Type.STRING,
                            description=(
                                "Optional: Filter results to a specific meeting. "
                                "Format: 'SA2#162' or 'RAN1#100'. "
                                "Use this to narrow search to a particular meeting's documents."
                            ),
                        ),
                        "contribution_number": types.Schema(
                            type=types.Type.STRING,
                            description=(
                                "Optional: Filter results to a specific contribution. "
                                "Format: 'S2-2401234'. "
                                "Use this when searching within a known document."
                            ),
                        ),
                        "document_id": types.Schema(
                            type=types.Type.STRING,
                            description=(
                                "Optional: Filter results to a specific document by its ID. "
                                "Use when you have the exact document identifier."
                            ),
                        ),
                        "top_k": types.Schema(
                            type=types.Type.INTEGER,
                            description=(
                                "Number of results to return. Default: 10. "
                                "Increase for broader searches, decrease for focused queries."
                            ),
                        ),
                    },
                    required=["query"],
                ),
            )
        ]
    )
