"""Rate limiting middleware using slowapi."""

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from analyzer.config import get_settings

settings = get_settings()


def get_rate_limit_key(request: Request) -> str:
    """
    Get rate limit key from request.

    Uses user ID if authenticated, otherwise falls back to IP address.
    """
    # Try to get user from auth header
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        try:
            # Import here to avoid circular dependency
            from analyzer.auth import verify_firebase_token

            token = auth_header.split("Bearer ")[1]
            user = verify_firebase_token(token)
            return f"user:{user.uid}"
        except Exception:
            # If token verification fails, fall back to IP
            pass

    # Fallback to IP address
    return get_remote_address(request)


# Create limiter instance
limiter = Limiter(
    key_func=get_rate_limit_key,
    default_limits=["300/minute"],  # Global limit: 5 req/sec
    storage_uri="memory://",  # In-memory storage (suitable for single instance)
)


# Export limiter
__all__ = ["limiter"]
