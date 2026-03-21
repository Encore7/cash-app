from __future__ import annotations

from decimal import Decimal
from itertools import combinations

from backend.models.enums import MatchStatus


def _norm(value: str | None) -> str:
    return (value or "").strip().lower()


def _contains(haystack: str | None, needle: str | None) -> bool:
    if not haystack or not needle:
        return False
    return _norm(needle) in _norm(haystack)


# ---------------------------------------------------------------------------
# Header-level reference matching helpers
# ---------------------------------------------------------------------------


def _ref_match_count(header: dict, bank: dict) -> int:
    """Count how many of the 3 reference fields match between a remittance header and a bank row.

    Fields compared (same-named pair must match):
      header.bank_reference       <-> bank.bank_reference
      header.buyer_reference      <-> bank.buyer_reference
      header.buyer_account_number <-> bank.buyer_account_number
    """
    count = 0
    for field in ("bank_reference", "buyer_reference", "buyer_account_number"):
        h_val = _norm(header.get(field))
        b_val = _norm(bank.get(field))
        if h_val and b_val and h_val == b_val:
            count += 1
    return count


def _find_line_combination(
    lines: list[dict],
    target: Decimal,
    tolerance: Decimal = Decimal("0.02"),
    max_combo_size: int = 6,
) -> list[dict] | None:
    """Return the smallest subset of lines whose abs(paid_amount) sums within tolerance of target.

    Searches combinations up to max_combo_size to avoid exponential blow-up on large inputs.
    """
    eligible = [ln for ln in lines if ln.get("paid_amount") is not None]
    limit = min(len(eligible), max_combo_size)
    for size in range(1, limit + 1):
        for combo in combinations(eligible, size):
            combo_sum = sum((abs(c["paid_amount"]) for c in combo), Decimal("0.00"))
            if abs(combo_sum - target) <= tolerance:
                return list(combo)
    return None


def _status_for_confidence(score: Decimal) -> MatchStatus:
    if score >= Decimal("0.85"):
        return MatchStatus.AUTO_MATCHED
    if score >= Decimal("0.65"):
        return MatchStatus.PARTIAL_MATCH
    return MatchStatus.MANUAL_REVIEW


