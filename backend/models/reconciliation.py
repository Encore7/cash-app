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
    from backend.models.bank import BankStatement
    from backend.models.core import IngestionRun
    from backend.models.journal import JournalEntry
    from backend.models.remittance import RemittanceAdviceLine


class ReconciliationMatch(Base):
    __tablename__ = 'reconciliation_matches'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('ingestion_runs.id'), nullable=False)
    bank_statement_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('bank_statement.id'), nullable=False)
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
    bank_statement: Mapped[BankStatement] = relationship(back_populates='matches')
    remittance_advice_line: Mapped[RemittanceAdviceLine | None] = relationship(back_populates='matches')
    journal_entries: Mapped[list[JournalEntry]] = relationship(back_populates='reconciliation_match')
