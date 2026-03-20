# Schema from sample files

## Files inspected
- `data/Sample Bank Statement.xlsx`
- `data/Sample Journal Entry.xlsx`
- `data/Sample Payment Advice.pdf`

## Bank statement (xlsx)
Sheet `Bank Statement` columns used:
- Buchungsdatum -> `booking_date`
- Valutadatum -> `value_date`
- Betrag -> `amount`
- Auftraggeber/Empfänger -> `counterparty_name`
- Verwendungszweck -> `payment_purpose`
- Auftraggeber-/Empfängerkonto -> `counterparty_account`
- BIC -> `bic`
- Bank -> `bank_name`
- Bankleitzahl -> `bank_code`
- Buchungstext -> `booking_text`
- Referenz -> `bank_reference`
- IBAN -> `iban`
- Konto -> `account_label`
- Kontonummer -> `account_number`
- Kundenreferenz -> `customer_reference`
- Währung -> `currency`

## Journal entry sample (xlsx)
Sheet `Journal Entry` columns used:
- Company Code -> `company_code`
- Posting Date -> `posting_date`
- Document Date -> `document_date`
- Document Type -> `document_type`
- Line Number -> `line_number`
- GL Account -> `gl_account`
- Debit -> `debit`
- Credit -> `credit`
- Currency -> `currency`
- Item Text -> `item_text`

## Payment advice (pdf)
The file is image-based in this environment (no embedded text via `pypdf`/`pdftotext`).
To keep this production-safe, schema separates header and line items:
- Header table stores advice-level fields (advice number/date, payer, totals, language, OCR metadata, raw text)
- Line table stores invoice-level items (invoice number/date, paid amount, discounts/deductions, references, raw line text)

This supports both OCR-first and parser-first extraction pipelines.

## Implemented tables
- `bank_statement_headers`
- `bank_statement_lines`
- `remittance_advice_headers`
- `remittance_advice_lines`
- `reconciliation_matches`
- `journal_entry_headers`
- `journal_entry_lines`

Migration:
- `alembic/versions/8783837c2904_normalize_bank_remittance_journal_tables.py`
