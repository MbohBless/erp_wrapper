"""App-DB access for the singleton BooksSetup state."""

import json
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from models.books_setup import BooksSetup


class BooksSetupRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self) -> BooksSetup:
        row = self.db.get(BooksSetup, 1)
        if row is None:
            row = BooksSetup(id=1)
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
