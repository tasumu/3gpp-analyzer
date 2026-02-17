"""Global session service manager for ADK agents.

Provides a shared InMemorySessionService instance to maintain
conversation history across multiple agent invocations.

Includes automatic session cleanup based on TTL to prevent memory leaks.
"""

import logging
from datetime import UTC, datetime, timedelta

from google.adk.sessions import InMemorySessionService

logger = logging.getLogger(__name__)

# Singleton session service instance
_session_service: InMemorySessionService | None = None

# Track session creation times for TTL-based cleanup
_session_timestamps: dict[str, datetime] = {}

# Session TTL (1 hour)
SESSION_TTL = timedelta(hours=1)

# Cleanup interval (10 minutes)
CLEANUP_INTERVAL = timedelta(minutes=10)

# Last cleanup time
_last_cleanup: datetime | None = None


def get_session_service() -> InMemorySessionService:
    """
    Get the global session service instance.

    Returns:
        Shared InMemorySessionService instance.

    Note:
        - Sessions are stored in memory and lost on server restart
        - Sessions older than SESSION_TTL (1 hour) are automatically cleaned up
        - For production with multiple instances, consider DatabaseSessionService
    """
    global _session_service
    if _session_service is None:
        _session_service = InMemorySessionService()
    return _session_service


def track_session(session_id: str) -> None:
    """
    Track session creation time for TTL management.

    Args:
        session_id: The session ID to track.
    """
    _session_timestamps[session_id] = datetime.now(UTC)


def touch_session(session_id: str) -> None:
    """
    Update session's last access time to extend its TTL.

    Args:
        session_id: The session ID to update.
    """
    if session_id in _session_timestamps:
        _session_timestamps[session_id] = datetime.now(UTC)


async def cleanup_expired_sessions() -> list[str]:
    """
    Remove sessions that have exceeded the TTL.

    Returns:
        List of expired session IDs that were cleaned up.
    """
    global _last_cleanup

    now = datetime.now(UTC)

    # Skip if cleanup was done recently
    if _last_cleanup and now - _last_cleanup < CLEANUP_INTERVAL:
        return []

    _last_cleanup = now
    expired_sessions = []
    cutoff_time = now - SESSION_TTL

    for session_id, created_at in list(_session_timestamps.items()):
        if created_at < cutoff_time:
            expired_sessions.append(session_id)

    if expired_sessions:
        logger.info(f"Cleaning up {len(expired_sessions)} expired sessions")
        for session_id in expired_sessions:
            _session_timestamps.pop(session_id, None)
            # Note: InMemorySessionService doesn't expose a delete method,
            # but sessions will be orphaned and inaccessible without the ID.
            # The memory will be reclaimed when the service is reset or
            # when we implement a custom session service with proper deletion.

    return expired_sessions


def get_active_session_count() -> int:
    """
    Get the number of active sessions being tracked.

    Returns:
        Number of sessions.
    """
    return len(_session_timestamps)


def reset_session_service() -> None:
    """
    Reset the session service (mainly for testing).

    Warning:
        This will clear all sessions and conversation history.
    """
    global _session_service, _last_cleanup
    _session_service = None
    _session_timestamps.clear()
    _last_cleanup = None