def match_bank_to_remittance(
    bank_rows: list[dict],
    remittance_headers: list[dict],
    lines_by_header: dict[str, list[dict]],
) -> list[dict]:
    """Match bank statement rows against remittance advice headers and their lines.

    Matching strategy (evaluated in priority order for each bank row):

    Step 1 – Header reference matching
        Compare header.bank_reference / buyer_reference / buyer_account_number against
        the same fields on each bank row:
          - 2+ fields match → high-confidence base (0.80)
          -  1 field  match → low-confidence  base (0.55)

        After a reference match, resolve the amount:
          a) header.total_paid_amount ≈ bank.amount  → +0.12 confidence (AUTO_MATCHED/PARTIAL)
          b) A subset of the header's lines sums to bank.amount → +0.08 confidence
          c) No amount agreement                     → -0.10 confidence (MANUAL_REVIEW)

        The header with the best (ref_score, amount_match_type) is selected. Only one
        header is chosen per bank row.

    Step 2 – Line buyer_reference fallback
        Applied only when no header reference matched at all.
        remittance_advice_lines.buyer_reference == bank.buyer_reference → 0.55 (MANUAL_REVIEW)

    Step 3 – No match
        A sentinel no_match candidate (confidence 0.10, UNMATCHED) is emitted so every
        bank row has at least one candidate record.

    Args:
        bank_rows: dicts with keys id, amount, bank_reference, buyer_reference,
                   buyer_account_number, payment_purpose.
        remittance_headers: dicts with keys id, bank_reference, buyer_reference,
                            buyer_account_number, total_paid_amount.
        lines_by_header: mapping of str(header_id) → list of line dicts with keys
                         id, invoice_number, paid_amount, buyer_reference.

    Returns:
        List of candidate match dicts compatible with ReconciliationMatch.
    """
    # Base confidence per reference match strength
    _HIGH_BASE = Decimal("0.80")  # 2+ ref fields matched
    _LOW_BASE = Decimal("0.55")  # 1 ref field matched

    candidates: list[dict] = []

    for bank in bank_rows:
        bank_amount = abs(bank["amount"])
        local_candidates: list[dict] = []

        # ── Step 1: Score every header and pick the best candidate ───────────
        # attempts: (ref_score, amount_type, header, matched_lines)
        # amount_type: 2 = total exact, 1 = line combo, 0 = no match
        attempts: list[tuple] = []
        for header in remittance_headers:
            rc = _ref_match_count(header, bank)
            if rc == 0:
                continue
            header_lines = lines_by_header.get(str(header["id"]), [])
            total_paid = header.get("total_paid_amount")

            if total_paid is not None and abs(abs(total_paid) - bank_amount) <= Decimal(
                "0.02"
            ):
                attempts.append((rc, 2, header, header_lines))
            else:
                combo = _find_line_combination(header_lines, bank_amount)
                if combo is not None:
                    attempts.append((rc, 1, header, combo))
                else:
                    attempts.append((rc, 0, header, header_lines))

        # Best header: highest ref_score first, then best amount_type
        attempts.sort(key=lambda x: (x[0], x[1]), reverse=True)

        if attempts:
            ref_score, amount_type, header, matched_lines = attempts[0]
            high_ref = ref_score >= 2
            base_conf = _HIGH_BASE if high_ref else _LOW_BASE
            ref_label = "high_ref" if high_ref else "low_ref"

            if amount_type == 2:
                conf = base_conf + Decimal("0.12")
                rule = f"{ref_label}_total_amount_exact"
                for line in matched_lines:
                    local_candidates.append(
                        {
                            "bank_statement_line_id": bank["id"],
                            "remittance_advice_line_id": line["id"],
                            "match_rule": rule,
                            "confidence_score": conf,
                            "amount_applied": line.get("paid_amount"),
                            "variance_amount": Decimal("0.00"),
                            "status": _status_for_confidence(conf),
                            "source": "RULE",
                            "is_selected": True,
                        }
                    )

            elif amount_type == 1:
                conf = base_conf + Decimal("0.08")
                rule = f"{ref_label}_line_combo_amount"
                for line in matched_lines:
                    local_candidates.append(
                        {
                            "bank_statement_line_id": bank["id"],
                            "remittance_advice_line_id": line["id"],
                            "match_rule": rule,
                            "confidence_score": conf,
                            "amount_applied": line.get("paid_amount"),
                            "variance_amount": Decimal("0.00"),
                            "status": _status_for_confidence(conf),
                            "source": "RULE",
                            "is_selected": True,
                        }
                    )

            else:  # amount_type == 0: ref matched but amounts disagree
                conf = max(base_conf - Decimal("0.10"), Decimal("0.10"))
                rule = f"{ref_label}_no_amount_match"
                total_paid = header.get("total_paid_amount")
                variance = bank_amount - (
                    abs(total_paid) if total_paid else Decimal("0.00")
                )
                for line in matched_lines:
                    local_candidates.append(
                        {
                            "bank_statement_line_id": bank["id"],
                            "remittance_advice_line_id": line["id"],
                            "match_rule": rule,
                            "confidence_score": conf,
                            "amount_applied": line.get("paid_amount"),
                            "variance_amount": variance,
                            "status": MatchStatus.MANUAL_REVIEW,
                            "source": "RULE",
                            "is_selected": True,
                        }
                    )

        # ── Step 2: Line buyer_reference fallback ────────────────────────────
        if not local_candidates:
            for header in remittance_headers:
                for line in lines_by_header.get(str(header["id"]), []):
                    line_bref = _norm(line.get("buyer_reference"))
                    bank_bref = _norm(bank.get("buyer_reference"))
                    if line_bref and bank_bref and line_bref == bank_bref:
                        paid = line.get("paid_amount")
                        variance = (
                            bank_amount - abs(paid) if paid is not None else bank_amount
                        )
                        local_candidates.append(
                            {
                                "bank_statement_line_id": bank["id"],
                                "remittance_advice_line_id": line["id"],
                                "match_rule": "line_buyer_ref_match",
                                "confidence_score": Decimal("0.55"),
                                "amount_applied": paid,
                                "variance_amount": variance,
                                "status": MatchStatus.MANUAL_REVIEW,
                                "source": "RULE",
                                "is_selected": True,
                            }
                        )

        # ── Step 3: No match sentinel ─────────────────────────────────────────
        if not local_candidates:
            local_candidates.append(
                {
                    "bank_statement_line_id": bank["id"],
                    "remittance_advice_line_id": None,
                    "match_rule": "no_match",
                    "confidence_score": Decimal("0.10"),
                    "amount_applied": None,
                    "variance_amount": bank_amount,
                    "status": MatchStatus.UNMATCHED,
                    "source": "RULE",
                    "is_selected": True,
                }
            )

        # Sort descending by confidence; ensure is_selected is boolean
        local_candidates.sort(key=lambda c: c["confidence_score"], reverse=True)
        any_preselected = any(c.get("is_selected") for c in local_candidates)
        if any_preselected:
            for c in local_candidates:
                c["is_selected"] = bool(c.get("is_selected"))
        else:
            local_candidates[0]["is_selected"] = True
            for c in local_candidates[1:]:
                c["is_selected"] = False

        candidates.extend(local_candidates)

    return candidates


