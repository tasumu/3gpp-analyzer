"""User management service."""

from datetime import datetime, timezone

from analyzer.models.user import User, UserRole, UserStatus
from analyzer.providers.firestore_client import FirestoreClient


class UserService:
    """Service for managing user approval and roles."""

    def __init__(self, firestore: FirestoreClient):
        """
        Initialize UserService.

        Args:
            firestore: Firestore client instance
        """
        self.firestore = firestore
        self.collection = "users"

    async def register_or_update_user(
        self,
        uid: str,
        email: str,
        display_name: str | None = None,
        initial_admins: list[str] | None = None,
    ) -> User:
        """
        Register new user or update last login time for existing user.

        Args:
            uid: Firebase Auth UID
            email: User email address
            display_name: User display name (optional)
            initial_admins: List of admin email addresses (auto-approve if in list)

        Returns:
            User instance
        """
        if initial_admins is None:
            initial_admins = []

        # Check if user already exists
        existing = await self.get_user(uid)

        if existing:
            # Update last login time for existing user
            existing.last_login_at = datetime.now(timezone.utc)
            doc_ref = self.firestore.client.collection(self.collection).document(uid)
            doc_ref.update({"last_login_at": existing.last_login_at})
            return existing

        # Create new user
        # Auto-approve if email is in initial admins list
        is_initial_admin = email in initial_admins
        status = UserStatus.APPROVED if is_initial_admin else UserStatus.PENDING
        role = UserRole.ADMIN if is_initial_admin else UserRole.USER

        user = User(
            uid=uid,
            email=email,
            display_name=display_name,
            status=status,
            role=role,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            last_login_at=datetime.now(timezone.utc),
            approved_by=uid if is_initial_admin else None,
            approved_at=datetime.now(timezone.utc) if is_initial_admin else None,
        )

        doc_ref = self.firestore.client.collection(self.collection).document(uid)
        doc_ref.set(user.to_firestore())
        return user

    async def get_user(self, uid: str) -> User | None:
        """
        Get user by UID.

        Args:
            uid: Firebase Auth UID

        Returns:
            User instance or None if not found
        """
        doc_ref = self.firestore.client.collection(self.collection).document(uid)
        doc = doc_ref.get()
        if not doc.exists:
            return None
        return User.from_firestore(uid, doc.to_dict())

    async def list_users(
        self, status_filter: UserStatus | None = None, limit: int = 100
    ) -> list[User]:
        """
        Get list of users with optional status filter.

        Args:
            status_filter: Filter by user status (optional)
            limit: Maximum number of users to return

        Returns:
            List of User instances
        """
        query = self.firestore.client.collection(self.collection)

        if status_filter:
            query = query.where("status", "==", status_filter.value)

        query = query.order_by("created_at", direction="DESCENDING").limit(limit)

        docs = query.stream()
        return [User.from_firestore(doc.id, doc.to_dict()) for doc in docs]

    async def approve_user(self, uid: str, admin_uid: str) -> User:
        """
        Approve a user.

        Args:
            uid: UID of user to approve
            admin_uid: UID of approving admin

        Returns:
            Updated User instance

        Raises:
            ValueError: If user not found
        """
        user = await self.get_user(uid)
        if not user:
            raise ValueError(f"User {uid} not found")

        user.status = UserStatus.APPROVED
        user.approved_by = admin_uid
        user.approved_at = datetime.now(timezone.utc)
        user.updated_at = datetime.now(timezone.utc)

        doc_ref = self.firestore.client.collection(self.collection).document(uid)
        doc_ref.update(user.to_firestore())

        return user

    async def reject_user(self, uid: str, admin_uid: str) -> User:
        """
        Reject a user.

        Args:
            uid: UID of user to reject
            admin_uid: UID of rejecting admin

        Returns:
            Updated User instance

        Raises:
            ValueError: If user not found
        """
        user = await self.get_user(uid)
        if not user:
            raise ValueError(f"User {uid} not found")

        user.status = UserStatus.REJECTED
        user.approved_by = admin_uid
        user.approved_at = datetime.now(timezone.utc)
        user.updated_at = datetime.now(timezone.utc)

        doc_ref = self.firestore.client.collection(self.collection).document(uid)
        doc_ref.update(user.to_firestore())

        return user
