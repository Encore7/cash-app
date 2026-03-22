"""drop_rule_tenants_rename_currency

Revision ID: k5e6f7a8b9c0
Revises: j4d5e6f7a8b9
Create Date: 2026-03-22 00:00:00.000000

"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "k5e6f7a8b9c0"
down_revision = "j4d5e6f7a8b9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Drop the job_schedule_rule_tenants junction table
    op.drop_table("job_schedule_rule_tenants")

    # 2. Rename document_currency -> currency in remittance_advice_headers
    op.alter_column(
        "remittance_advice_headers",
        "document_currency",
        new_column_name="currency",
    )


def downgrade() -> None:
    # 2. Rename currency -> document_currency
    op.alter_column(
        "remittance_advice_headers",
        "currency",
        new_column_name="document_currency",
    )

    # 1. Re-create the job_schedule_rule_tenants table
    op.create_table(
        "job_schedule_rule_tenants",
        sa.Column("rule_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["rule_id"], ["job_schedule_rules.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("rule_id", "tenant_id"),
    )
