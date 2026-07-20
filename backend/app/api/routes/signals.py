from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func
from datetime import datetime, timezone

from backend.app.db.session import get_db
from backend.app.db.models import Signal, Outcome
from backend.app.db.repositories import SignalRepository
from backend.app.signals.generator import SignalGenerator
from backend.app.ingestion.pipeline import IngestionPipeline


router = APIRouter(prefix="/api/signals", tags=["signals"])


@router.get("/active")
async def get_active_signals(
    ticker: Optional[str] = None,
    session: AsyncSession = Depends(get_db),
):
    """Current active signals across tracked tickers."""
    repo = SignalRepository(session)
    signals = await repo.get_active(ticker.upper() if ticker else None)
    return [
        {
            "id": s.id,
            "ticker": s.ticker,
            "signal": s.signal,
            "confidence": s.confidence,
            "reasoning": s.combiner_reasoning,
            "entry": s.entry_price,
            "sl": s.stop_loss,
            "tp1": s.take_profit_1,
            "tp2": s.take_profit_2,
            "tp3": s.take_profit_3,
            "regime": s.regime,
            "model_version": s.model_version,
            "generated_at": s.generated_at.isoformat(),
            "expires_at": s.expires_at.isoformat() if s.expires_at else None,
            "sub_signals": {
                "ta": {"signal": (s.ta_subsignal or {}).get("signal"), "confidence": (s.ta_subsignal or {}).get("confidence"), "details": s.ta_subsignal},
                "sentiment": {"signal": (s.sentiment_subsignal or {}).get("signal"), "confidence": (s.sentiment_subsignal or {}).get("confidence"), "details": s.sentiment_subsignal},
                "fundamental": {"signal": (s.fundamental_subsignal or {}).get("signal"), "confidence": (s.fundamental_subsignal or {}).get("confidence"), "details": s.fundamental_subsignal},
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
    """Paginated, filterable by ticker/date/outcome."""
    count_stmt = select(func.count(Signal.id))
    if ticker:
        count_stmt = count_stmt.where(Signal.ticker == ticker.upper())
    total = (await session.execute(count_stmt)).scalar() or 0

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
            "signal": s.signal,
            "confidence": s.confidence,
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
                "return_pct": float(o.return_pct) if o.return_pct else None,
                "exit_price": float(o.exit_price) if o.exit_price else None,
                "exit_reason": o.exit_reason,
                "evaluated_at": o.evaluated_at.isoformat(),
            } if o else None,
        }
        for s, o in rows
    ], "total": total}


@router.post("/refresh")
async def refresh_all(
    session: AsyncSession = Depends(get_db),
):
    """Manual/admin trigger: full pipeline refresh for all tracked tickers.

    Pipeline: news ingestion → price ingestion → signal generation.
    """
    import logging, pandas as pd
    from backend.app.core.config import get_settings
    from backend.app.db.repositories import TickerRepository, PriceRepository

    logger = logging.getLogger(__name__)
    settings = get_settings()

    # 1. News ingestion
    pipeline = IngestionPipeline(session)
    ingest_stats = await pipeline.run()

    # Ensure all configured tickers exist in the DB
    from backend.app.db.models import Ticker as TickerModel
    ticker_repo = TickerRepository(session)
    tracked = await ticker_repo.get_all_tracked()
    tracked_set = {t.ticker for t in tracked}
    tracked_tickers = list(settings.TICKERS)
    for t in settings.TICKERS:
        if t not in tracked_set:
            session.add(TickerModel(ticker=t, is_actively_tracked=True))
    if tracked_set != set(settings.TICKERS):
        await session.commit()

    print(f"[refresh_all] tracked_tickers={tracked_tickers}", flush=True)

    # 2. Price ingestion for each tracked ticker
    import yfinance as yf
    price_repo = PriceRepository(session)
    price_stats = {}
    yf_to_symbol = {"BTC": "BTC-USD", "ETH": "ETH-USD", "XAUUSD": "GC=F"}

    for ticker in tracked_tickers:
        try:
            yf_symbol = yf_to_symbol.get(ticker, ticker)
            yf_ticker = yf.Ticker(yf_symbol)
            df = yf_ticker.history(period="6mo", interval="1d")
            if df.empty:
                logger.warning("yfinance returned empty DataFrame for %s (symbol=%s)", ticker, yf_symbol)
                price_stats[ticker] = "no data"
                continue
            df = df.reset_index()
            ts_col = "Date" if "Date" in df.columns else ("Datetime" if "Datetime" in df.columns else df.columns[0])
            bars = [
                {"ts": pd.Timestamp(row[ts_col]).to_pydatetime(),
                 "open": float(row["Open"]), "high": float(row["High"]),
                 "low": float(row["Low"]), "close": float(row["Close"]),
                 "volume": float(row["Volume"]) if "Volume" in row else 0}
                for _, row in df.iterrows()
            ]
            inserted = await price_repo.upsert_bars(ticker, "1d", bars)
            price_stats[ticker] = f"{inserted} bars"
            logger.info("Ingested %d price bars for %s (1d)", inserted, ticker)
        except Exception as e:
            logger.error("Price ingestion failed for %s: %s", ticker, e)
            price_stats[ticker] = f"error: {e}"

    await session.commit()

    # 3. Signal generation
    generator = SignalGenerator(session)
    results = []
    for ticker in tracked_tickers:
        signal = await generator.generate_for_ticker(ticker)
        if signal:
            results.append(ticker)

    await session.commit()

    return {
        "status": "ok",
        "ingestion": ingest_stats,
        "price_ingestion": price_stats,
        "signals_generated": results,
        "_debug_tickers": tracked_tickers,
    }


