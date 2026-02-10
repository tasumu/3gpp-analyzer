"""Authentication and user management API endpoints."""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from analyzer.dependencies import (
    CurrentUserNoApprovalDep,
    SettingsDep,
    UserServiceDep,
)
from analyzer.models.user import UserStatus

router = APIRouter()


class RegisterRequest(BaseModel):
    """User registration request."""

    display_name: str | None = None


class UserResponse(BaseModel):
    """User information response."""

    uid: str
    email: str
    display_name: str | None
    status: UserStatus
    role: str


@router.post("/auth/register", response_model=UserResponse)
async def register_user(
    current_user: CurrentUserNoApprovalDep,
    user_service: UserServiceDep,
    settings: SettingsDep,
    request: RegisterRequest,
):
    """
    Register user on first login or update last login time.

    This endpoint is called automatically by the frontend after Firebase authentication.
    If the user's email is in the initial admin list, they are auto-approved as admin.
    """
    # Get initial admin emails from environment variable
    initial_admins = settings.initial_admin_emails

    user = await user_service.register_or_update_user(
        uid=current_user.uid,
        email=current_user.email,
        display_name=request.display_name,
        initial_admins=initial_admins,
    )

    return UserResponse(
        uid=user.uid,
        email=user.email,
        display_name=user.display_name,
        status=user.status,
        role=user.role.value,
    )


@router.get("/auth/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: CurrentUserNoApprovalDep,
    user_service: UserServiceDep,
):
    """
    Get current user information including approval status.

    Note: This endpoint uses CurrentUserNoApprovalDep to allow pending/rejected users
    to check their status.
    """
    user = await user_service.get_user(current_user.uid)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found in database"
        )

    return UserResponse(
        uid=user.uid,
        email=user.email,
        display_name=user.display_name,
        status=user.status,
        role=user.role.value,
    )
