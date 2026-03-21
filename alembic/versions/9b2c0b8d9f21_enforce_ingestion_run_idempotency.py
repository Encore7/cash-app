"""enforce ingestion run idempotency

Revision ID: 9b2c0b8d9f21
Revises: ce9049704dc3
Create Date: 2026-03-21 08:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '9b2c0b8d9f21'
down_revision: Union[str, Sequence[str], None] = 'ce9049704dc3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Remove legacy duplicates first, keeping the newest row per logical run slot.
    op.execute(
        """
        DELETE FROM ingestion_runs r
        USING (
            SELECT id
            FROM (
                SELECT
                    id,
                    row_number() OVER (
                        PARTITION BY tenant_id, business_date, bank_blob_id, remittance_blob_id
                        ORDER BY started_at DESC, id DESC
                    ) AS rn
                FROM ingestion_runs
                WHERE bank_blob_id IS NOT NULL
                  AND remittance_blob_id IS NOT NULL
            ) ranked
            WHERE ranked.rn > 1
        ) d
        WHERE r.id = d.id
        """
    )
    op.create_unique_constraint(
        'uq_ingestion_run_slot',
        'ingestion_runs',
        ['tenant_id', 'business_date', 'bank_blob_id', 'remittance_blob_id'],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('uq_ingestion_run_slot', 'ingestion_runs', type_='unique')

