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


async def get_current_user_no_approval_check(
    credentials: HTTPAuthorizationCredentials | None = Security(_security),
) -> AuthenticatedUser:
    """
    FastAPI dependency for extracting authenticated user without approval check.

    Used for endpoints that need Firebase authentication but not approval status check
    (e.g., /auth/register).

    Usage:
        @router.post("/auth/register")
        async def register(current_user: CurrentUserNoApprovalDep):
            return {"user_id": current_user.uid}
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return await verify_firebase_token(credentials.credentials)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Security(_security),
) -> AuthenticatedUser:
    """
    FastAPI dependency for extracting authenticated user from Authorization header.

    This includes approval status check. Only approved users can access endpoints
    that use this dependency.

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

    auth_user = await verify_firebase_token(credentials.credentials)

    # Import here to avoid circular imports
    from analyzer.dependencies import get_firestore_client
    from analyzer.services.user_service import UserService

    firestore = get_firestore_client()
    user_service = UserService(firestore)

    user = await user_service.get_user(auth_user.uid)

    # User not registered
    if not user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User not registered. Please complete registration first.",
        )

    # Pending approval
    if user.status.value == "pending":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account is pending approval. Please wait for administrator approval.",
        )

    # Rejected
    if user.status.value == "rejected":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account has been rejected. Please contact the administrator.",
        )

    # Approved users only pass through
    return auth_user


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