@router.post("/generate/{ticker}")
async def generate_signal(
    ticker: str,
    session: AsyncSession = Depends(get_db),
):
    """Generate a new combined signal for a ticker (one-time trigger, not polling)."""
    ticker = ticker.upper()

    from backend.app.db.models import Ticker
    ticker_exists = await session.get(Ticker, ticker)
    if not ticker_exists:
        raise HTTPException(400, f"Ticker '{ticker}' is not tracked. POST /api/tickers/{ticker}/track first.")

    generator = SignalGenerator(session)
    signal = await generator.generate_for_ticker(ticker)
    if not signal:
        raise HTTPException(404, f"Insufficient data for {ticker}")

    await session.commit()

    ta = signal.ta_subsignal or {}
    sent = signal.sentiment_subsignal or {}
    fund = signal.fundamental_subsignal or {}

    return {
        "id": signal.id,
        "ticker": signal.ticker,
        "signal": signal.signal,
        "confidence": signal.confidence,
        "reasoning": signal.combiner_reasoning,
        "entry": signal.entry_price,
        "stop_loss": signal.stop_loss,
        "tp1": signal.take_profit_1,
        "tp2": signal.take_profit_2,
        "tp3": signal.take_profit_3,
        "regime": signal.regime,
        "model_version": signal.model_version,
        "generated_at": signal.generated_at.isoformat(),
        "expires_at": signal.expires_at.isoformat() if signal.expires_at else None,
        "sub_signals": {
            "ta": {**ta},
            "sentiment": {**sent},
            "fundamental": {**fund},
        },
    }


@router.get("/{signal_id}")
async def get_signal_detail(
    signal_id: int,
    session: AsyncSession = Depends(get_db),
):
    """Full signal detail including sub-signals and explanation."""
    repo = SignalRepository(session)
    signal = await repo.get_by_id(signal_id)
    if not signal:
        raise HTTPException(404, "Signal not found")

    ta = signal.ta_subsignal or {}
    sent = signal.sentiment_subsignal or {}
    fund = signal.fundamental_subsignal or {}

    return {
        "id": signal.id,
        "ticker": signal.ticker,
        "signal": signal.signal,
        "confidence": signal.confidence,
        "combiner_reasoning": signal.combiner_reasoning,
        "entry": signal.entry_price,
        "sl": signal.stop_loss,
        "tp1": signal.take_profit_1,
        "tp2": signal.take_profit_2,
        "tp3": signal.take_profit_3,
        "regime": signal.regime,
        "model_version": signal.model_version,
        "status": signal.status,
        "generated_at": signal.generated_at.isoformat(),
        "expires_at": signal.expires_at.isoformat() if signal.expires_at else None,
        "llm_explanation": signal.llm_explanation,
        "llm_model_used": signal.llm_model_used,
        "sub_signals": {
            "ta": {**ta},
            "sentiment": {**sent},
            "fundamental": {**fund},
        },
        "outcome": {
            "outcome": signal.outcome.outcome,
            "exit_price": float(signal.outcome.exit_price) if signal.outcome and signal.outcome.exit_price else None,
            "exit_reason": signal.outcome.exit_reason if signal.outcome else None,
            "return_pct": float(signal.outcome.return_pct) if signal.outcome and signal.outcome.return_pct else None,
        } if signal.outcome else None,
    }
