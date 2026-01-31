"""Firebase Authentication module for API protection."""

from dataclasses import dataclass

from fastapi import HTTPException, Query, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from firebase_admin import auth

# HTTP Bearer scheme for Authorization header
_security = HTTPBearer(auto_error=False)


@dataclass
class AuthenticatedUser:
    """Authenticated user information from Firebase token."""

    uid: str
    email: str | None
    email_verified: bool


async def verify_firebase_token(token: str) -> AuthenticatedUser:
    """
    Verify Firebase ID token and return user information.

    Args:
        token: Firebase ID token from client

    Returns:
        AuthenticatedUser with uid, email, and verification status

    Raises:
        HTTPException: If token is invalid or expired
    """
    try:
        decoded = auth.verify_id_token(token)
        return AuthenticatedUser(
            uid=decoded["uid"],
            email=decoded.get("email"),
            email_verified=decoded.get("email_verified", False),
        )
    except auth.InvalidIdTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except auth.ExpiredIdTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except auth.RevokedIdTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token has been revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Security(_security),
) -> AuthenticatedUser:
    """
    FastAPI dependency for extracting authenticated user from Authorization header.

    Usage:
        @router.get("/protected")
        async def protected_endpoint(current_user: CurrentUserDep):
            return {"user_id": current_user.uid}
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return await verify_firebase_token(credentials.credentials)


async def get_current_user_from_query(
    token: str = Query(..., description="Firebase ID token for SSE authentication"),
) -> AuthenticatedUser:
    """
    FastAPI dependency for extracting authenticated user from query parameter.

    Used for SSE endpoints where EventSource cannot set headers.

    Usage:
        @router.get("/stream")
        async def stream_endpoint(current_user: CurrentUserQueryDep):
            return {"user_id": current_user.uid}
    """
    return await verify_firebase_token(token)
