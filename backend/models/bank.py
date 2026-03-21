from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base

if TYPE_CHECKING:
    from backend.models.core import BlobObject
    from backend.models.journal import JournalEntry
    from backend.models.reconciliation import ReconciliationMatch


class BankStatement(Base):
    __tablename__ = 'bank_statement'
    __table_args__ = (UniqueConstraint('blob_object_id', 'line_number', name='uq_bank_statement_line'),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    blob_object_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('blob_objects.id'), nullable=False)
    line_number: Mapped[int] = mapped_column(nullable=False)
    booking_date: Mapped[date] = mapped_column(Date, nullable=False)
    value_date: Mapped[date | None] = mapped_column(Date)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    counterparty_name: Mapped[str | None] = mapped_column(String(255))
    payment_purpose: Mapped[str | None] = mapped_column(Text)
    bank_reference: Mapped[str | None] = mapped_column(String(120))
    customer_reference: Mapped[str | None] = mapped_column(String(120))
    currency: Mapped[str] = mapped_column(String(3), nullable=False)

    source_blob: Mapped[BlobObject] = relationship(back_populates='bank_statements')
    matches: Mapped[list[ReconciliationMatch]] = relationship(back_populates='bank_statement')
    journal_entries: Mapped[list[JournalEntry]] = relationship(back_populates='bank_statement')
