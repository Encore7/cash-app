from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import AliasChoices, BaseModel, Field


class IngestRunRequest(BaseModel):
    tenant_code: str
    business_date: date


class RunResponse(BaseModel):
    run_id: str
    tenant_code: str
    business_date: date
    status: str
    parsed_line_count: int
    matched_line_count: int
    review_required_count: int
    review_reason_code: str | None = None
    started_at: datetime
    finished_at: datetime | None = None


class MatchView(BaseModel):
    match_id: str
    status: str
    match_rule: str
    confidence_score: Decimal
    amount_applied: Decimal | None = None
    variance_amount: Decimal | None = None
    source: str
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    review_comment: str | None = None
    bank_line_id: str
    remittance_line_id: str | None = None


class RunItemsResponse(BaseModel):
    run_id: str
    bank_line_count: int
    remittance_line_count: int
    matches: list[MatchView]


class MatchDecisionRequest(BaseModel):
    reason_code: str | None = None
    comment: str | None = None


class ManualLinkRequest(BaseModel):
    bank_statement_id: str = Field(validation_alias=AliasChoices('bank_statement_id', 'bank_statement_line_id'))
    remittance_advice_line_id: str | None = None
    reason_code: str | None = None
    comment: str | None = None


class MatchActionResponse(BaseModel):
    match_id: str
    status: str
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None


class JournalLineView(BaseModel):
    id: str
    line_number: int
    gl_account: str
    debit: Decimal | None = None
    credit: Decimal | None = None
    currency: str
    item_text: str | None = None
    reconciliation_match_id: str | None = None


class JournalPreviewResponse(BaseModel):
    run_id: str
    status: str
    journal_headers: int
    journal_lines: list[JournalLineView] = Field(default_factory=list)
