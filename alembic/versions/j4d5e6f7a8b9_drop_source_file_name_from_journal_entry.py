"""drop source_file_name from journal_entry

Revision ID: j4d5e6f7a8b9
Revises: i3c4d5e6f7a8
Create Date: 2026-03-22 00:00:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "j4d5e6f7a8b9"
down_revision: Union[str, None] = "i3c4d5e6f7a8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("journal_entry", "source_file_name")


def downgrade() -> None:
    op.add_column(
        "journal_entry",
        sa.Column("source_file_name", sa.String(length=255), nullable=True),
    )
