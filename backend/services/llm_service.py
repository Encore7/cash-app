from __future__ import annotations

import base64
import json
import re
import urllib.error
import urllib.request
from datetime import date, datetime
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


def _build_prompt() -> str:
    return (
        'You are an expert AR cash-application extractor. Extract remittance advice header and line items into the schema. '
        'Return strict JSON only without markdown fences or commentary. '
        'Use ISO date format YYYY-MM-DD. '
        'Use decimal dot notation for amounts (for example 1234.56, not 1.234,56). '
        'Extract all invoice/payment line items, not just a subset. '
        'For line items, map the final amount from the German "Zahlbetrag" column to paid_amount. '
        'Ensure arithmetic consistency: sum(lines[].paid_amount) must equal total_paid_amount from payment summary. '
        'If mismatch appears, re-read ambiguous OCR digits (especially 1/7) and correct line values before output. '
        'Use this JSON shape: '
        '{"advice_number":null,"advice_date":null,"payer_name":null,"payer_iban":null,"payer_bic":null,'
        '"document_currency":null,"total_paid_amount":null,"document_language":"de","remittance_subject":null,'
        '"raw_text":null,"parsing_confidence":0.0,'
        '"lines":[{"line_number":1,"invoice_number":null,"invoice_date":null,"due_date":null,"gross_amount":null,'
        '"discount_amount":null,"deduction_amount":null,"paid_amount":null,"currency":null,"customer_reference":null,'
        '"assignment_text":null,"raw_line_text":""}]}. '
        'Leave unknown values as null and keep decimals using dot notation.'
    )


