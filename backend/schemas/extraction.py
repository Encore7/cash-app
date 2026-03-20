from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field


class RemittanceLineExtraction(BaseModel):
    line_number: int
    invoice_number: str | None = None
    invoice_date: date | None = None
    due_date: date | None = None
    gross_amount: Decimal | None = None
    discount_amount: Decimal | None = None
    deduction_amount: Decimal | None = None
    paid_amount: Decimal | None = None
    currency: str | None = None
    customer_reference: str | None = None
    assignment_text: str | None = None
    raw_line_text: str = ''


class RemittanceExtractionResult(BaseModel):
    advice_number: str | None = None
    advice_date: date | None = None
    payer_name: str | None = None
    payer_iban: str | None = None
    payer_bic: str | None = None
    document_currency: str | None = None
    total_paid_amount: Decimal | None = None
    document_language: str = 'de'
    remittance_subject: str | None = None
    raw_text: str | None = None
    parsing_confidence: Decimal | None = Field(default=Decimal('0.0'))
    lines: list[RemittanceLineExtraction] = Field(default_factory=list)


class RemittanceValidationReport(BaseModel):
    is_valid: bool
    reason_codes: list[str] = Field(default_factory=list)
    normalized: RemittanceExtractionResult
