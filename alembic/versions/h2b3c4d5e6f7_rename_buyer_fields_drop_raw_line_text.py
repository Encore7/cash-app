"""rename buyer fields, add account numbers, drop raw_line_text

bank_statement  : customer_reference → buyer_reference, + buyer_account_number
remittance_advice_headers : advice_number → buyer_reference, + bank_reference, + buyer_account_number
remittance_advice_lines   : customer_reference → buyer_reference, drop raw_line_text

Revision ID: h2b3c4d5e6f7
Revises: g1a2b3c4d5e6
Create Date: 2026-03-21 00:01:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "h2b3c4d5e6f7"
down_revision = "g1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── bank_statement ────────────────────────────────────────────
    op.alter_column(
        "bank_statement", "customer_reference", new_column_name="buyer_reference"
    )
    op.add_column(
        "bank_statement",
        sa.Column("buyer_account_number", sa.String(34), nullable=True),
    )

    # ── remittance_advice_headers ─────────────────────────────────
    op.alter_column(
        "remittance_advice_headers", "advice_number", new_column_name="buyer_reference"
    )
    op.add_column(
        "remittance_advice_headers",
        sa.Column("bank_reference", sa.String(120), nullable=True),
    )
    op.add_column(
        "remittance_advice_headers",
        sa.Column("buyer_account_number", sa.String(34), nullable=True),
    )

    # ── remittance_advice_lines ───────────────────────────────────
    op.alter_column(
        "remittance_advice_lines",
        "customer_reference",
        new_column_name="buyer_reference",
    )
    op.drop_column("remittance_advice_lines", "raw_line_text")


def downgrade() -> None:
    # ── remittance_advice_lines ───────────────────────────────────
    op.add_column(
        "remittance_advice_lines", sa.Column("raw_line_text", sa.Text(), nullable=True)
    )
    op.alter_column(
        "remittance_advice_lines",
        "buyer_reference",
        new_column_name="customer_reference",
    )

    # ── remittance_advice_headers ─────────────────────────────────
    op.drop_column("remittance_advice_headers", "buyer_account_number")
    op.drop_column("remittance_advice_headers", "bank_reference")
    op.alter_column(
        "remittance_advice_headers", "buyer_reference", new_column_name="advice_number"
    )

    # ── bank_statement ────────────────────────────────────────────
    op.drop_column("bank_statement", "buyer_account_number")
    op.alter_column(
        "bank_statement", "buyer_reference", new_column_name="customer_reference"
    )
