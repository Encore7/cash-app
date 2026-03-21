"""rename payer_name to buyer_name in remittance_advice_headers

Revision ID: i3c4d5e6f7a8
Revises: h2b3c4d5e6f7
Create Date: 2026-03-21 00:00:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "i3c4d5e6f7a8"
down_revision: Union[str, None] = "h2b3c4d5e6f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "remittance_advice_headers",
        "payer_name",
        new_column_name="buyer_name",
    )


def downgrade() -> None:
    op.alter_column(
        "remittance_advice_headers",
        "buyer_name",
        new_column_name="payer_name",
    )
