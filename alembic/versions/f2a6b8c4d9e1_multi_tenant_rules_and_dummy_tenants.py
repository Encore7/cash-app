"""multi_tenant_rules_and_dummy_tenants

Revision ID: f2a6b8c4d9e1
Revises: e1f5a9b3c7d2
Create Date: 2025-01-01 00:00:00.000000

"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "f2a6b8c4d9e1"
down_revision = "e1f5a9b3c7d2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add rule_type column to job_schedule_rules
    op.add_column(
        "job_schedule_rules",
        sa.Column(
            "rule_type", sa.String(20), nullable=False, server_default="processing"
        ),
    )

    # 2. Drop old single tenant_id FK from job_schedule_rules
    op.drop_constraint(
        "job_schedule_rules_tenant_id_fkey", "job_schedule_rules", type_="foreignkey"
    )
    op.drop_column("job_schedule_rules", "tenant_id")

    # 3. Create junction table for rule <-> tenant many-to-many
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


def downgrade() -> None:
    op.drop_table("job_schedule_rule_tenants")

    op.add_column(
        "job_schedule_rules",
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        "job_schedule_rules_tenant_id_fkey",
        "job_schedule_rules",
        "tenants",
        ["tenant_id"],
        ["id"],
    )

    op.drop_column("job_schedule_rules", "rule_type")
