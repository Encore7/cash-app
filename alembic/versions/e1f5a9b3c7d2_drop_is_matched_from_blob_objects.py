"""drop is_matched from blob_objects

Revision ID: e1f5a9b3c7d2
Revises: b7e3d2f4a8c1
Create Date: 2026-03-21 13:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

revision: str = "e1f5a9b3c7d2"
down_revision: Union[str, Sequence[str], None] = "b7e3d2f4a8c1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE blob_objects DROP COLUMN IF EXISTS is_matched")


def downgrade() -> None:
    op.execute(
        "ALTER TABLE blob_objects ADD COLUMN IF NOT EXISTS is_matched BOOLEAN NOT NULL DEFAULT false"
    )
