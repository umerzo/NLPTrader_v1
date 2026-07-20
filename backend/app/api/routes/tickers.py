from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import yfinance as yf
from datetime import datetime, timezone

from backend.app.db.session import get_db
from backend.app.db.models import Ticker
from backend.app.db.repositories import TickerRepository

router = APIRouter(prefix="/api/tickers", tags=["tickers"])


@router.get("/search")
async def search_ticker(
    q: str = Query(..., min_length=1, max_length=20, description="Ticker symbol to search"),
):
    """Search/validate a ticker via yfinance, return basic info."""
    q = q.upper().strip()
    try:
        yf_ticker = yf.Ticker(q)
        info = yf_ticker.info or {}
        if not info.get("symbol") and not info.get("shortName"):
            return {
                "found": False,
                "query": q,
                "message": f"No data for '{q}' on yfinance",
            }
    except Exception as e:
        raise HTTPException(502, f"yfinance error: {e}")

    return {
        "found": True,
        "ticker": info.get("symbol", q),
        "name": info.get("shortName") or info.get("longName"),
        "exchange": info.get("exchange"),
        "sector": info.get("sector"),
        "industry": info.get("industry"),
        "asset_type": info.get("quoteType"),
        "current_price": info.get("regularMarketPrice") or info.get("previousClose"),
        "currency": info.get("currency"),
    }


@router.post("/{ticker}/track")
async def track_ticker(
    ticker: str,
    session: AsyncSession = Depends(get_db),
):
    """Add ticker to tracked list; triggers on-demand ingestion if new or stale."""
    ticker = ticker.upper().strip()
    repo = TickerRepository(session)

    existing = await repo.get(ticker)
    now = datetime.now(timezone.utc)
    triggered_ingestion = False

    if existing:
        if existing.last_refreshed_at and (now - existing.last_refreshed_at).total_seconds() < 3600:
            return {"status": "ok", "ticker": ticker, "action": "already_tracked"}
        existing.last_refreshed_at = now
    else:
        new_ticker = Ticker(ticker=ticker, first_added_at=now, last_refreshed_at=now)
        session.add(new_ticker)
        triggered_ingestion = True

    await session.commit()

    if triggered_ingestion:
        from backend.app.ingestion.pipeline import IngestionPipeline
        pipeline = IngestionPipeline(session)
        ingest_stats = await pipeline.run_single_ticker(ticker)

        from backend.app.signals.generator import SignalGenerator
        generator = SignalGenerator(session)
        signal = await generator.generate_for_ticker(ticker)
        await session.commit()

        return {
            "status": "ok",
            "ticker": ticker,
            "action": "new_ticker",
            "ingestion": ingest_stats,
            "signal_generated": signal is not None,
        }

    return {
        "status": "ok",
        "ticker": ticker,
        "action": "refreshed",
    }
