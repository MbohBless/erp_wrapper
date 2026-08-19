"""User management business logic."""

from fastapi import HTTPException, status

from models.user import assignable_roles, User
from repositories.user_repository import UserRepository
from schemas.user import UserCreate, UserUpdate
from utils.security import hash_password


class UserService:
    def __init__(self, repo: UserRepository) -> None:
        self.repo = repo

    def get(self, user_id: int) -> User:
        user = self.repo.get(user_id)
        if user is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
        return user

    def list(self, skip: int = 0, limit: int = 100) -> list[User]:
        return self.repo.list(skip, limit)

    @staticmethod
    def _check_role(role) -> None:
        """Refuse a role this deployment has retired.

        Enforced here rather than only hidden in the dropdown: the roles a
        workspace uses is a policy decision, and a policy only the UI knows is
        one anybody with the API can ignore.
        """
        if role is None or role in assignable_roles():
            return
        allowed = ", ".join(r.value for r in assignable_roles())
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"The {role.value} role is not in use on this workspace. "
            f"Available roles: {allowed}.",
        )

    def create(self, data: UserCreate) -> User:
        self._check_role(data.role)
        if self.repo.get_by_email(data.email):
            raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
        user = User(
            email=data.email,
            full_name=data.full_name,
            role=data.role.value,
            is_active=data.is_active,
            hashed_password=hash_password(data.password),
        )
        return self.repo.add(user)

    def update(self, user_id: int, data: UserUpdate) -> User:
        self._check_role(data.role)
        user = self.get(user_id)

        if data.email is not None and data.email != user.email:
            if self.repo.get_by_email(data.email):
                raise HTTPException(
                    status.HTTP_409_CONFLICT, "Email already registered"
                )
            user.email = data.email
        if data.full_name is not None:
            user.full_name = data.full_name
        if data.role is not None:
            user.role = data.role.value
        if data.is_active is not None:
            user.is_active = data.is_active
        if data.password is not None:
            user.hashed_password = hash_password(data.password)

        return self.repo.save(user)

    def delete(self, user_id: int) -> None:
        user = self.get(user_id)
        self.repo.delete(user)