def _parse_dateish(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value.isoformat()
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    for pattern in ('%Y-%m-%d', '%d.%m.%Y', '%d/%m/%Y', '%d-%m-%Y'):
        try:
            return date.fromisoformat(text).isoformat() if pattern == '%Y-%m-%d' else datetime.strptime(text, pattern).date().isoformat()
        except Exception:
            continue
    return text


def _parse_decimalish(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, int | float):
        return str(Decimal(str(value)))
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    text = text.replace('EUR', '').replace('€', '').replace(' ', '')
    if ',' in text and '.' in text:
        text = text.replace('.', '').replace(',', '.')
    elif ',' in text:
        text = text.replace(',', '.')
    try:
        return str(Decimal(text))
    except Exception:
        return None


def _extract_german_amounts(raw_line_text: str) -> list[str]:
    matches = re.findall(r'([0-9]{1,3}(?:\.[0-9]{3})*,[0-9]{2})', raw_line_text)
    extracted: list[str] = []
    for match in matches:
        converted = _parse_decimalish(match)
        if converted is not None:
            extracted.append(converted)
    return extracted


def _normalize_payload(payload: dict) -> dict:
    normalized = dict(payload)
    normalized['advice_date'] = _parse_dateish(normalized.get('advice_date'))
    normalized['total_paid_amount'] = _parse_decimalish(normalized.get('total_paid_amount'))
    normalized['parsing_confidence'] = _parse_decimalish(normalized.get('parsing_confidence'))

    raw_lines = normalized.get('lines')
    if not isinstance(raw_lines, list):
        normalized['lines'] = []
        return normalized

    fixed_lines: list[dict] = []
    for idx, raw_line in enumerate(raw_lines, start=1):
        if not isinstance(raw_line, dict):
            continue
        item = dict(raw_line)
        line_number = item.get('line_number')
        if isinstance(line_number, int):
            item['line_number'] = line_number
        elif isinstance(line_number, str) and line_number.strip().isdigit():
            item['line_number'] = int(line_number.strip())
        else:
            item['line_number'] = idx
        item['invoice_date'] = _parse_dateish(item.get('invoice_date'))
        item['due_date'] = _parse_dateish(item.get('due_date'))
        item['gross_amount'] = _parse_decimalish(item.get('gross_amount'))
        item['discount_amount'] = _parse_decimalish(item.get('discount_amount'))
        item['deduction_amount'] = _parse_decimalish(item.get('deduction_amount'))
        item['paid_amount'] = _parse_decimalish(item.get('paid_amount'))
        item['currency'] = item.get('currency').strip()[:3].upper() if isinstance(item.get('currency'), str) and item.get('currency').strip() else None
        raw_line_text = item.get('raw_line_text')
        if raw_line_text is None:
            item['raw_line_text'] = item.get('assignment_text') or ''
        elif isinstance(raw_line_text, str):
            # For classic Zahlungsavis rows, enforce exact amount mapping from raw line:
            # [skonto, bruttobetrag, zahlbetrag].
            amounts = _extract_german_amounts(raw_line_text)
            if len(amounts) >= 3:
                item['discount_amount'] = amounts[0]
                item['gross_amount'] = amounts[1]
                item['paid_amount'] = amounts[2]
                item['deduction_amount'] = '0.00'
        fixed_lines.append(item)

    normalized['lines'] = fixed_lines
    return normalized


def _extract_json_payload(text: str) -> dict:
    stripped = text.strip()
    if stripped.startswith('```'):
        stripped = re.sub(r'^```(?:json)?\s*', '', stripped)
        stripped = re.sub(r'\s*```$', '', stripped)
    try:
        parsed = json.loads(stripped)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass
    match = re.search(r'\{[\s\S]*\}', stripped)
    if match:
        parsed = json.loads(match.group(0))
        if isinstance(parsed, dict):
            return parsed
    raise ValueError('Gemini response did not include a valid JSON object')


def _extract_via_gemini_pdf_bytes(pdf_bytes: bytes) -> tuple[RemittanceExtractionResult, dict]:
    if not settings.google_api_key:
        raise ValueError('Missing GOOGLE_API_KEY')
    body = {
        'contents': [
            {
                'parts': [
                    {'text': _build_prompt()},
                    {
                        'inline_data': {
                            'mime_type': 'application/pdf',
                            'data': base64.b64encode(pdf_bytes).decode('ascii'),
                        }
                    },
                ]
            }
        ],
        'generationConfig': {'temperature': 0.0},
    }
    request = urllib.request.Request(
        url=f'https://generativelanguage.googleapis.com/v1beta/models/{settings.gemini_model}:generateContent',
        data=json.dumps(body).encode('utf-8'),
        headers={'Content-Type': 'application/json', 'X-goog-api-key': settings.google_api_key},
        method='POST',
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        raw = response.read().decode('utf-8')
    payload = json.loads(raw)
    candidates = payload.get('candidates', [])
    if not candidates:
        raise ValueError('Gemini returned no candidates')
    parts = candidates[0].get('content', {}).get('parts', [])
    text_part = next((part.get('text') for part in parts if isinstance(part, dict) and part.get('text')), '')
    if not text_part:
        raise ValueError('Gemini did not return text content for PDF')
    extracted_payload = _normalize_payload(_extract_json_payload(text_part))
    return RemittanceExtractionResult.model_validate(extracted_payload), payload


def extract_remittance_with_llm(raw_text: str, pdf_bytes: bytes | None = None) -> tuple[RemittanceExtractionResult, dict, str, str]:
    if not raw_text.strip() and pdf_bytes is None:
        result = RemittanceExtractionResult(raw_text=raw_text, parsing_confidence=Decimal('0.0'), lines=[])
        return result, {'mode': 'empty_text'}, 'heuristic', 'no-model'

    if not settings.google_api_key:
        result = _heuristic_extract(raw_text)
        return result, {'mode': 'no_api_key'}, 'heuristic', 'no-model'

    if not raw_text.strip() and pdf_bytes:
        try:
            extracted, raw_payload = _extract_via_gemini_pdf_bytes(pdf_bytes)
            return extracted, raw_payload, 'llm_pdf', settings.gemini_model
        except (ValueError, urllib.error.URLError, json.JSONDecodeError) as exc:
            result = RemittanceExtractionResult(raw_text=raw_text, parsing_confidence=Decimal('0.0'), lines=[])
            return result, {'mode': 'llm_pdf_error', 'error': str(exc)}, 'heuristic', settings.gemini_model

    try:
        from langchain_google_genai import ChatGoogleGenerativeAI

        llm = ChatGoogleGenerativeAI(model=settings.gemini_model, google_api_key=settings.google_api_key)
        structured_llm = llm.with_structured_output(RemittanceExtractionResult)
        prompt = f'{_build_prompt()}\\n\\nRemittance text:\\n{raw_text}'
        extracted = structured_llm.invoke(prompt)
        raw_payload = extracted.model_dump(mode='json')
        return extracted, raw_payload, 'llm', settings.gemini_model
    except Exception as exc:
        if pdf_bytes:
            try:
                extracted, raw_payload = _extract_via_gemini_pdf_bytes(pdf_bytes)
                return extracted, raw_payload, 'llm_pdf', settings.gemini_model
            except Exception as pdf_exc:
                fallback = _heuristic_extract(raw_text)
                return (
                    fallback,
                    {'mode': 'llm_text_and_pdf_error', 'text_error': str(exc), 'pdf_error': str(pdf_exc)},
                    'heuristic',
                    settings.gemini_model,
                )
        fallback = _heuristic_extract(raw_text)
        return fallback, {'mode': 'llm_error', 'error': str(exc)}, 'heuristic', settings.gemini_model

