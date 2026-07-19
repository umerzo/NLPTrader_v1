"""Initial schema

Revision ID: 001
Revises:
Create Date: 2024-01-01 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # raw_articles
    op.create_table(
        'raw_articles',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('source', sa.String(50), nullable=False),
        sa.Column('source_id', sa.String(200), nullable=False),
        sa.Column('url', sa.String(500), nullable=False),
        sa.Column('ticker', sa.String(20), nullable=False),
        sa.Column('headline', sa.Text(), nullable=False),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('author', sa.String(200), nullable=True),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('fetched_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('raw_json', JSONB, nullable=True),
        sa.Column('sentiment', sa.String(20), nullable=True),
        sa.Column('sentiment_score', sa.Numeric(5, 4), nullable=True),
        sa.Column('sentiment_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('source', 'source_id', name='uq_article_source'),
    )
    op.create_index('ix_articles_ticker_published', 'raw_articles', ['ticker', 'published_at'])

    # price_ohlcv
    op.create_table(
        'price_ohlcv',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('ticker', sa.String(20), nullable=False),
        sa.Column('timeframe', sa.String(10), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('open', sa.Numeric(18, 8), nullable=False),
        sa.Column('high', sa.Numeric(18, 8), nullable=False),
        sa.Column('low', sa.Numeric(18, 8), nullable=False),
        sa.Column('close', sa.Numeric(18, 8), nullable=False),
        sa.Column('volume', sa.Numeric(24, 8), nullable=False),
        sa.Column('source', sa.String(50), server_default='yfinance'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('ticker', 'timeframe', 'timestamp', name='uq_price_tf_ts'),
    )
    op.create_index('ix_price_ticker_tf_ts', 'price_ohlcv', ['ticker', 'timeframe', 'timestamp'])

    # signals
    op.create_table(
        'signals',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('ticker', sa.String(20), nullable=False),
        sa.Column('generated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('model_version', sa.String(50), nullable=False),
        sa.Column('ta_signal', sa.String(10), nullable=True),
        sa.Column('ta_confidence', sa.SmallInteger(), nullable=True),
        sa.Column('ta_details', JSONB, nullable=True),
        sa.Column('sentiment_signal', sa.String(10), nullable=True),
        sa.Column('sentiment_confidence', sa.SmallInteger(), nullable=True),
        sa.Column('sentiment_details', JSONB, nullable=True),
        sa.Column('fundamental_signal', sa.String(10), nullable=True),
        sa.Column('fundamental_confidence', sa.SmallInteger(), nullable=True),
        sa.Column('fundamental_details', JSONB, nullable=True),
        sa.Column('combined_signal', sa.String(10), nullable=False),
        sa.Column('combined_confidence', sa.SmallInteger(), nullable=False),
        sa.Column('combined_reasoning', sa.Text(), nullable=True),
        sa.Column('prediction_horizon', sa.String(50), server_default='24h'),
        sa.Column('entry_price', sa.Numeric(18, 8), nullable=True),
        sa.Column('stop_loss', sa.Numeric(18, 8), nullable=True),
        sa.Column('take_profit_1', sa.Numeric(18, 8), nullable=True),
        sa.Column('take_profit_2', sa.Numeric(18, 8), nullable=True),
        sa.Column('take_profit_3', sa.Numeric(18, 8), nullable=True),
        sa.Column('regime', sa.String(20), nullable=True),
        sa.Column('status', sa.String(20), server_default='active'),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_signals_ticker_gen', 'signals', ['ticker', 'generated_at'])
    op.create_index('ix_signals_active', 'signals', ['ticker', 'status'])

    # outcomes
    op.create_table(
        'outcomes',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('signal_id', sa.BigInteger(), nullable=False),
        sa.Column('checked_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('current_price', sa.Numeric(18, 8), nullable=False),
        sa.Column('price_change_pct', sa.Numeric(10, 4), nullable=False),
        sa.Column('outcome', sa.String(20), nullable=False),
        sa.Column('hours_elapsed', sa.Numeric(8, 2), nullable=False),
        sa.Column('max_favorable_pct', sa.Numeric(10, 4), nullable=True),
        sa.Column('max_adverse_pct', sa.Numeric(10, 4), nullable=True),
        sa.Column('hit_sl', sa.Boolean(), server_default='false'),
        sa.Column('hit_tp1', sa.Boolean(), server_default='false'),
        sa.Column('hit_tp2', sa.Boolean(), server_default='false'),
        sa.Column('hit_tp3', sa.Boolean(), server_default='false'),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['signal_id'], ['signals.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('signal_id', name='uq_outcome_signal'),
    )
    op.create_index('ix_outcomes_signal', 'outcomes', ['signal_id'])

    # model_versions
    op.create_table(
        'model_versions',
        sa.Column('version', sa.String(50), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('config', JSONB, nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='false'),
        sa.Column('parent_version', sa.String(50), nullable=True),
        sa.PrimaryKeyConstraint('version'),
        sa.ForeignKeyConstraint(['parent_version'], ['model_versions.version']),
    )

    # backtest_runs
    op.create_table(
        'backtest_runs',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('model_version', sa.String(50), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('config', JSONB, nullable=True),
        sa.Column('metrics', JSONB, nullable=True),
        sa.Column('status', sa.String(20), server_default='running'),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['model_version'], ['model_versions.version']),
    )


def downgrade():
    op.drop_table('backtest_runs')
    op.drop_table('model_versions')
    op.drop_table('outcomes')
    op.drop_table('signals')
    op.drop_table('price_ohlcv')
    op.drop_table('raw_articles')