"""Platform operator data access."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from models.platform_user import PlatformUser


class PlatformUserRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, user_id: int) -> PlatformUser | None:
        return self.db.get(PlatformUser, user_id)

    def get_by_email(self, email: str) -> PlatformUser | None:
        return self.db.scalar(
            select(PlatformUser).where(PlatformUser.email == email.strip().lower())
        )

    def list(self) -> list[PlatformUser]:
        return list(self.db.scalars(select(PlatformUser).order_by(PlatformUser.id)))

    def add(self, user: PlatformUser) -> PlatformUser:
        user.email = user.email.strip().lower()
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def save(self, user: PlatformUser) -> PlatformUser:
        self.db.commit()
        self.db.refresh(user)
        return user

    def delete(self, user: PlatformUser) -> None:
        self.db.delete(user)
        self.db.commit()
