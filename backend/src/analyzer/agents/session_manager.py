"""Global session service manager for ADK agents.

Provides a shared InMemorySessionService instance to maintain
conversation history across multiple agent invocations.
"""

from google.adk.sessions import InMemorySessionService

# Singleton session service instance
_session_service: InMemorySessionService | None = None


def get_session_service() -> InMemorySessionService:
    """
    Get the global session service instance.

    Returns:
        Shared InMemorySessionService instance.

    Note:
        - Sessions are stored in memory and lost on server restart
        - For production with multiple instances, consider DatabaseSessionService
    """
    global _session_service
    if _session_service is None:
        _session_service = InMemorySessionService()
    return _session_service


def reset_session_service() -> None:
    """
    Reset the session service (mainly for testing).

    Warning:
        This will clear all sessions and conversation history.
    """
    global _session_service
    _session_service = None
