"""trim schema to expected io

Revision ID: c2f4a7c91e10
Revises: 9b2c0b8d9f21
Create Date: 2026-03-21 08:20:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'c2f4a7c91e10'
down_revision: Union[str, Sequence[str], None] = '9b2c0b8d9f21'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_table('match_action_audit')

    op.drop_column('remittance_advice_headers', 'payer_iban')
    op.drop_column('remittance_advice_headers', 'payer_bic')
    op.drop_column('remittance_advice_headers', 'document_language')
    op.drop_column('remittance_advice_headers', 'remittance_subject')
    op.drop_column('remittance_advice_headers', 'raw_text')
    op.drop_column('remittance_advice_headers', 'ocr_engine')
    op.drop_column('remittance_advice_headers', 'parsing_confidence')
    op.drop_column('remittance_advice_headers', 'extraction_method')
    op.drop_column('remittance_advice_headers', 'llm_model')
    op.drop_column('remittance_advice_headers', 'llm_prompt_version')
    op.drop_column('remittance_advice_headers', 'raw_llm_output')
    op.drop_column('remittance_advice_headers', 'normalized_payload')
    op.drop_column('remittance_advice_headers', 'validation_errors')
    op.drop_column('remittance_advice_headers', 'parsed_at')

    op.drop_column('remittance_advice_lines', 'due_date')
    op.drop_column('remittance_advice_lines', 'gross_amount')
    op.drop_column('remittance_advice_lines', 'discount_amount')
    op.drop_column('remittance_advice_lines', 'deduction_amount')
    op.drop_column('remittance_advice_lines', 'assignment_text')


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column('remittance_advice_lines', sa.Column('assignment_text', sa.Text(), nullable=True))
    op.add_column('remittance_advice_lines', sa.Column('deduction_amount', sa.Numeric(precision=18, scale=2), nullable=True))
    op.add_column('remittance_advice_lines', sa.Column('discount_amount', sa.Numeric(precision=18, scale=2), nullable=True))
    op.add_column('remittance_advice_lines', sa.Column('gross_amount', sa.Numeric(precision=18, scale=2), nullable=True))
    op.add_column('remittance_advice_lines', sa.Column('due_date', sa.Date(), nullable=True))

    op.add_column('remittance_advice_headers', sa.Column('parsed_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('remittance_advice_headers', sa.Column('validation_errors', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('remittance_advice_headers', sa.Column('normalized_payload', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('remittance_advice_headers', sa.Column('raw_llm_output', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('remittance_advice_headers', sa.Column('llm_prompt_version', sa.String(length=40), nullable=True))
    op.add_column('remittance_advice_headers', sa.Column('llm_model', sa.String(length=120), nullable=True))
    op.add_column('remittance_advice_headers', sa.Column('extraction_method', sa.String(length=32), nullable=True))
    op.add_column('remittance_advice_headers', sa.Column('parsing_confidence', sa.Numeric(precision=5, scale=4), nullable=True))
    op.add_column('remittance_advice_headers', sa.Column('ocr_engine', sa.String(length=40), nullable=True))
    op.add_column('remittance_advice_headers', sa.Column('raw_text', sa.Text(), nullable=True))
    op.add_column('remittance_advice_headers', sa.Column('remittance_subject', sa.Text(), nullable=True))
    op.add_column(
        'remittance_advice_headers',
        sa.Column('document_language', sa.String(length=10), nullable=False, server_default='de'),
    )
    op.add_column('remittance_advice_headers', sa.Column('payer_bic', sa.String(length=20), nullable=True))
    op.add_column('remittance_advice_headers', sa.Column('payer_iban', sa.String(length=64), nullable=True))
    op.alter_column('remittance_advice_headers', 'document_language', server_default=None)

    op.create_table(
        'match_action_audit',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('run_id', sa.UUID(), nullable=False),
        sa.Column('match_id', sa.UUID(), nullable=True),
        sa.Column('action', sa.String(length=40), nullable=False),
        sa.Column('actor_id', sa.String(length=120), nullable=False),
        sa.Column('reason_code', sa.String(length=64), nullable=True),
        sa.Column('comment', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['match_id'], ['reconciliation_matches.id']),
        sa.ForeignKeyConstraint(['run_id'], ['ingestion_runs.id']),
        sa.PrimaryKeyConstraint('id'),
    )

