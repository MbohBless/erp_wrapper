"""App-DB access for the per-tenant BooksSetup state."""

import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from models.books_setup import BooksSetup


class BooksSetupRepository:
    def __init__(self, db: Session, tenant_id: str) -> None:
        self.db = db
        self.tenant_id = tenant_id

    def get(self) -> BooksSetup:
        row = self.db.scalar(
            select(BooksSetup).where(BooksSetup.tenant_id == self.tenant_id)
        )
        if row is None:
            row = BooksSetup(tenant_id=self.tenant_id)
            self.db.add(row)
            self.db.commit()
            self.db.refresh(row)
        return row

    def mark_complete(self, start_date: str, opening_ref: str, payload: dict) -> BooksSetup:
        row = self.get()
        row.setup_complete = True
        row.start_date = start_date
        row.opening_ref = opening_ref or ""
        row.payload_json = json.dumps(payload)[:100000]
        row.posted_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete(self) -> None:
        row = self.db.scalar(
            select(BooksSetup).where(BooksSetup.tenant_id == self.tenant_id)
        )
        if row is not None:
            self.db.delete(row)
            self.db.commit()
