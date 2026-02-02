"""Document tools for meeting analysis agents."""

from google.genai import types


def create_document_tools() -> types.Tool:
    """
    Create document-related tools for meeting analysis.

    These tools allow agents to:
    - List documents in a meeting
    - Get document summary

    Returns:
        Tool definition with multiple function declarations.
    """
    return types.Tool(
        function_declarations=[
            types.FunctionDeclaration(
                name="list_meeting_documents",
                description=(
                    "List all indexed documents (contributions) in a specific meeting. "
                    "Use this to get an overview of what documents are available for analysis."
                ),
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "meeting_id": types.Schema(
                            type=types.Type.STRING,
                            description=(
                                "The meeting ID to list documents for. "
                                "Format: 'SA2#162' or 'RAN1#100'."
                            ),
                        ),
                        "limit": types.Schema(
                            type=types.Type.INTEGER,
                            description=(
                                "Maximum number of documents to return. Default: 100. "
                                "Use a lower number if you only need a sample."
                            ),
                        ),
                    },
                    required=["meeting_id"],
                ),
            ),
            types.FunctionDeclaration(
                name="get_document_summary",
                description=(
                    "Get the summary of a specific document. "
                    "Returns the pre-computed analysis summary if available, "
                    "or basic document metadata if not analyzed yet."
                ),
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "document_id": types.Schema(
                            type=types.Type.STRING,
                            description=(
                                "The document ID to get summary for. "
                                "This is typically the contribution number."
                            ),
                        ),
                    },
                    required=["document_id"],
                ),
            ),
            types.FunctionDeclaration(
                name="get_document_content",
                description=(
                    "Get the full content of a specific document as organized chunks. "
                    "Use this when you need to read the complete document content."
                ),
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "document_id": types.Schema(
                            type=types.Type.STRING,
                            description="The document ID to get content for.",
                        ),
                        "max_chunks": types.Schema(
                            type=types.Type.INTEGER,
                            description="Maximum number of chunks to return. Default: 50.",
                        ),
                    },
                    required=["document_id"],
                ),
            ),
        ]
    )