def generate_match_candidates(
    bank_lines: list[dict], remittance_lines: list[dict]
) -> list[dict]:
    candidates: list[dict] = []
    used_remittance_ids: set[str] = set()

    for bank in bank_lines:
        bank_amount = abs(bank["amount"])
        local_candidates: list[dict] = []
        remaining = [
            r
            for r in remittance_lines
            if r["id"] not in used_remittance_ids and r.get("paid_amount") is not None
        ]

        # Rule 0: full remittance set equals one bank payment (header-total equivalent).
        if remaining:
            full_sum = sum((abs(r["paid_amount"]) for r in remaining), Decimal("0.00"))
            if abs(full_sum - bank_amount) <= Decimal("0.02"):
                for rem in remaining:
                    local_candidates.append(
                        {
                            "bank_statement_line_id": bank["id"],
                            "remittance_advice_line_id": rem["id"],
                            "match_rule": "header_total_amount_exact",
                            "confidence_score": Decimal("0.97"),
                            "amount_applied": rem["paid_amount"],
                            "variance_amount": Decimal("0.00"),
                            "status": MatchStatus.AUTO_MATCHED,
                            "source": "RULE",
                            "is_selected": True,
                        }
                    )
                candidates.extend(local_candidates)
                used_remittance_ids.update(rem["id"] for rem in remaining)
                continue

        # Rule 1: exact reference based matching
        for rem in remittance_lines:
            if rem["id"] in used_remittance_ids:
                continue
            invoice_number = rem.get("invoice_number")
            if invoice_number and (
                _contains(bank.get("bank_reference"), invoice_number)
                or _contains(bank.get("buyer_reference"), invoice_number)
                or _contains(bank.get("payment_purpose"), invoice_number)
            ):
                variance = bank_amount - (rem.get("paid_amount") or Decimal("0.00"))
                local_candidates.append(
                    {
                        "bank_statement_line_id": bank["id"],
                        "remittance_advice_line_id": rem["id"],
                        "match_rule": "invoice_reference_exact",
                        "confidence_score": Decimal("0.96"),
                        "amount_applied": rem.get("paid_amount") or Decimal("0.00"),
                        "variance_amount": variance,
                        "status": MatchStatus.AUTO_MATCHED,
                        "source": "RULE",
                    }
                )

        # Rule 2: exact amount single line
        for rem in remittance_lines:
            if rem["id"] in used_remittance_ids:
                continue
            paid = rem.get("paid_amount")
            if paid is None:
                continue
            if abs(bank_amount - abs(paid)) <= Decimal("0.02"):
                local_candidates.append(
                    {
                        "bank_statement_line_id": bank["id"],
                        "remittance_advice_line_id": rem["id"],
                        "match_rule": "single_line_amount_exact",
                        "confidence_score": Decimal("0.90"),
                        "amount_applied": paid,
                        "variance_amount": Decimal("0.00"),
                        "status": MatchStatus.AUTO_MATCHED,
                        "source": "RULE",
                    }
                )

        # Rule 3: aggregate 2-3 remittance lines
        agg_selected: list[dict] = []
        for size in (2, 3):
            if len(remaining) < size:
                continue
            found = False
            for combo in combinations(remaining, size):
                combo_sum = sum((abs(c["paid_amount"]) for c in combo), Decimal("0.00"))
                if abs(combo_sum - bank_amount) <= Decimal("0.02"):
                    for rem in combo:
                        agg_selected.append(
                            {
                                "bank_statement_line_id": bank["id"],
                                "remittance_advice_line_id": rem["id"],
                                "match_rule": f"aggregate_{size}_line_amount",
                                "confidence_score": Decimal("0.88"),
                                "amount_applied": rem["paid_amount"],
                                "variance_amount": Decimal("0.00"),
                                "status": MatchStatus.PARTIAL_MATCH,
                                "source": "RULE",
                                "is_selected": True,
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
                paid = abs(rem.get("paid_amount") or Decimal("0.00"))
                if paid == 0:
                    continue
                if paid < bank_amount:
                    variance = bank_amount - paid
                    cand = {
                        "bank_statement_line_id": bank["id"],
                        "remittance_advice_line_id": rem["id"],
                        "match_rule": "partial_amount_fallback",
                        "confidence_score": Decimal("0.70"),
                        "amount_applied": rem.get("paid_amount"),
                        "variance_amount": variance,
                        "status": MatchStatus.MANUAL_REVIEW,
                        "source": "RULE",
                    }
                    if (
                        best_partial is None
                        or cand["variance_amount"] < best_partial["variance_amount"]
                    ):
                        best_partial = cand
            if best_partial:
                local_candidates.append(best_partial)

        if not local_candidates:
            local_candidates.append(
                {
                    "bank_statement_line_id": bank["id"],
                    "remittance_advice_line_id": None,
                    "match_rule": "no_match",
                    "confidence_score": Decimal("0.10"),
                    "amount_applied": None,
                    "variance_amount": bank_amount,
                    "status": MatchStatus.UNMATCHED,
                    "source": "RULE",
                }
            )

        local_candidates.sort(key=lambda c: c["confidence_score"], reverse=True)
        if local_candidates:
            any_preselected = any(c.get("is_selected") for c in local_candidates)
            if any_preselected:
                for cand in local_candidates:
                    cand["is_selected"] = bool(cand.get("is_selected"))
            else:
                local_candidates[0]["is_selected"] = True
                for cand in local_candidates[1:]:
                    cand["is_selected"] = False

            used_remittance_ids.update(
                c["remittance_advice_line_id"]
                for c in local_candidates
                if c.get("is_selected") and c.get("remittance_advice_line_id")
            )
        candidates.extend(local_candidates)

    return candidates
