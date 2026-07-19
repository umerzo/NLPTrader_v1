"""
signals.py — FastAPI routes for signals.
Thin layer: validation → call generator → return JSON.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func, case
from datetime import datetime, timezone

from backend.app.db.session import get_db
from backend.app.db.models import Signal, Outcome
from backend.app.db.repositories import SignalRepository, OutcomeRepository, ArticleRepository
from backend.app.signals.generator import SignalGenerator
from backend.app.ingestion.pipeline import IngestionPipeline

router = APIRouter(prefix="/signals", tags=["signals"])


@router.post("/refresh")
async def refresh_all(
    session: AsyncSession = Depends(get_db),
):
    """Run full pipeline: ingest news + prices → generate signals for all tickers."""
    from backend.app.core.config import get_settings
    settings = get_settings()

    # 1. Ingest news
    pipeline = IngestionPipeline(session)
    ingest_stats = await pipeline.run()

    # 2. Ingest price data for all timeframes
    from backend.app.db.repositories import PriceRepository
    price_repo = PriceRepository(session)
    price_stats = {}
    for ticker in settings.TICKERS:
        price_stats[ticker] = {}
        for tf in settings.PRICE_TIMEFRAMES:
            bars = await price_repo.get_latest(ticker, tf, limit=5)
            if len(bars) < 5:
                from backend.app.api.routes.ta import _auto_fetch_bars
                raw = await _auto_fetch_bars(ticker, tf, price_repo)
                price_stats[ticker][tf] = len(raw) if raw else 0
            else:
                price_stats[ticker][tf] = f"{len(bars)} (cached)"

    # 3. Generate signals for all tickers
    generator = SignalGenerator(session)
    results = []
    for ticker in settings.TICKERS:
        signal = await generator.generate_for_ticker(ticker)
        if signal:
            results.append(ticker)

    await session.commit()

    return {
        "status": "ok",
        "ingestion": ingest_stats,
        "prices": price_stats,
        "signals_generated": results,
    }


@router.post("/generate/{ticker}")
async def generate_signal(
    ticker: str,
    session: AsyncSession = Depends(get_db),
):
    """Generate a new combined signal for a ticker."""
    ticker = ticker.upper()
    if ticker not in ["BTC", "ETH", "XAUUSD", "NVDA"]:
        raise HTTPException(400, f"Unsupported ticker: {ticker}")

    generator = SignalGenerator(session)
    signal = await generator.generate_for_ticker(ticker)
    if not signal:
        raise HTTPException(404, f"Insufficient data for {ticker}")

    await session.commit()

    return {
        "id": signal.id,
        "ticker": signal.ticker,
        "signal": signal.combined_signal,
        "confidence": signal.combined_confidence,
        "reasoning": signal.combined_reasoning,
        "entry": signal.entry_price,
        "stop_loss": signal.stop_loss,
        "tp1": signal.take_profit_1,
        "tp2": signal.take_profit_2,
        "tp3": signal.take_profit_3,
        "horizon": signal.prediction_horizon,
        "regime": signal.regime,
        "model_version": signal.model_version,
        "generated_at": signal.generated_at.isoformat(),
        "expires_at": signal.expires_at.isoformat() if signal.expires_at else None,
        "sub_signals": {
            "ta": {"signal": signal.ta_signal, "confidence": signal.ta_confidence, "details": signal.ta_details},
            "sentiment": {"signal": signal.sentiment_signal, "confidence": signal.sentiment_confidence, "details": signal.sentiment_details},
            "fundamental": {"signal": signal.fundamental_signal, "confidence": signal.fundamental_confidence, "details": signal.fundamental_details},
        },
    }


@router.get("/active")
async def get_active_signals(
    ticker: Optional[str] = None,
    session: AsyncSession = Depends(get_db),
):
    """Get all active signals, optionally filtered by ticker."""
    repo = SignalRepository(session)
    signals = await repo.get_active(ticker.upper() if ticker else None)
    return [
        {
            "id": s.id,
            "ticker": s.ticker,
            "signal": s.combined_signal,
            "confidence": s.combined_confidence,
            "reasoning": s.combined_reasoning,
            "entry": s.entry_price,
            "sl": s.stop_loss,
            "tp1": s.take_profit_1,
            "tp2": s.take_profit_2,
            "tp3": s.take_profit_3,
            "horizon": s.prediction_horizon,
            "regime": s.regime,
            "model_version": s.model_version,
            "generated_at": s.generated_at.isoformat(),
            "expires_at": s.expires_at.isoformat() if s.expires_at else None,
            "sub_signals": {
                "ta": {"signal": s.ta_signal, "confidence": s.ta_confidence, "details": s.ta_details},
                "sentiment": {"signal": s.sentiment_signal, "confidence": s.sentiment_confidence, "details": s.sentiment_details},
                "fundamental": {"signal": s.fundamental_signal, "confidence": s.fundamental_confidence, "details": s.fundamental_details},
            },
        }
        for s in signals
    ]


@router.get("/history")
async def get_signal_history(
    ticker: Optional[str] = None,
    limit: int = Query(100, le=500),
    offset: int = 0,
    session: AsyncSession = Depends(get_db),
):
    """Paginated signal history with outcomes."""
    # Get total count
    count_stmt = select(func.count(Signal.id))
    if ticker:
        count_stmt = count_stmt.where(Signal.ticker == ticker.upper())
    total = (await session.execute(count_stmt)).scalar() or 0

    # Get paginated rows
    stmt = select(Signal, Outcome).outerjoin(Outcome, Outcome.signal_id == Signal.id)
    if ticker:
        stmt = stmt.where(Signal.ticker == ticker.upper())
    stmt = stmt.order_by(desc(Signal.generated_at)).limit(limit).offset(offset)
    result = await session.execute(stmt)
    rows = result.all()

    return {"items": [
        {
            "id": s.id,
            "ticker": s.ticker,
            "signal": s.combined_signal,
            "confidence": s.combined_confidence,
            "entry": s.entry_price,
            "sl": s.stop_loss,
            "tp1": s.take_profit_1,
            "regime": s.regime,
            "model_version": s.model_version,
            "generated_at": s.generated_at.isoformat(),
            "expires_at": s.expires_at.isoformat() if s.expires_at else None,
            "status": s.status,
            "outcome": {
                "outcome": o.outcome,
                "price_change_pct": float(o.price_change_pct) if o.price_change_pct else None,
                "max_fav": float(o.max_favorable_pct) if o.max_favorable_pct else None,
                "max_adv": float(o.max_adverse_pct) if o.max_adverse_pct else None,
                "hit_sl": o.hit_sl,
                "hit_tp1": o.hit_tp1,
                "checked_at": o.checked_at.isoformat(),
            } if o else None,
        }
        for s, o in rows
    ], "total": total}


@router.get("/stats")
async def get_signal_stats(
    ticker: Optional[str] = None,
    session: AsyncSession = Depends(get_db),
):
    """Accuracy, calibration, P&L summary."""
    repo = OutcomeRepository(session)
    return await repo.get_summary(ticker.upper() if ticker else None)