"""Agent tools for Function Calling."""

from analyzer.agents.tools.document_tool import create_document_tools
from analyzer.agents.tools.search_tool import create_search_tool

__all__ = ["create_search_tool", "create_document_tools"]
