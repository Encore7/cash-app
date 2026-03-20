from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base

if TYPE_CHECKING:
    from backend.models.core import BlobObject
    from backend.models.journal import JournalEntryLine
    from backend.models.reconciliation import ReconciliationMatch


class BankStatementHeader(Base):
    __tablename__ = 'bank_statement_headers'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    blob_object_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('blob_objects.id'), unique=True, nullable=False)
    sheet_name: Mapped[str] = mapped_column(String(120), nullable=False, default='Bank Statement')
    source_file_name: Mapped[str | None] = mapped_column(String(255))
    statement_currency: Mapped[str | None] = mapped_column(String(3))
    line_count: Mapped[int] = mapped_column(default=0, nullable=False)
    total_credit_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    total_debit_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    parsed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    source_blob: Mapped[BlobObject] = relationship(back_populates='bank_statement_header')
    lines: Mapped[list[BankStatementLine]] = relationship(back_populates='statement_header')


class BankStatementLine(Base):
    __tablename__ = 'bank_statement_lines'
    __table_args__ = (UniqueConstraint('statement_header_id', 'line_number', name='uq_bank_line_number'),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    statement_header_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('bank_statement_headers.id'), nullable=False)
    line_number: Mapped[int] = mapped_column(nullable=False)
    booking_date: Mapped[date] = mapped_column(Date, nullable=False)
    value_date: Mapped[date | None] = mapped_column(Date)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    counterparty_name: Mapped[str | None] = mapped_column(String(255))
    payment_purpose: Mapped[str | None] = mapped_column(Text)
    counterparty_account: Mapped[str | None] = mapped_column(String(64))
    bic: Mapped[str | None] = mapped_column(String(20))
    bank_name: Mapped[str | None] = mapped_column(String(255))
    bank_code: Mapped[str | None] = mapped_column(String(20))
    booking_text: Mapped[str | None] = mapped_column(String(120))
    bank_reference: Mapped[str | None] = mapped_column(String(120))
    iban: Mapped[str | None] = mapped_column(String(64))
    account_label: Mapped[str | None] = mapped_column(String(255))
    account_number: Mapped[str | None] = mapped_column(String(40))
    customer_reference: Mapped[str | None] = mapped_column(String(120))
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    raw_payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    statement_header: Mapped[BankStatementHeader] = relationship(back_populates='lines')
    matches: Mapped[list[ReconciliationMatch]] = relationship(back_populates='bank_statement_line')
    journal_lines: Mapped[list[JournalEntryLine]] = relationship(back_populates='bank_statement_line')
