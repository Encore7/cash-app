from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base
from backend.models.enums import MatchStatus

if TYPE_CHECKING:
    from backend.models.bank import BankStatementLine
    from backend.models.core import IngestionRun
    from backend.models.journal import JournalEntryLine
    from backend.models.remittance import RemittanceAdviceLine


class ReconciliationMatch(Base):
    __tablename__ = 'reconciliation_matches'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('ingestion_runs.id'), nullable=False)
    bank_statement_line_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('bank_statement_lines.id'), nullable=False)
    remittance_advice_line_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('remittance_advice_lines.id'))
    status: Mapped[MatchStatus] = mapped_column(SAEnum(MatchStatus), nullable=False, default=MatchStatus.MANUAL_REVIEW)
    confidence_score: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    match_rule: Mapped[str] = mapped_column(String(80), nullable=False)
    amount_applied: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    variance_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    notes: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default='RULE')
    reviewed_by: Mapped[str | None] = mapped_column(String(120))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_comment: Mapped[str | None] = mapped_column(Text)
    is_selected: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    run: Mapped[IngestionRun] = relationship(back_populates='matches')
    bank_statement_line: Mapped[BankStatementLine] = relationship(back_populates='matches')
    remittance_advice_line: Mapped[RemittanceAdviceLine | None] = relationship(back_populates='matches')
    journal_lines: Mapped[list[JournalEntryLine]] = relationship(back_populates='reconciliation_match')
    actions: Mapped[list[MatchActionAudit]] = relationship(back_populates='match')


class MatchActionAudit(Base):
    __tablename__ = 'match_action_audit'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('ingestion_runs.id'), nullable=False)
    match_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('reconciliation_matches.id'))
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(120), nullable=False)
    reason_code: Mapped[str | None] = mapped_column(String(64))
    comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    run: Mapped[IngestionRun] = relationship(back_populates='match_actions')
    match: Mapped[ReconciliationMatch | None] = relationship(back_populates='actions')
