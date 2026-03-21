"""flatten bank and journal tables

Revision ID: d4a3e8bf1c5a
Revises: c2f4a7c91e10
Create Date: 2026-03-21 11:45:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'd4a3e8bf1c5a'
down_revision: Union[str, Sequence[str], None] = 'c2f4a7c91e10'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('bank_statement_lines', sa.Column('blob_object_id', sa.UUID(), nullable=True))
    op.execute(
        """
        UPDATE bank_statement_lines bsl
        SET blob_object_id = bsh.blob_object_id
        FROM bank_statement_headers bsh
        WHERE bsh.id = bsl.statement_header_id
        """
    )

    with op.batch_alter_table('bank_statement_lines') as batch_op:
        batch_op.alter_column('blob_object_id', existing_type=sa.UUID(), nullable=False)
        batch_op.drop_constraint('uq_bank_line_number', type_='unique')
        batch_op.drop_constraint('bank_statement_lines_statement_header_id_fkey', type_='foreignkey')
        batch_op.drop_column('statement_header_id')
        batch_op.drop_column('counterparty_account')
        batch_op.drop_column('bic')
        batch_op.drop_column('bank_name')
        batch_op.drop_column('bank_code')
        batch_op.drop_column('booking_text')
        batch_op.drop_column('iban')
        batch_op.drop_column('account_label')
        batch_op.drop_column('account_number')
        batch_op.drop_column('raw_payload')
        batch_op.create_unique_constraint('uq_bank_statement_line', ['blob_object_id', 'line_number'])
        batch_op.create_foreign_key('bank_statement_blob_object_id_fkey', 'blob_objects', ['blob_object_id'], ['id'])

    op.rename_table('bank_statement_lines', 'bank_statement')
    op.drop_table('bank_statement_headers')

    with op.batch_alter_table('reconciliation_matches') as batch_op:
        batch_op.alter_column('bank_statement_line_id', new_column_name='bank_statement_id')

    op.create_table(
        'journal_entry',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('run_id', sa.UUID(), nullable=False),
        sa.Column('line_number', sa.Integer(), nullable=False),
        sa.Column('company_code', sa.String(length=20), nullable=False),
        sa.Column('posting_date', sa.Date(), nullable=False),
        sa.Column('document_date', sa.Date(), nullable=False),
        sa.Column('document_type', sa.String(length=10), nullable=False),
        sa.Column('gl_account', sa.String(length=20), nullable=False),
        sa.Column('debit', sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column('credit', sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column('currency', sa.String(length=3), nullable=False),
        sa.Column('item_text', sa.String(length=255), nullable=True),
        sa.Column('source_file_name', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('reconciliation_match_id', sa.UUID(), nullable=True),
        sa.Column('bank_statement_id', sa.UUID(), nullable=True),
        sa.Column('remittance_advice_line_id', sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(['run_id'], ['ingestion_runs.id']),
        sa.ForeignKeyConstraint(['reconciliation_match_id'], ['reconciliation_matches.id']),
        sa.ForeignKeyConstraint(['bank_statement_id'], ['bank_statement.id']),
        sa.ForeignKeyConstraint(['remittance_advice_line_id'], ['remittance_advice_lines.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    op.execute(
        """
        INSERT INTO journal_entry (
            id,
            run_id,
            line_number,
            company_code,
            posting_date,
            document_date,
            document_type,
            gl_account,
            debit,
            credit,
            currency,
            item_text,
            source_file_name,
            created_at,
            reconciliation_match_id,
            bank_statement_id,
            remittance_advice_line_id
        )
        SELECT
            jel.id,
            jeh.run_id,
            jel.line_number,
            jeh.company_code,
            jeh.posting_date,
            jeh.document_date,
            jeh.document_type,
            jel.gl_account,
            jel.debit,
            jel.credit,
            jel.currency,
            jel.item_text,
            jeh.source_file_name,
            jeh.created_at,
            jel.reconciliation_match_id,
            jel.bank_statement_line_id,
            jel.remittance_advice_line_id
        FROM journal_entry_lines jel
        INNER JOIN journal_entry_headers jeh ON jeh.id = jel.journal_header_id
        """
    )

    op.drop_table('journal_entry_lines')
    op.drop_table('journal_entry_headers')


def downgrade() -> None:
    op.create_table(
        'journal_entry_headers',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('run_id', sa.UUID(), nullable=False),
        sa.Column('company_code', sa.String(length=20), nullable=False),
        sa.Column('posting_date', sa.Date(), nullable=False),
        sa.Column('document_date', sa.Date(), nullable=False),
        sa.Column('document_type', sa.String(length=10), nullable=False),
        sa.Column('currency', sa.String(length=3), nullable=False),
        sa.Column('source_file_name', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['run_id'], ['ingestion_runs.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'journal_entry_lines',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('journal_header_id', sa.UUID(), nullable=False),
        sa.Column('line_number', sa.Integer(), nullable=False),
        sa.Column('gl_account', sa.String(length=20), nullable=False),
        sa.Column('debit', sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column('credit', sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column('currency', sa.String(length=3), nullable=False),
        sa.Column('item_text', sa.String(length=255), nullable=True),
        sa.Column('reconciliation_match_id', sa.UUID(), nullable=True),
        sa.Column('bank_statement_line_id', sa.UUID(), nullable=True),
        sa.Column('remittance_advice_line_id', sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(['journal_header_id'], ['journal_entry_headers.id']),
        sa.ForeignKeyConstraint(['reconciliation_match_id'], ['reconciliation_matches.id']),
        sa.ForeignKeyConstraint(['bank_statement_line_id'], ['bank_statement.id']),
        sa.ForeignKeyConstraint(['remittance_advice_line_id'], ['remittance_advice_lines.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    op.execute(
        """
        INSERT INTO journal_entry_headers (
            id,
            run_id,
            company_code,
            posting_date,
            document_date,
            document_type,
            currency,
            source_file_name,
            created_at
        )
        SELECT
            gen_random_uuid(),
            je.run_id,
            je.company_code,
            je.posting_date,
            je.document_date,
            je.document_type,
            je.currency,
            je.source_file_name,
            min(je.created_at)
        FROM journal_entry je
        GROUP BY je.run_id, je.company_code, je.posting_date, je.document_date, je.document_type, je.currency, je.source_file_name
        """
    )

    op.execute(
        """
        INSERT INTO journal_entry_lines (
            id,
            journal_header_id,
            line_number,
            gl_account,
            debit,
            credit,
            currency,
            item_text,
            reconciliation_match_id,
            bank_statement_line_id,
            remittance_advice_line_id
        )
        SELECT
            je.id,
            jeh.id,
            je.line_number,
            je.gl_account,
            je.debit,
            je.credit,
            je.currency,
            je.item_text,
            je.reconciliation_match_id,
            je.bank_statement_id,
            je.remittance_advice_line_id
        FROM journal_entry je
        INNER JOIN journal_entry_headers jeh ON jeh.run_id = je.run_id
        """
    )

    op.drop_table('journal_entry')

    with op.batch_alter_table('reconciliation_matches') as batch_op:
        batch_op.alter_column('bank_statement_id', new_column_name='bank_statement_line_id')

    op.rename_table('bank_statement', 'bank_statement_lines')

    with op.batch_alter_table('bank_statement_lines') as batch_op:
        batch_op.drop_constraint('uq_bank_statement_line', type_='unique')
        batch_op.drop_constraint('bank_statement_blob_object_id_fkey', type_='foreignkey')
        batch_op.add_column(sa.Column('statement_header_id', sa.UUID(), nullable=True))
        batch_op.add_column(sa.Column('counterparty_account', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('bic', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('bank_name', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('bank_code', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('booking_text', sa.String(length=120), nullable=True))
        batch_op.add_column(sa.Column('iban', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('account_label', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('account_number', sa.String(length=40), nullable=True))
        batch_op.add_column(sa.Column('raw_payload', sa.JSON(), nullable=True))
        batch_op.create_unique_constraint('uq_bank_line_number', ['statement_header_id', 'line_number'])

    op.create_table(
        'bank_statement_headers',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('blob_object_id', sa.UUID(), nullable=False),
        sa.Column('sheet_name', sa.String(length=120), nullable=False, server_default='Sheet1'),
        sa.Column('source_file_name', sa.String(length=255), nullable=True),
        sa.Column('statement_currency', sa.String(length=3), nullable=True),
        sa.Column('line_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_credit_amount', sa.Numeric(precision=18, scale=2), nullable=False, server_default='0'),
        sa.Column('total_debit_amount', sa.Numeric(precision=18, scale=2), nullable=False, server_default='0'),
        sa.Column('parsed_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['blob_object_id'], ['blob_objects.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('blob_object_id'),
    )

    op.execute(
        """
        INSERT INTO bank_statement_headers (
            id,
            blob_object_id,
            source_file_name,
            statement_currency,
            line_count,
            total_credit_amount,
            total_debit_amount,
            parsed_at
        )
        SELECT
            gen_random_uuid(),
            bs.blob_object_id,
            bo.blob_path,
            'EUR',
            count(*),
            sum(CASE WHEN bs.amount > 0 THEN bs.amount ELSE 0 END),
            sum(CASE WHEN bs.amount < 0 THEN abs(bs.amount) ELSE 0 END),
            now()
        FROM bank_statement_lines bs
        INNER JOIN blob_objects bo ON bo.id = bs.blob_object_id
        GROUP BY bs.blob_object_id, bo.blob_path
        """
    )

    op.execute(
        """
        UPDATE bank_statement_lines bsl
        SET statement_header_id = bsh.id
        FROM bank_statement_headers bsh
        WHERE bsh.blob_object_id = bsl.blob_object_id
        """
    )

    with op.batch_alter_table('bank_statement_lines') as batch_op:
        batch_op.alter_column('statement_header_id', existing_type=sa.UUID(), nullable=False)
        batch_op.create_foreign_key(
            'bank_statement_lines_statement_header_id_fkey',
            'bank_statement_headers',
            ['statement_header_id'],
            ['id'],
        )
        batch_op.drop_column('blob_object_id')

