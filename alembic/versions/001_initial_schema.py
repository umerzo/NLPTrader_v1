"""Initial schema — full spec §3

Revision ID: 001
Revises:
Create Date: 2024-01-01 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, BIGINT
from pgvector.sqlalchemy import VECTOR

revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # tickers
    op.create_table(
        'tickers',
        sa.Column('ticker', sa.String(20), primary_key=True),
        sa.Column('display_name', sa.Text(), nullable=True),
        sa.Column('asset_type', sa.String(20), nullable=True),
        sa.Column('first_added_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('last_refreshed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_actively_tracked', sa.Boolean(), server_default='true', nullable=False),
    )

    # raw_articles
    op.create_table(
        'raw_articles',
        sa.Column('id', BIGINT(), autoincrement=True, nullable=False),
        sa.Column('source', sa.String(50), nullable=False),
        sa.Column('source_id', sa.String(200), nullable=False),
        sa.Column('url', sa.Text(), nullable=False),
        sa.Column('headline', sa.Text(), nullable=False),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('ingested_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('sentiment', sa.String(20), nullable=True),
        sa.Column('sentiment_score', sa.Numeric(5, 4), nullable=True),
        sa.Column('sentiment_scored_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('embedding', VECTOR(384), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('source', 'source_id', name='uq_article_source'),
    )

    # article_tickers (many-to-many)
    op.create_table(
        'article_tickers',
        sa.Column('article_id', BIGINT(), nullable=False),
        sa.Column('ticker', sa.String(20), nullable=False),
        sa.Column('event_type', sa.String(30), nullable=True),
        sa.Column('relevance', sa.Numeric(5, 4), nullable=True),
        sa.PrimaryKeyConstraint('article_id', 'ticker'),
        sa.ForeignKeyConstraint(['article_id'], ['raw_articles.id'], ),
        sa.ForeignKeyConstraint(['ticker'], ['tickers.ticker'], ),
    )

    # price_ohlcv
    op.create_table(
        'price_ohlcv',
        sa.Column('ticker', sa.String(20), nullable=False),
        sa.Column('timeframe', sa.String(10), nullable=False),
        sa.Column('ts', sa.DateTime(timezone=True), nullable=False),
        sa.Column('open', sa.Numeric(18, 8), nullable=False),
        sa.Column('high', sa.Numeric(18, 8), nullable=False),
        sa.Column('low', sa.Numeric(18, 8), nullable=False),
        sa.Column('close', sa.Numeric(18, 8), nullable=False),
        sa.Column('volume', sa.Numeric(24, 8), nullable=True),
        sa.PrimaryKeyConstraint('ticker', 'timeframe', 'ts'),
    )

    # signals
    op.create_table(
        'signals',
        sa.Column('id', BIGINT(), autoincrement=True, nullable=False),
        sa.Column('ticker', sa.String(20), nullable=False),
        sa.Column('generated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('status', sa.String(20), server_default='active', nullable=False),
        sa.Column('signal', sa.String(10), nullable=False),
        sa.Column('confidence', sa.SmallInteger(), nullable=False),
        sa.Column('regime', sa.String(20), nullable=True),
        sa.Column('entry_price', sa.Numeric(18, 8), nullable=True),
        sa.Column('stop_loss', sa.Numeric(18, 8), nullable=True),
        sa.Column('take_profit_1', sa.Numeric(18, 8), nullable=True),
        sa.Column('take_profit_2', sa.Numeric(18, 8), nullable=True),
        sa.Column('take_profit_3', sa.Numeric(18, 8), nullable=True),
        sa.Column('ta_subsignal', JSONB(), nullable=True),
        sa.Column('sentiment_subsignal', JSONB(), nullable=True),
        sa.Column('fundamental_subsignal', JSONB(), nullable=True),
        sa.Column('combiner_reasoning', sa.Text(), nullable=True),
        sa.Column('llm_explanation', sa.Text(), nullable=True),
        sa.Column('llm_model_used', sa.String(50), nullable=True),
        sa.Column('model_version', sa.String(50), server_default='v1', nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_signals_ticker_gen', 'signals', ['ticker', 'generated_at'])
    op.create_index('ix_signals_active', 'signals', ['ticker', 'status'])

    # outcomes
    op.create_table(
        'outcomes',
        sa.Column('id', BIGINT(), autoincrement=True, nullable=False),
        sa.Column('signal_id', BIGINT(), nullable=False),
        sa.Column('evaluated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('outcome', sa.String(20), nullable=False),
        sa.Column('exit_price', sa.Numeric(18, 8), nullable=True),
        sa.Column('exit_reason', sa.String(20), nullable=True),
        sa.Column('return_pct', sa.Numeric(10, 4), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['signal_id'], ['signals.id'], ),
    )


def downgrade():
    op.drop_table('outcomes')
    op.drop_table('signals')
    op.drop_table('price_ohlcv')
    op.drop_table('article_tickers')
    op.drop_table('raw_articles')
    op.drop_table('tickers')
