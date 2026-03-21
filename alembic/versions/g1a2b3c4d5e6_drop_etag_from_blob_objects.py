"""drop etag from blob_objects

Revision ID: g1a2b3c4d5e6
Revises: f2a6b8c4d9e1
Create Date: 2026-03-21 00:00:00.000000

"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "g1a2b3c4d5e6"
down_revision = "f2a6b8c4d9e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("blob_objects", "etag")


def downgrade() -> None:
    op.add_column(
        "blob_objects",
        sa.Column("etag", sa.String(length=128), nullable=True),
    )
