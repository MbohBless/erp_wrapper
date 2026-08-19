"""Platform operator authentication and account management."""

from datetime import datetime, timezone

from fastapi import HTTPException, status

from models.platform_user import PlatformRole, PlatformUser
from repositories.platform_user_repository import PlatformUserRepository
from schemas.auth import PlatformUserCreate, PlatformUserUpdate
from utils.security import create_access_token, hash_password, verify_password


class PlatformAuthService:
    def __init__(self, repo: PlatformUserRepository) -> None:
        self.repo = repo

    def login(self, email: str, password: str) -> str:
        user = self.repo.get_by_email(email)
        if user is None or not verify_password(password, user.hashed_password):
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED,
                "Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if not user.is_active:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Account disabled")
        user.last_login_at = datetime.now(timezone.utc)
        self.repo.save(user)
        return create_access_token(subject=str(user.id), role=str(user.role))


class PlatformUserService:
    def __init__(self, repo: PlatformUserRepository) -> None:
        self.repo = repo

    def list(self) -> list[PlatformUser]:
        return self.repo.list()

    def get(self, user_id: int) -> PlatformUser:
        user = self.repo.get(user_id)
        if user is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Operator not found")
        return user

    def create(self, data: PlatformUserCreate) -> PlatformUser:
        if self.repo.get_by_email(data.email):
            raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
        return self.repo.add(
            PlatformUser(
                email=str(data.email),
                full_name=data.full_name,
                role=data.role.value,
                is_active=data.is_active,
                hashed_password=hash_password(data.password),
            )
        )

    def update(self, user_id: int, data: PlatformUserUpdate) -> PlatformUser:
        user = self.get(user_id)
        if data.full_name is not None:
            user.full_name = data.full_name
        if data.password is not None:
            user.hashed_password = hash_password(data.password)
        if data.role is not None:
            user.role = data.role.value
        if data.is_active is not None:
            self._guard_last_owner(user, becoming_inactive=not data.is_active)
            user.is_active = data.is_active
        return self.repo.save(user)

    def delete(self, user_id: int) -> None:
        user = self.get(user_id)
        self._guard_last_owner(user, becoming_inactive=True)
        self.repo.delete(user)

    def _guard_last_owner(self, user: PlatformUser, becoming_inactive: bool) -> None:
        """Refuse to leave the platform with no way in.

        Locking out the last owner is unrecoverable without database access.
        """
        if not becoming_inactive or user.role != PlatformRole.OWNER.value:
            return
        active_owners = [
            u
            for u in self.repo.list()
            if u.role == PlatformRole.OWNER.value and u.is_active and u.id != user.id
        ]
        if not active_owners:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "This is the last active owner; promote another operator first.",
            )
