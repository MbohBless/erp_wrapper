"""User data-access (repository pattern). No business rules — persistence only."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from models.user import User


class UserRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, user_id: int) -> User | None:
        return self.db.get(User, user_id)

    def get_by_email(self, email: str) -> User | None:
        return self.db.scalar(select(User).where(User.email == email))

    def list(self, skip: int = 0, limit: int = 100) -> list[User]:
        return list(
            self.db.scalars(select(User).order_by(User.id).offset(skip).limit(limit))
        )

    def add(self, user: User) -> User:
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def save(self, user: User) -> User:
        """Persist changes to an already-tracked user."""
        self.db.commit()
        self.db.refresh(user)
        return user

    def delete(self, user: User) -> None:
        self.db.delete(user)
        self.db.commit()
