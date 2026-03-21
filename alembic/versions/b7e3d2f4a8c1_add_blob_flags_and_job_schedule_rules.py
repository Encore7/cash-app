"""add blob flags and job schedule rules

Revision ID: b7e3d2f4a8c1
Revises: d4a3e8bf1c5a
Create Date: 2026-03-21 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b7e3d2f4a8c1"
down_revision: Union[str, Sequence[str], None] = "d4a3e8bf1c5a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new columns to blob_objects (IF NOT EXISTS is idempotent on replay)
    op.execute(
        "ALTER TABLE blob_objects ADD COLUMN IF NOT EXISTS original_file_name VARCHAR(255)"
    )
    op.execute(
        "ALTER TABLE blob_objects ADD COLUMN IF NOT EXISTS is_parsed BOOLEAN NOT NULL DEFAULT false"
    )
    op.execute(
        "ALTER TABLE blob_objects ADD COLUMN IF NOT EXISTS is_matched BOOLEAN NOT NULL DEFAULT false"
    )

    # Create enum type only if it does not already exist
    op.execute(
        """
        DO $$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'schedulefrequency') THEN
                CREATE TYPE schedulefrequency AS ENUM ('daily', 'weekly', 'monthly');
            END IF;
        END $$;
    """
    )

    # Create the scheduling rules table using raw SQL to avoid SQLAlchemy
    # re-issuing CREATE TYPE for the enum column
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS job_schedule_rules (
            id UUID NOT NULL PRIMARY KEY,
            tenant_id UUID REFERENCES tenants(id),
            frequency schedulefrequency NOT NULL,
            day_of_week INTEGER,
            day_of_month INTEGER,
            run_time VARCHAR(5) NOT NULL,
            is_active BOOLEAN NOT NULL DEFAULT true,
            created_at TIMESTAMPTZ NOT NULL,
            last_triggered_at TIMESTAMPTZ
        )
    """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS job_schedule_rules")
    op.execute("DROP TYPE IF EXISTS schedulefrequency")
    op.execute("ALTER TABLE blob_objects DROP COLUMN IF EXISTS is_matched")
    op.execute("ALTER TABLE blob_objects DROP COLUMN IF EXISTS is_parsed")
    op.execute("ALTER TABLE blob_objects DROP COLUMN IF EXISTS original_file_name")
