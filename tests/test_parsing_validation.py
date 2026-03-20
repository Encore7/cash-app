from decimal import Decimal

from backend.schemas.extraction import RemittanceExtractionResult, RemittanceLineExtraction
from backend.services.parsing_service import validate_remittance_result


def test_validate_remittance_header_line_sum_mismatch() -> None:
    result = RemittanceExtractionResult(
        total_paid_amount=Decimal('100.00'),
        lines=[
            RemittanceLineExtraction(
                line_number=1,
                invoice_number='INV-1',
                paid_amount=Decimal('90.00'),
                currency='EUR',
                raw_line_text='INV-1 90.00 EUR',
            )
        ],
    )
    report = validate_remittance_result(result)
    assert not report.is_valid
    assert 'HEADER_LINE_SUM_MISMATCH' in report.reason_codes
