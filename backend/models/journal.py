from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base

if TYPE_CHECKING:
    from backend.models.bank import BankStatementLine
    from backend.models.core import IngestionRun
    from backend.models.reconciliation import ReconciliationMatch
    from backend.models.remittance import RemittanceAdviceLine


class JournalEntryHeader(Base):
    __tablename__ = 'journal_entry_headers'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('ingestion_runs.id'), nullable=False)
    company_code: Mapped[str] = mapped_column(String(20), nullable=False)
    posting_date: Mapped[date] = mapped_column(Date, nullable=False)
    document_date: Mapped[date] = mapped_column(Date, nullable=False)
    document_type: Mapped[str] = mapped_column(String(10), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    source_file_name: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    run: Mapped[IngestionRun] = relationship(back_populates='journal_entry_headers')
    lines: Mapped[list[JournalEntryLine]] = relationship(back_populates='journal_header')


class JournalEntryLine(Base):
    __tablename__ = 'journal_entry_lines'
    __table_args__ = (UniqueConstraint('journal_header_id', 'line_number', name='uq_journal_line_number'),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    journal_header_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('journal_entry_headers.id'), nullable=False)
    line_number: Mapped[int] = mapped_column(nullable=False)
    gl_account: Mapped[str] = mapped_column(String(20), nullable=False)
    debit: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    credit: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    item_text: Mapped[str | None] = mapped_column(String(255))
    reconciliation_match_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('reconciliation_matches.id'))
    bank_statement_line_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('bank_statement_lines.id'))
    remittance_advice_line_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('remittance_advice_lines.id'))

    journal_header: Mapped[JournalEntryHeader] = relationship(back_populates='lines')
    reconciliation_match: Mapped[ReconciliationMatch | None] = relationship(back_populates='journal_lines')
    bank_statement_line: Mapped[BankStatementLine | None] = relationship(back_populates='journal_lines')
    remittance_advice_line: Mapped[RemittanceAdviceLine | None] = relationship(
        back_populates='journal_lines'
    )
