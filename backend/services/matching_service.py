from __future__ import annotations

from decimal import Decimal
from itertools import combinations

from backend.models.enums import MatchStatus


def _norm(value: str | None) -> str:
    return (value or '').strip().lower()


def _contains(haystack: str | None, needle: str | None) -> bool:
    if not haystack or not needle:
        return False
    return _norm(needle) in _norm(haystack)


def generate_match_candidates(bank_lines: list[dict], remittance_lines: list[dict]) -> list[dict]:
    candidates: list[dict] = []
    used_remittance_ids: set[str] = set()

    for bank in bank_lines:
        bank_amount = abs(bank['amount'])
        local_candidates: list[dict] = []

        # Rule 1: exact reference based matching
        for rem in remittance_lines:
            if rem['id'] in used_remittance_ids:
                continue
            invoice_number = rem.get('invoice_number')
            if invoice_number and (
                _contains(bank.get('bank_reference'), invoice_number)
                or _contains(bank.get('customer_reference'), invoice_number)
                or _contains(bank.get('payment_purpose'), invoice_number)
            ):
                variance = bank_amount - (rem.get('paid_amount') or Decimal('0.00'))
                local_candidates.append(
                    {
                        'bank_statement_line_id': bank['id'],
                        'remittance_advice_line_id': rem['id'],
                        'match_rule': 'invoice_reference_exact',
                        'confidence_score': Decimal('0.96'),
                        'amount_applied': rem.get('paid_amount') or Decimal('0.00'),
                        'variance_amount': variance,
                        'status': MatchStatus.AUTO_MATCHED,
                        'source': 'RULE',
                    }
                )

        # Rule 2: exact amount single line
        for rem in remittance_lines:
            if rem['id'] in used_remittance_ids:
                continue
            paid = rem.get('paid_amount')
            if paid is None:
                continue
            if abs(bank_amount - abs(paid)) <= Decimal('0.02'):
                local_candidates.append(
                    {
                        'bank_statement_line_id': bank['id'],
                        'remittance_advice_line_id': rem['id'],
                        'match_rule': 'single_line_amount_exact',
                        'confidence_score': Decimal('0.90'),
                        'amount_applied': paid,
                        'variance_amount': Decimal('0.00'),
                        'status': MatchStatus.AUTO_MATCHED,
                        'source': 'RULE',
                    }
                )

        # Rule 3: aggregate 2-3 remittance lines
        remaining = [r for r in remittance_lines if r['id'] not in used_remittance_ids and r.get('paid_amount') is not None]
        agg_selected: list[dict] = []
        for size in (2, 3):
            if len(remaining) < size:
                continue
            found = False
            for combo in combinations(remaining, size):
                combo_sum = sum((abs(c['paid_amount']) for c in combo), Decimal('0.00'))
                if abs(combo_sum - bank_amount) <= Decimal('0.02'):
                    for rem in combo:
                        agg_selected.append(
                            {
                                'bank_statement_line_id': bank['id'],
                                'remittance_advice_line_id': rem['id'],
                                'match_rule': f'aggregate_{size}_line_amount',
                                'confidence_score': Decimal('0.88'),
                                'amount_applied': rem['paid_amount'],
                                'variance_amount': Decimal('0.00'),
                                'status': MatchStatus.PARTIAL_MATCH,
                                'source': 'RULE',
                            }
                        )
                    found = True
                    break
            if found:
                break
        local_candidates.extend(agg_selected)

        # Rule 4: partial match fallback
        if not local_candidates:
            best_partial = None
            for rem in remaining:
                paid = abs(rem.get('paid_amount') or Decimal('0.00'))
                if paid == 0:
                    continue
                if paid < bank_amount:
                    variance = bank_amount - paid
                    cand = {
                        'bank_statement_line_id': bank['id'],
                        'remittance_advice_line_id': rem['id'],
                        'match_rule': 'partial_amount_fallback',
                        'confidence_score': Decimal('0.70'),
                        'amount_applied': rem.get('paid_amount'),
                        'variance_amount': variance,
                        'status': MatchStatus.MANUAL_REVIEW,
                        'source': 'RULE',
                    }
                    if best_partial is None or cand['variance_amount'] < best_partial['variance_amount']:
                        best_partial = cand
            if best_partial:
                local_candidates.append(best_partial)

        if not local_candidates:
            local_candidates.append(
                {
                    'bank_statement_line_id': bank['id'],
                    'remittance_advice_line_id': None,
                    'match_rule': 'no_match',
                    'confidence_score': Decimal('0.10'),
                    'amount_applied': None,
                    'variance_amount': bank_amount,
                    'status': MatchStatus.UNMATCHED,
                    'source': 'RULE',
                }
            )

        local_candidates.sort(key=lambda c: c['confidence_score'], reverse=True)
        if local_candidates:
            local_candidates[0]['is_selected'] = True
            for cand in local_candidates[1:]:
                cand['is_selected'] = False
            if local_candidates[0]['remittance_advice_line_id']:
                used_remittance_ids.add(local_candidates[0]['remittance_advice_line_id'])
        candidates.extend(local_candidates)

    return candidates
