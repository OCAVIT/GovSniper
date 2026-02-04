"""Initial schema - create all tables.

Revision ID: initial_schema
Revises:
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enum types
    tenderstatus = postgresql.ENUM(
        'NEW', 'DOWNLOADED', 'ANALYZED', 'NOTIFIED', 'SOLD',
        name='tenderstatus'
    )
    tenderstatus.create(op.get_bind(), checkfirst=True)

    paymentstatus = postgresql.ENUM(
        'pending', 'waiting_for_capture', 'succeeded', 'canceled', 'refunded',
        name='paymentstatus'
    )
    paymentstatus.create(op.get_bind(), checkfirst=True)

    notificationtype = postgresql.ENUM(
        'teaser', 'report',
        name='notificationtype'
    )
    notificationtype.create(op.get_bind(), checkfirst=True)

    notificationstatus = postgresql.ENUM(
        'pending', 'sent', 'failed', 'bounced',
        name='notificationstatus'
    )
    notificationstatus.create(op.get_bind(), checkfirst=True)

    # Create tenders table
    op.create_table(
        'tenders',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('external_id', sa.String(length=100), nullable=False),
        sa.Column('title', sa.String(length=1000), nullable=False),
        sa.Column('url', sa.String(length=2000), nullable=False),
        sa.Column('price', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('customer_name', sa.String(length=500), nullable=True),
        sa.Column('deadline', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.Enum('NEW', 'DOWNLOADED', 'ANALYZED', 'NOTIFIED', 'SOLD', name='tenderstatus'), nullable=False),
        sa.Column('raw_text', sa.Text(), nullable=True),
        sa.Column('risk_score', sa.Integer(), nullable=True),
        sa.Column('margin_estimate', sa.String(length=100), nullable=True),
        sa.Column('teaser_description', sa.Text(), nullable=True),
        sa.Column('deep_analysis', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_tenders_external_id', 'tenders', ['external_id'], unique=True)
    op.create_index('ix_tenders_status', 'tenders', ['status'], unique=False)
    op.create_index('ix_tenders_status_created', 'tenders', ['status', 'created_at'], unique=False)
    op.create_index('ix_tenders_price', 'tenders', ['price'], unique=False)

    # Create clients table
    op.create_table(
        'clients',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=True),
        sa.Column('company', sa.String(length=500), nullable=True),
        sa.Column('phone', sa.String(length=50), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('keywords', postgresql.ARRAY(sa.String(length=100)), nullable=False),
        sa.Column('min_price', sa.Integer(), nullable=True),
        sa.Column('max_price', sa.Integer(), nullable=True),
        sa.Column('regions', postgresql.ARRAY(sa.String(length=100)), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_clients_email', 'clients', ['email'], unique=True)

    # Create payments table
    op.create_table(
        'payments',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('yookassa_id', sa.String(length=100), nullable=False),
        sa.Column('tender_id', sa.Integer(), nullable=False),
        sa.Column('client_id', sa.Integer(), nullable=False),
        sa.Column('amount', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('currency', sa.String(length=3), nullable=False),
        sa.Column('status', sa.Enum('pending', 'waiting_for_capture', 'succeeded', 'canceled', 'refunded', name='paymentstatus'), nullable=False),
        sa.Column('confirmation_url', sa.String(length=2000), nullable=True),
        sa.Column('report_sent', sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tender_id'], ['tenders.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_payments_yookassa_id', 'payments', ['yookassa_id'], unique=True)

    # Create notifications table
    op.create_table(
        'notifications',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('tender_id', sa.Integer(), nullable=False),
        sa.Column('client_id', sa.Integer(), nullable=False),
        sa.Column('notification_type', sa.Enum('teaser', 'report', name='notificationtype'), nullable=False),
        sa.Column('status', sa.Enum('pending', 'sent', 'failed', 'bounced', name='notificationstatus'), nullable=False),
        sa.Column('resend_id', sa.String(length=100), nullable=True),
        sa.Column('error_message', sa.String(length=1000), nullable=True),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tender_id'], ['tenders.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_notifications_tender_client', 'notifications', ['tender_id', 'client_id'], unique=False)
    op.create_index('ix_notifications_type_status', 'notifications', ['notification_type', 'status'], unique=False)


def downgrade() -> None:
    # Drop tables
    op.drop_table('notifications')
    op.drop_table('payments')
    op.drop_table('clients')
    op.drop_table('tenders')

    # Drop enum types
    op.execute('DROP TYPE IF EXISTS notificationstatus')
    op.execute('DROP TYPE IF EXISTS notificationtype')
    op.execute('DROP TYPE IF EXISTS paymentstatus')
    op.execute('DROP TYPE IF EXISTS tenderstatus')
