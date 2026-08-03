"""App-DB access for payment intents."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from models.payment_intent import (
    RECON_PENDING,
    STATUS_PENDING,
    PaymentIntent,
)


class PaymentIntentRepository:
    def __init__(self, db: Session, tenant_id: str) -> None:
        self.db = db
        self.tenant_id = tenant_id

    # -- reads -------------------------------------------------------------
    def get(self, intent_id: int) -> PaymentIntent | None:
        return self.db.scalar(
            select(PaymentIntent).where(
                PaymentIntent.id == intent_id,
                PaymentIntent.tenant_id == self.tenant_id,
            )
        )

    def get_by_reference(self, reference: str) -> PaymentIntent | None:
        return self.db.scalar(
            select(PaymentIntent).where(
                PaymentIntent.reference == reference,
                PaymentIntent.tenant_id == self.tenant_id,
            )
        )

    def get_by_provider_ref(self, provider: str, provider_ref: str) -> PaymentIntent | None:
        return self.db.scalar(
            select(PaymentIntent).where(
                PaymentIntent.provider == provider,
                PaymentIntent.provider_ref == provider_ref,
                PaymentIntent.tenant_id == self.tenant_id,
            )
        )

    def find_for_webhook(
        self, provider: str, provider_ref: str, our_reference: str
    ) -> PaymentIntent | None:
        """Match a callback to an intent by either identifier.

        Providers are inconsistent about which one they echo, and some send
        only the one they generated — so try both rather than assuming.
        """
        clauses = []
        if provider_ref:
            clauses.append(PaymentIntent.provider_ref == provider_ref)
        if our_reference:
            clauses.append(PaymentIntent.reference == our_reference)
        if not clauses:
            return None
        return self.db.scalar(
            select(PaymentIntent).where(
                PaymentIntent.tenant_id == self.tenant_id,
                PaymentIntent.provider == provider,
                or_(*clauses),
            )
        )

    def list(
        self,
        *,
        direction: str | None = None,
        status: str | None = None,
        reconciliation: str | None = None,
        erpnext_docname: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[PaymentIntent]:
        stmt = select(PaymentIntent).where(PaymentIntent.tenant_id == self.tenant_id)
        if direction:
            stmt = stmt.where(PaymentIntent.direction == direction)
        if status:
            stmt = stmt.where(PaymentIntent.status == status)
        if reconciliation:
            stmt = stmt.where(PaymentIntent.reconciliation == reconciliation)
        if erpnext_docname:
            stmt = stmt.where(PaymentIntent.erpnext_docname == erpnext_docname)
        stmt = stmt.order_by(PaymentIntent.id.desc()).offset(skip).limit(limit)
        return list(self.db.scalars(stmt))

    def list_open(self, limit: int = 200) -> list[PaymentIntent]:
        """Intents still awaiting a terminal answer — what a poller sweeps.

        Necessary because a callback that never arrives is a normal event, not
        an exception: polling is the backstop that stops a paid invoice sitting
        unreconciled forever.
        """
        return list(
            self.db.scalars(
                select(PaymentIntent)
                .where(
                    PaymentIntent.tenant_id == self.tenant_id,
                    PaymentIntent.status.in_(("created", STATUS_PENDING)),
                )
                .order_by(PaymentIntent.id)
                .limit(limit)
            )
        )

    def list_unposted(self, limit: int = 200) -> list[PaymentIntent]:
        """Money arrived but the ledger entry is still owed."""
        return list(
            self.db.scalars(
                select(PaymentIntent)
                .where(
                    PaymentIntent.tenant_id == self.tenant_id,
                    PaymentIntent.status == "succeeded",
                    PaymentIntent.reconciliation == RECON_PENDING,
                )
                .order_by(PaymentIntent.id)
                .limit(limit)
            )
        )

    # -- writes ------------------------------------------------------------
    def add(self, intent: PaymentIntent) -> PaymentIntent:
        intent.tenant_id = self.tenant_id
        self.db.add(intent)
        self.db.commit()
        self.db.refresh(intent)
        return intent

    def save(self, intent: PaymentIntent) -> PaymentIntent:
        self.db.commit()
        self.db.refresh(intent)
        return intent

    def mark_confirmed(self, intent: PaymentIntent) -> PaymentIntent:
        intent.confirmed_at = datetime.now(timezone.utc)
        return self.save(intent)

    def delete_all(self) -> int:
        rows = list(
            self.db.scalars(
                select(PaymentIntent).where(PaymentIntent.tenant_id == self.tenant_id)
            )
        )
        for row in rows:
            self.db.delete(row)
        self.db.commit()
        return len(rows)
