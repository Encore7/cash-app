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


class RemittanceAdviceHeader(Base):
    __tablename__ = 'remittance_advice_headers'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    blob_object_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('blob_objects.id'), unique=True, nullable=False)
    advice_number: Mapped[str | None] = mapped_column(String(80))
    advice_date: Mapped[date | None] = mapped_column(Date)
    payer_name: Mapped[str | None] = mapped_column(String(255))
    document_currency: Mapped[str | None] = mapped_column(String(3))
    total_paid_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))

    source_blob: Mapped[BlobObject] = relationship(back_populates='remittance_advice_header')
    lines: Mapped[list[RemittanceAdviceLine]] = relationship(back_populates='advice_header')


class RemittanceAdviceLine(Base):
    __tablename__ = 'remittance_advice_lines'
    __table_args__ = (UniqueConstraint('advice_header_id', 'line_number', name='uq_remittance_line_number'),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    advice_header_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('remittance_advice_headers.id'), nullable=False)
    line_number: Mapped[int] = mapped_column(nullable=False)
    invoice_number: Mapped[str | None] = mapped_column(String(80))
    invoice_date: Mapped[date | None] = mapped_column(Date)
    paid_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    currency: Mapped[str | None] = mapped_column(String(3))
    customer_reference: Mapped[str | None] = mapped_column(String(120))
    raw_line_text: Mapped[str] = mapped_column(Text, nullable=False)

    advice_header: Mapped[RemittanceAdviceHeader] = relationship(back_populates='lines')
    matches: Mapped[list[ReconciliationMatch]] = relationship(back_populates='remittance_advice_line')
    journal_entries: Mapped[list[JournalEntry]] = relationship(back_populates='remittance_advice_line')
