from decimal import Decimal

from backend.services.matching_service import generate_match_candidates


def test_generate_match_candidates_aggregate_and_selection() -> None:
    bank_lines = [
        {
            'id': '00000000-0000-0000-0000-000000000001',
            'amount': Decimal('300.00'),
            'bank_reference': None,
            'customer_reference': None,
            'payment_purpose': 'bundle payment',
        }
    ]
    remittance_lines = [
        {'id': '00000000-0000-0000-0000-000000000101', 'invoice_number': 'INV-1', 'paid_amount': Decimal('100.00')},
        {'id': '00000000-0000-0000-0000-000000000102', 'invoice_number': 'INV-2', 'paid_amount': Decimal('200.00')},
    ]

    candidates = generate_match_candidates(bank_lines, remittance_lines)
    assert len(candidates) == 2
    assert any(c['match_rule'] == 'aggregate_2_line_amount' for c in candidates)
    selected = [c for c in candidates if c['is_selected']]
    assert len(selected) == 1
