from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime
from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base
from backend.models.enums import RuleType, RunStatus, ScheduleFrequency, SourceType

if TYPE_CHECKING:
    from backend.models.bank import BankStatement
    from backend.models.journal import JournalEntry
    from backend.models.reconciliation import ReconciliationMatch
    from backend.models.remittance import RemittanceAdviceHeader


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )

    blob_objects: Mapped[list[BlobObject]] = relationship(back_populates="tenant")
    ingestion_runs: Mapped[list[IngestionRun]] = relationship(back_populates="tenant")


class BlobObject(Base):
    __tablename__ = "blob_objects"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "source_type",
            "business_date",
            "content_hash",
            name="uq_blob_dedup",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id"), nullable=False
    )
    source_type: Mapped[SourceType] = mapped_column(SAEnum(SourceType), nullable=False)
    business_date: Mapped[date] = mapped_column(Date, nullable=False)
    container_name: Mapped[str] = mapped_column(String(120), nullable=False)
    blob_path: Mapped[str] = mapped_column(String(512), nullable=False)
    original_file_name: Mapped[str | None] = mapped_column(String(255))
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int | None] = mapped_column()
    arrived_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )
    is_parsed: Mapped[bool] = mapped_column(default=False, nullable=False)

    tenant: Mapped[Tenant] = relationship(back_populates="blob_objects")
    bank_statements: Mapped[list[BankStatement]] = relationship(
        back_populates="source_blob"
    )
    remittance_advice_header: Mapped[RemittanceAdviceHeader | None] = relationship(
        back_populates="source_blob"
    )


class IngestionRun(Base):
    __tablename__ = "ingestion_runs"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "business_date",
            "bank_blob_id",
            "remittance_blob_id",
            name="uq_ingestion_run_slot",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id"), nullable=False
    )
    business_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[RunStatus] = mapped_column(
        SAEnum(RunStatus), nullable=False, default=RunStatus.RECEIVED
    )
    bank_blob_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("blob_objects.id")
    )
    remittance_blob_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("blob_objects.id")
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)
    review_reason_code: Mapped[str | None] = mapped_column(String(64))
    parsed_line_count: Mapped[int] = mapped_column(default=0, nullable=False)
    matched_line_count: Mapped[int] = mapped_column(default=0, nullable=False)
    review_required_count: Mapped[int] = mapped_column(default=0, nullable=False)

    tenant: Mapped[Tenant] = relationship(back_populates="ingestion_runs")
    matches: Mapped[list[ReconciliationMatch]] = relationship(back_populates="run")
    journal_entries: Mapped[list[JournalEntry]] = relationship(back_populates="run")


class JobScheduleRule(Base):
    __tablename__ = "job_schedule_rules"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    rule_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="processing"
    )
    frequency: Mapped[ScheduleFrequency] = mapped_column(
        SAEnum(
            ScheduleFrequency,
            name="schedulefrequency",
            create_type=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    day_of_week: Mapped[int | None] = mapped_column(Integer, nullable=True)
    day_of_month: Mapped[int | None] = mapped_column(Integer, nullable=True)
    run_time: Mapped[str] = mapped_column(String(5), nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )
    last_triggered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
