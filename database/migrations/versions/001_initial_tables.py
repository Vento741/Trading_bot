"""initial tables

Revision ID: 001
Revises: 
Create Date: 2024-01-27 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Создание таблицы positions
    op.create_table(
        'positions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('symbol', sa.String(20), nullable=False),
        sa.Column('side', sa.String(10), nullable=False),
        sa.Column('entry_price', sa.Numeric(), nullable=False),
        sa.Column('size', sa.Numeric(), nullable=False),
        sa.Column('take_profit', sa.Numeric()),
        sa.Column('stop_loss', sa.Numeric()),
        sa.Column('strategy', sa.String(50), nullable=False),
        sa.Column('exchange', sa.String(20), nullable=False),
        sa.Column('entry_time', sa.TIMESTAMP, nullable=False),
        sa.Column('exit_time', sa.TIMESTAMP),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('realized_pnl', sa.Numeric()),
        sa.Column('metadata', sa.JSON),
        sa.Column('created_at', sa.TIMESTAMP, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id')
    )

    # Создание таблицы orders
    op.create_table(
        'orders',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('position_id', sa.Integer()),
        sa.Column('symbol', sa.String(20), nullable=False),
        sa.Column('side', sa.String(10), nullable=False),
        sa.Column('order_type', sa.String(20), nullable=False),
        sa.Column('size', sa.Numeric(), nullable=False),
        sa.Column('price', sa.Numeric()),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('exchange', sa.String(20), nullable=False),
        sa.Column('exchange_order_id', sa.String(50)),
        sa.Column('created_at', sa.TIMESTAMP, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.TIMESTAMP, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['position_id'], ['positions.id'])
    )

    # Создание таблицы trades
    op.create_table(
        'trades',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('symbol', sa.String(20), nullable=False),
        sa.Column('price', sa.Numeric(), nullable=False),
        sa.Column('size', sa.Numeric(), nullable=False),
        sa.Column('side', sa.String(10), nullable=False),
        sa.Column('exchange', sa.String(20), nullable=False),
        sa.Column('timestamp', sa.TIMESTAMP, nullable=False),
        sa.Column('metadata', sa.JSON),
        sa.Column('created_at', sa.TIMESTAMP, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id')
    )

    # Создание таблицы metrics
    op.create_table(
        'metrics',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('metric_name', sa.String(50), nullable=False),
        sa.Column('metric_value', sa.Numeric(), nullable=False),
        sa.Column('symbol', sa.String(20)),
        sa.Column('strategy', sa.String(50)),
        sa.Column('timestamp', sa.TIMESTAMP, nullable=False),
        sa.Column('metadata', sa.JSON),
        sa.Column('created_at', sa.TIMESTAMP, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id')
    )

    # Создание индексов
    op.create_index('idx_positions_symbol', 'positions', ['symbol'])
    op.create_index('idx_positions_strategy', 'positions', ['strategy'])
    op.create_index('idx_orders_symbol', 'orders', ['symbol'])
    op.create_index('idx_trades_symbol', 'trades', ['symbol'])
    op.create_index('idx_trades_timestamp', 'trades', ['timestamp'])
    op.create_index('idx_metrics_name', 'metrics', ['metric_name'])
    op.create_index('idx_metrics_timestamp', 'metrics', ['timestamp'])


def downgrade() -> None:
    op.drop_table('metrics')
    op.drop_table('trades')
    op.drop_table('orders')
    op.drop_table('positions')