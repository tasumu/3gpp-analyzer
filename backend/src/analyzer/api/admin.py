"""Admin API endpoints for user management."""

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from analyzer.dependencies import CurrentUserDep, UserServiceDep
from analyzer.models.user import User, UserRole, UserStatus

router = APIRouter()


class UserListResponse(BaseModel):
    """User list response."""

    users: list[dict]
    total: int


async def require_admin(current_user: CurrentUserDep, user_service: UserServiceDep) -> User:
    """
    Helper function to require admin privileges.

    Args:
        current_user: Authenticated user
        user_service: User service instance

    Returns:
        User instance with admin role

    Raises:
        HTTPException: If user is not admin
    """
    user = await user_service.get_user(current_user.uid)
    if not user or user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required"
        )
    return user


@router.get("/admin/users", response_model=UserListResponse)
async def list_users(
    current_user: CurrentUserDep,
    user_service: UserServiceDep,
    status_filter: UserStatus | None = Query(None, description="Filter by status"),
    limit: int = Query(100, le=1000),
):
    """
    Get list of users (admin only).

    Args:
        status_filter: Optional status filter (pending/approved/rejected)
        limit: Maximum number of users to return (default: 100, max: 1000)
    """
    await require_admin(current_user, user_service)

    users = await user_service.list_users(status_filter=status_filter, limit=limit)

    return UserListResponse(
        users=[user.model_dump() for user in users],
        total=len(users),
    )


@router.post("/admin/users/{uid}/approve")
async def approve_user(
    uid: str,
    current_user: CurrentUserDep,
    user_service: UserServiceDep,
):
    """
    Approve a user (admin only).

    Args:
        uid: UID of user to approve
    """
    admin = await require_admin(current_user, user_service)

    try:
        user = await user_service.approve_user(uid, admin.uid)
        return {"message": f"User {user.email} approved successfully"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/admin/users/{uid}/reject")
async def reject_user(
    uid: str,
    current_user: CurrentUserDep,
    user_service: UserServiceDep,
):
    """
    Reject a user (admin only).

    Args:
        uid: UID of user to reject
    """
    admin = await require_admin(current_user, user_service)

    try:
        user = await user_service.reject_user(uid, admin.uid)
        return {"message": f"User {user.email} rejected"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
