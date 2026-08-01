"""User data-access (repository pattern). No business rules — persistence only.

Tenant-scoped: the repository is constructed for exactly one tenant and every
query filters on it. There is intentionally no "get any user by id" method —
tenant isolation is enforced here rather than being left to each caller.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from models.user import User


class UserRepository:
    def __init__(self, db: Session, tenant_id: str) -> None:
        self.db = db
        self.tenant_id = tenant_id

    def get(self, user_id: int) -> User | None:
        return self.db.scalar(
            select(User).where(
                User.id == user_id, User.tenant_id == self.tenant_id
            )
        )

    def get_by_email(self, email: str) -> User | None:
        return self.db.scalar(
            select(User).where(
                User.email == email, User.tenant_id == self.tenant_id
            )
        )

    def list(self, skip: int = 0, limit: int = 100) -> list[User]:
        return list(
            self.db.scalars(
                select(User)
                .where(User.tenant_id == self.tenant_id)
                .order_by(User.id)
                .offset(skip)
                .limit(limit)
            )
        )

    def count(self) -> int:
        return len(
            list(self.db.scalars(select(User.id).where(User.tenant_id == self.tenant_id)))
        )

    def add(self, user: User) -> User:
        # Stamp rather than trust the caller: a service cannot accidentally
        # write a row into another tenant.
        user.tenant_id = self.tenant_id
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

    def delete_all(self) -> int:
        """Remove every user in this tenant (offboarding). Returns the count."""
        rows = list(
            self.db.scalars(select(User).where(User.tenant_id == self.tenant_id))
        )
        for row in rows:
            self.db.delete(row)
        self.db.commit()
        return len(rows)
