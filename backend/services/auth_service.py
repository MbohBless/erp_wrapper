"""Authentication business logic."""

from fastapi import HTTPException, status

from models.user import User
from repositories.user_repository import UserRepository
from utils.security import create_access_token, verify_password


class AuthService:
    def __init__(self, repo: UserRepository) -> None:
        self.repo = repo

    def authenticate(self, email: str, password: str) -> User:
        user = self.repo.get_by_email(email)
        if user is None or not verify_password(password, user.hashed_password):
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED,
                "Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if not user.is_active:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Inactive user")
        return user

    def login(self, email: str, password: str) -> str:
        """Authenticate and return a signed JWT access token."""
        user = self.authenticate(email, password)
        return create_access_token(subject=str(user.id), role=str(user.role))
