"""
prices.py — FastAPI route for price data ingestion and management.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone, timedelta
import yfinance as yf

from backend.app.db.session import get_db
from backend.app.db.repositories import PriceRepository

router = APIRouter(prefix="/prices", tags=["prices"])

YF_TICKER_MAP = {
    "BTC": "BTC-USD",
    "ETH": "ETH-USD",
    "XAUUSD": "GC=F",
    "NVDA": "NVDA",
}

YF_TIMEFRAMES = {
    "1m": ("1m", "1d"),
    "5m": ("5m", "5d"),
    "15m": ("15m", "60d"),
    "30m": ("30m", "60d"),
    "1h": ("1h", "1mo"),
    "4h": ("1h", "2mo"),  # aggregated from 1h bars
    "1d": ("1d", "6mo"),
}


@router.post("/ingest")
async def ingest_prices(
    ticker: str = Query(..., description="Ticker symbol"),
    timeframe: str = Query("1h", description="Price timeframe"),
    session: AsyncSession = Depends(get_db),
):
    """Fetch price data from yfinance and store in DB."""
    ticker = ticker.upper()
    yf_ticker = YF_TICKER_MAP.get(ticker)
    if not yf_ticker:
        raise HTTPException(400, f"Unsupported ticker: {ticker}")

    tf_info = YF_TIMEFRAMES.get(timeframe)
    if not tf_info:
        raise HTTPException(400, f"Unsupported timeframe: {timeframe}")

    interval, period = tf_info
    try:
        data = yf.download(tickers=yf_ticker, period=period, interval=interval, progress=False, auto_adjust=True)
    except Exception as e:
        raise HTTPException(502, f"yfinance error: {e}")

    if data.empty:
        raise HTTPException(404, f"No price data for {ticker} ({timeframe})")

    # Flatten multi-level columns (yfinance 1.x returns tuples)
    if isinstance(data.columns[0], tuple):
        data.columns = data.columns.get_level_values(0)

    bars = []
    for idx, row in data.iterrows():
        ts = idx.to_pydatetime()
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        bars.append({
            "timestamp": ts,
            "open": float(row["Open"]),
            "high": float(row["High"]),
            "low": float(row["Low"]),
            "close": float(row["Close"]),
            "volume": int(row["Volume"]),
        })

    repo = PriceRepository(session)
    count = await repo.upsert_bars(ticker, timeframe, bars)
    await session.commit()

    return {
        "ticker": ticker,
        "timeframe": timeframe,
        "bars_inserted": count,
        "total_bars": len(bars),
        "from": bars[0]["timestamp"].isoformat() if bars else None,
        "to": bars[-1]["timestamp"].isoformat() if bars else None,
    }
