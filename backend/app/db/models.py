"""
models.py — SQLAlchemy 2.0 models (async).
All tables for the Decision Support system.
"""
from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy import (
    String, Text, DateTime, Integer, SmallInteger, Numeric, JSON, ForeignKey, UniqueConstraint, Index
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB
from backend.app.db.session import Base


class RawArticle(Base):
    __tablename__ = "raw_articles"
    __table_args__ = (
        UniqueConstraint("source", "source_id", name="uq_article_source"),
        Index("ix_articles_ticker_published", "ticker", "published_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    source_id: Mapped[str] = mapped_column(String(200), nullable=False)
    url: Mapped[str] = mapped_column(String(500), unique=True, nullable=False)
    ticker: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    headline: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(Text)
    author: Mapped[Optional[str]] = mapped_column(String(200))
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    raw_json: Mapped[Optional[dict]] = mapped_column(JSONB)

    # FinBERT sentiment (populated by sentiment engine)
    sentiment: Mapped[Optional[str]] = mapped_column(String(20))  # positive/negative/neutral
    sentiment_score: Mapped[Optional[float]] = mapped_column(Numeric(5, 4))
    sentiment_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class PriceOHLCV(Base):
    __tablename__ = "price_ohlcv"
    __table_args__ = (
        UniqueConstraint("ticker", "timeframe", "timestamp", name="uq_price_tf_ts"),
        Index("ix_price_ticker_tf_ts", "ticker", "timeframe", "timestamp"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    timeframe: Mapped[str] = mapped_column(String(10), nullable=False)  # 1m,5m,15m,1h,4h,1d
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    open: Mapped[float] = mapped_column(Numeric(18, 8), nullable=False)
    high: Mapped[float] = mapped_column(Numeric(18, 8), nullable=False)
    low: Mapped[float] = mapped_column(Numeric(18, 8), nullable=False)
    close: Mapped[float] = mapped_column(Numeric(18, 8), nullable=False)
    volume: Mapped[float] = mapped_column(Numeric(24, 8), nullable=False)
    source: Mapped[str] = mapped_column(String(50), default="yfinance")


class Signal(Base):
    __tablename__ = "signals"
    __table_args__ = (
        Index("ix_signals_ticker_gen", "ticker", "generated_at"),
        Index("ix_signals_active", "ticker", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    model_version: Mapped[str] = mapped_column(String(50), nullable=False)

    # Sub-signals (nullable - each engine independent)
    ta_signal: Mapped[Optional[str]] = mapped_column(String(10))
    ta_confidence: Mapped[Optional[int]] = mapped_column(SmallInteger)
    ta_details: Mapped[Optional[dict]] = mapped_column(JSONB)

    sentiment_signal: Mapped[Optional[str]] = mapped_column(String(10))
    sentiment_confidence: Mapped[Optional[int]] = mapped_column(SmallInteger)
    sentiment_details: Mapped[Optional[dict]] = mapped_column(JSONB)

    fundamental_signal: Mapped[Optional[str]] = mapped_column(String(10))
    fundamental_confidence: Mapped[Optional[int]] = mapped_column(SmallInteger)
    fundamental_details: Mapped[Optional[dict]] = mapped_column(JSONB)

    # Combined output
    combined_signal: Mapped[str] = mapped_column(String(10), nullable=False)
    combined_confidence: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    combined_reasoning: Mapped[Optional[str]] = mapped_column(Text)
    prediction_horizon: Mapped[str] = mapped_column(String(50), default="24h")
    entry_price: Mapped[Optional[float]] = mapped_column(Numeric(18, 8))
    stop_loss: Mapped[Optional[float]] = mapped_column(Numeric(18, 8))
    take_profit_1: Mapped[Optional[float]] = mapped_column(Numeric(18, 8))
    take_profit_2: Mapped[Optional[float]] = mapped_column(Numeric(18, 8))
    take_profit_3: Mapped[Optional[float]] = mapped_column(Numeric(18, 8))

    # Regime context
    regime: Mapped[Optional[str]] = mapped_column(String(20))

    # Lifecycle
    status: Mapped[str] = mapped_column(String(20), default="active")  # active, expired, cancelled
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Relationship
    outcome: Mapped[Optional["Outcome"]] = relationship(back_populates="signal", uselist=False)


class Outcome(Base):
    __tablename__ = "outcomes"
    __table_args__ = (Index("ix_outcomes_signal", "signal_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    signal_id: Mapped[int] = mapped_column(Integer, ForeignKey("signals.id", ondelete="CASCADE"), unique=True)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    current_price: Mapped[float] = mapped_column(Numeric(18, 8), nullable=False)
    price_change_pct: Mapped[float] = mapped_column(Numeric(10, 4), nullable=False)
    outcome: Mapped[str] = mapped_column(String(20), nullable=False)  # correct, incorrect, neutral, pending
    hours_elapsed: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)
    max_favorable_pct: Mapped[Optional[float]] = mapped_column(Numeric(10, 4))
    max_adverse_pct: Mapped[Optional[float]] = mapped_column(Numeric(10, 4))
    hit_sl: Mapped[bool] = mapped_column(default=False)
    hit_tp1: Mapped[bool] = mapped_column(default=False)
    hit_tp2: Mapped[bool] = mapped_column(default=False)
    hit_tp3: Mapped[bool] = mapped_column(default=False)

    signal: Mapped["Signal"] = relationship(back_populates="outcome")


class ModelVersion(Base):
    __tablename__ = "model_versions"

    version: Mapped[str] = mapped_column(String(50), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    description: Mapped[Optional[str]] = mapped_column(Text)
    config: Mapped[dict] = mapped_column(JSONB, nullable=False)
    is_active: Mapped[bool] = mapped_column(default=False)
    parent_version: Mapped[Optional[str]] = mapped_column(String(50), ForeignKey("model_versions.version"))


class BacktestRun(Base):
    __tablename__ = "backtest_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    model_version: Mapped[str] = mapped_column(String(50), ForeignKey("model_versions.version"))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    config: Mapped[Optional[dict]] = mapped_column(JSONB)
    metrics: Mapped[Optional[dict]] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(20), default="running")  # running, completed, failed