from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, Text, DateTime, Integer, SmallInteger, Numeric, Boolean, ForeignKey, UniqueConstraint, Index, PrimaryKeyConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB, BIGINT
from pgvector.sqlalchemy import Vector
from backend.app.db.session import Base


class Ticker(Base):
    __tablename__ = "tickers"

    ticker: Mapped[str] = mapped_column(String(20), primary_key=True)
    display_name: Mapped[Optional[str]] = mapped_column(Text)
    asset_type: Mapped[Optional[str]] = mapped_column(String(20))
    first_added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    last_refreshed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    is_actively_tracked: Mapped[bool] = mapped_column(Boolean, default=True)


class RawArticle(Base):
    __tablename__ = "raw_articles"
    __table_args__ = (
        UniqueConstraint("source", "source_id", name="uq_article_source"),
    )

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    source_id: Mapped[str] = mapped_column(String(200), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    headline: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(Text)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    sentiment: Mapped[Optional[str]] = mapped_column(String(20))
    sentiment_score: Mapped[Optional[float]] = mapped_column(Numeric(5, 4))
    sentiment_scored_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    embedding: Mapped[Optional[list[float]]] = mapped_column(Vector(384))

    ticker_links: Mapped[list["ArticleTicker"]] = relationship(back_populates="article", cascade="all, delete-orphan")


class ArticleTicker(Base):
    __tablename__ = "article_tickers"
    __table_args__ = (
        PrimaryKeyConstraint("article_id", "ticker"),
    )

    article_id: Mapped[int] = mapped_column(BIGINT, ForeignKey("raw_articles.id"), primary_key=True)
    ticker: Mapped[str] = mapped_column(String(20), ForeignKey("tickers.ticker"), primary_key=True)
    event_type: Mapped[Optional[str]] = mapped_column(String(30))
    relevance: Mapped[Optional[float]] = mapped_column(Numeric(5, 4))

    article: Mapped["RawArticle"] = relationship(back_populates="ticker_links")
    ticker_rel: Mapped["Ticker"] = relationship()


class PriceOHLCV(Base):
    __tablename__ = "price_ohlcv"
    __table_args__ = (
        PrimaryKeyConstraint("ticker", "timeframe", "ts"),
    )

    ticker: Mapped[str] = mapped_column(String(20), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(10), nullable=False)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    open: Mapped[float] = mapped_column(Numeric(18, 8), nullable=False)
    high: Mapped[float] = mapped_column(Numeric(18, 8), nullable=False)
    low: Mapped[float] = mapped_column(Numeric(18, 8), nullable=False)
    close: Mapped[float] = mapped_column(Numeric(18, 8), nullable=False)
    volume: Mapped[Optional[float]] = mapped_column(Numeric(24, 8))


class Signal(Base):
    __tablename__ = "signals"
    __table_args__ = (
        Index("ix_signals_ticker_gen", "ticker", "generated_at"),
        Index("ix_signals_active", "ticker", "status"),
    )

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(20), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active")
    signal: Mapped[str] = mapped_column(String(10), nullable=False)
    confidence: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    regime: Mapped[Optional[str]] = mapped_column(String(20))
    entry_price: Mapped[Optional[float]] = mapped_column(Numeric(18, 8))
    stop_loss: Mapped[Optional[float]] = mapped_column(Numeric(18, 8))
    take_profit_1: Mapped[Optional[float]] = mapped_column(Numeric(18, 8))
    take_profit_2: Mapped[Optional[float]] = mapped_column(Numeric(18, 8))
    take_profit_3: Mapped[Optional[float]] = mapped_column(Numeric(18, 8))

    ta_subsignal: Mapped[Optional[dict]] = mapped_column(JSONB)
    sentiment_subsignal: Mapped[Optional[dict]] = mapped_column(JSONB)
    fundamental_subsignal: Mapped[Optional[dict]] = mapped_column(JSONB)

    combiner_reasoning: Mapped[Optional[str]] = mapped_column(Text)

    llm_explanation: Mapped[Optional[str]] = mapped_column(Text)
    llm_model_used: Mapped[Optional[str]] = mapped_column(String(50))
    model_version: Mapped[str] = mapped_column(String(50), default="v1")

    outcome: Mapped[Optional["Outcome"]] = relationship(back_populates="signal", uselist=False)


class Outcome(Base):
    __tablename__ = "outcomes"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    signal_id: Mapped[int] = mapped_column(BIGINT, ForeignKey("signals.id"), nullable=False)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    outcome: Mapped[str] = mapped_column(String(20), nullable=False)
    exit_price: Mapped[Optional[float]] = mapped_column(Numeric(18, 8))
    exit_reason: Mapped[Optional[str]] = mapped_column(String(20))
    return_pct: Mapped[Optional[float]] = mapped_column(Numeric(10, 4))

    signal: Mapped["Signal"] = relationship(back_populates="outcome")


