"""Add tender_participants table and client source fields for lead generation.

Revision ID: add_participants
Revises: initial_schema
Create Date: 2025-02-05 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'add_participants'
down_revision: Union[str, None] = 'initial_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enum type for participant result
    participantresult = postgresql.ENUM(
        'WINNER', 'LOSER', 'REJECTED', 'WITHDRAWN',
        name='participantresult'
    )
    participantresult.create(op.get_bind(), checkfirst=True)

    # Create tender_participants table
    op.create_table(
        'tender_participants',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('tender_id', sa.Integer(), nullable=False),
        sa.Column('company_name', sa.String(length=500), nullable=False),
        sa.Column('inn', sa.String(length=12), nullable=True),
        sa.Column('kpp', sa.String(length=9), nullable=True),
        sa.Column('bid_amount', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('result', postgresql.ENUM('WINNER', 'LOSER', 'REJECTED', 'WITHDRAWN', name='participantresult', create_type=False), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=True),
        sa.Column('phone', sa.String(length=50), nullable=True),
        sa.Column('address', sa.Text(), nullable=True),
        sa.Column('contacts_fetched', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('client_created', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('email_sent', sa.Boolean(), nullable=False, server_default='false'),
        sa.ForeignKeyConstraint(['tender_id'], ['tenders.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_participants_tender_id', 'tender_participants', ['tender_id'], unique=False)
    op.create_index('ix_participants_inn', 'tender_participants', ['inn'], unique=False)
    op.create_index('ix_participants_inn_result', 'tender_participants', ['inn', 'result'], unique=False)
    op.create_index('ix_participants_contacts_fetched', 'tender_participants', ['contacts_fetched'], unique=False)
    op.create_index('ix_participants_client_created', 'tender_participants', ['client_created'], unique=False)

    # Add source tracking fields to clients table
    op.add_column('clients', sa.Column('source', sa.String(length=50), nullable=True))
    op.add_column('clients', sa.Column('source_inn', sa.String(length=12), nullable=True))
    op.add_column('clients', sa.Column('source_tender_id', sa.Integer(), nullable=True))
    op.create_index('ix_clients_source', 'clients', ['source'], unique=False)
    op.create_index('ix_clients_source_inn', 'clients', ['source_inn'], unique=False)


def downgrade() -> None:
    # Remove client source fields
    op.drop_index('ix_clients_source_inn', table_name='clients')
    op.drop_index('ix_clients_source', table_name='clients')
    op.drop_column('clients', 'source_tender_id')
    op.drop_column('clients', 'source_inn')
    op.drop_column('clients', 'source')

    # Drop tender_participants table
    op.drop_index('ix_participants_client_created', table_name='tender_participants')
    op.drop_index('ix_participants_contacts_fetched', table_name='tender_participants')
    op.drop_index('ix_participants_inn_result', table_name='tender_participants')
    op.drop_index('ix_participants_inn', table_name='tender_participants')
    op.drop_index('ix_participants_tender_id', table_name='tender_participants')
    op.drop_table('tender_participants')

    # Drop enum type
    op.execute('DROP TYPE IF EXISTS participantresult')
