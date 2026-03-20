from __future__ import annotations

import json
import re
from decimal import Decimal

from backend.config import settings
from backend.schemas.extraction import RemittanceExtractionResult, RemittanceLineExtraction


def _heuristic_extract(text: str) -> RemittanceExtractionResult:
    lines: list[RemittanceLineExtraction] = []
    amount_re = re.compile(r'([0-9]{1,3}(?:[\.,][0-9]{3})*[\.,][0-9]{2})\s*(EUR|€)?', re.IGNORECASE)
    invoice_re = re.compile(r'(?:RECHNUNG|INVOICE|RNR|RG)\s*[:#-]?\s*([A-Z0-9\-/]+)', re.IGNORECASE)

    for idx, line in enumerate([raw_line.strip() for raw_line in text.splitlines() if raw_line.strip()], start=1):
        invoice_match = invoice_re.search(line)
        amount_match = amount_re.search(line)
        if not invoice_match and not amount_match:
            continue
        paid_amount = None
        if amount_match:
            normalized = amount_match.group(1).replace('.', '').replace(',', '.')
            try:
                paid_amount = Decimal(normalized)
            except Exception:
                paid_amount = None
        lines.append(
            RemittanceLineExtraction(
                line_number=idx,
                invoice_number=invoice_match.group(1) if invoice_match else None,
                paid_amount=paid_amount,
                currency='EUR' if amount_match else None,
                raw_line_text=line,
                assignment_text=line,
            )
        )

    total = None
    if lines and any(item.paid_amount is not None for item in lines):
        total = sum((item.paid_amount or Decimal('0.00')) for item in lines)

    return RemittanceExtractionResult(
        remittance_subject='Heuristic extraction fallback',
        raw_text=text,
        parsing_confidence=Decimal('0.55') if lines else Decimal('0.20'),
        document_currency='EUR',
        total_paid_amount=total,
        lines=lines,
    )


def extract_remittance_with_llm(raw_text: str) -> tuple[RemittanceExtractionResult, dict, str, str]:
    if not raw_text.strip():
        result = RemittanceExtractionResult(raw_text=raw_text, parsing_confidence=Decimal('0.0'), lines=[])
        return result, {'mode': 'empty_text'}, 'heuristic', 'no-model'

    if not settings.google_api_key:
        result = _heuristic_extract(raw_text)
        return result, {'mode': 'no_api_key'}, 'heuristic', 'no-model'

    try:
        from langchain_google_genai import ChatGoogleGenerativeAI

        llm = ChatGoogleGenerativeAI(model=settings.gemini_model, google_api_key=settings.google_api_key)
        structured_llm = llm.with_structured_output(RemittanceExtractionResult)
        prompt = (
            'You are an expert AR cash-application extractor. Extract remittance advice header and line items '
            'into the provided schema. Preserve raw_line_text for each line and infer currency if clear. '
            'If unknown, keep null.\\n\\n'
            f'Remittance text:\\n{raw_text}'
        )
        extracted = structured_llm.invoke(prompt)
        raw_payload = extracted.model_dump(mode='json')
        return extracted, raw_payload, 'llm', settings.gemini_model
    except Exception as exc:
        fallback = _heuristic_extract(raw_text)
        return fallback, {'mode': 'llm_error', 'error': str(exc)}, 'heuristic', settings.gemini_model


def serialize_extraction_payload(result: RemittanceExtractionResult) -> dict:
    return json.loads(result.model_dump_json())
