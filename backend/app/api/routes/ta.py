"""
ta.py — FastAPI route for on-demand Technical Analysis.
Auto-fetches missing price data from yfinance when needed.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
import numpy as np

from backend.app.db.session import get_db
from backend.app.db.repositories import PriceRepository
from backend.app.db.models import PriceOHLCV
from backend.app.signals.ta_engine import (
    generate_ta_signal, support_resistance, fibonacci_levels,
    calculate_trade_setup, TASignal,
)

router = APIRouter(prefix="/api/ta", tags=["technical-analysis"])

SUPPORTED_TIMEFRAMES = ["15m", "1h", "4h", "1d"]

TICKER_ALIASES = {"XAU": "XAUUSD", "GOLD": "XAUUSD"}
YF_TICKER_MAP = {"BTC": "BTC-USD", "ETH": "ETH-USD", "XAUUSD": "GC=F"}
YF_TIMEFRAMES = {"15m": ("15m", "60d"), "1h": ("1h", "1mo"), "4h": ("1h", "2mo"), "1d": ("1d", "6mo")}

from datetime import datetime, timezone


async def _auto_fetch_bars(ticker: str, timeframe: str, repo: PriceRepository) -> list:
    """Fetch price data from yfinance, store it, return bars."""
    import yfinance as yf

    yf_ticker = YF_TICKER_MAP.get(ticker, ticker)
    tf_info = YF_TIMEFRAMES.get(timeframe)
    if not tf_info:
        return []

    interval, period = tf_info
    data = yf.download(tickers=yf_ticker, period=period, interval=interval, progress=False, auto_adjust=True)
    if data.empty:
        return []

    # Flatten multi-level columns (yfinance 1.x returns tuples)
    if isinstance(data.columns[0], tuple):
        data.columns = data.columns.get_level_values(0)

    bars = []
    for idx, row in data.iterrows():
        ts = idx.to_pydatetime()
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        bars.append({
            "ts": ts,
            "open": float(row["Open"]),
            "high": float(row["High"]),
            "low": float(row["Low"]),
            "close": float(row["Close"]),
            "volume": int(row["Volume"]),
        })

    if bars:
        await repo.upsert_bars(ticker, timeframe, bars)

    return bars


@router.get("/{ticker}")
async def analyze_technical(
    ticker: str,
    timeframe: str = Query("1h", description="Price timeframe"),
    session: AsyncSession = Depends(get_db),
):
    ticker = ticker.upper()
    ticker = TICKER_ALIASES.get(ticker, ticker)
    if timeframe not in SUPPORTED_TIMEFRAMES:
        raise HTTPException(400, f"Unsupported timeframe: {timeframe}")

    repo = PriceRepository(session)
    bars_orm = await repo.get_latest(ticker, timeframe, limit=200)
    bars = [{
        "ts": b.ts,
        "open": float(b.open), "high": float(b.high),
        "low": float(b.low), "close": float(b.close),
        "volume": float(b.volume),
    } for b in bars_orm]

    # Auto-fetch from yfinance if not enough bars
    if len(bars) < 30:
        raw_bars = await _auto_fetch_bars(ticker, timeframe, repo)
        if raw_bars:
            # Store into DB and re-read (so 4h gets aggregated properly)
            await session.commit()
            bars_orm = await repo.get_latest(ticker, timeframe, limit=200)
            bars = [{
                "ts": b.ts,
                "open": float(b.open), "high": float(b.high),
                "low": float(b.low), "close": float(b.close),
                "volume": float(b.volume),
            } for b in bars_orm]

    # Auto-aggregate 4h from 1h if still not enough
    if len(bars) < 30 and timeframe == "4h":
        one_hour_orm = await repo.get_latest(ticker, "1h", limit=200)
        if len(one_hour_orm) >= 30:
            from collections import OrderedDict
            buckets = OrderedDict()
            for b in reversed(one_hour_orm):
                ts = b.timestamp
                bucket_hour = (ts.hour // 4) * 4
                bucket_ts = ts.replace(hour=bucket_hour, minute=0, second=0, microsecond=0)
                if bucket_ts not in buckets:
                    buckets[bucket_ts] = {
                        "open": float(b.open), "high": float(b.high),
                        "low": float(b.low), "close": float(b.close),
                        "volume": float(b.volume),
                    }
                else:
                    bk = buckets[bucket_ts]
                    bk["high"] = max(bk["high"], float(b.high))
                    bk["low"] = min(bk["low"], float(b.low))
                    bk["close"] = float(b.close)
                    bk["volume"] += float(b.volume)
            bars = []
            for ts, bk in buckets.items():
                bars.append({
                    "ts": ts, "open": bk["open"], "high": bk["high"],
                    "low": bk["low"], "close": bk["close"], "volume": bk["volume"],
                })
            bars = bars[-200:]

    if len(bars) < 30:
        available = await repo.get_distinct_timeframes(ticker)
        raise HTTPException(404,
            f"Insufficient price data for {ticker} ({timeframe}). "
            f"yfinance also returned no data. Available timeframes: {available}."
        )

    reversed_bars = list(reversed(bars))
    opens = np.array([b["open"] for b in reversed_bars], dtype=np.float64)
    highs = np.array([b["high"] for b in reversed_bars], dtype=np.float64)
    lows = np.array([b["low"] for b in reversed_bars], dtype=np.float64)
    closes = np.array([b["close"] for b in reversed_bars], dtype=np.float64)
    volumes = np.array([b["volume"] for b in reversed_bars], dtype=np.float64)
    current_price = float(closes[-1])

    timestamps = [b["ts"].isoformat() if hasattr(b["ts"], 'isoformat') else str(b["ts"]) for b in reversed_bars]

    ta: TASignal = generate_ta_signal(opens, highs, lows, closes, volumes)

    support, resistance = support_resistance(highs, lows, 30)
    fib_levels, fib_high, fib_low = fibonacci_levels(highs, lows, 90)
    trade_setup = calculate_trade_setup(ta.signal, current_price, support, resistance, ta.indicators.get('rsi_14'))

    narrative_prompt = (
        f"Act as a Professional daytrader and analyze {ticker} on the {timeframe} timeframe. "
        f"Current price: ${current_price:.2f}. "
        f"Signal: {ta.signal.upper()} with {ta.confidence}% confidence. "
        f"Reasoning: {ta.reasoning}. "
        f"Technical Indicators: RSI(14)={ta.indicators.get('rsi_14', 'N/A')}, "
        f"MACD={ta.indicators.get('macd', ('N/A',))[0]}, "
        f"SMA20={ta.indicators.get('sma_20', 'N/A')}, SMA50={ta.indicators.get('sma_50', 'N/A')}. "
        f"Bollinger Bands: Upper={ta.indicators.get('bb_upper', 'N/A')}, Lower={ta.indicators.get('bb_lower', 'N/A')}. "
        f"Support levels: {[round(s, 2) for s in support[:3]]}. "
        f"Resistance levels: {[round(r, 2) for r in resistance[:3]]}. "
        f"Market regime: {ta.regime} (multiplier: {ta.regime_multiplier})."
    )

    return {
        "ticker": ticker,
        "timeframe": timeframe,
        "current_price": current_price,
        "signal": ta.signal,
        "confidence": ta.confidence,
        "reasoning": ta.reasoning,
        "regime": ta.regime,
        "regime_multiplier": ta.regime_multiplier,
        "indicators": {
            "rsi_14": ta.indicators.get("rsi_14"),
            "rsi_7": ta.indicators.get("rsi_7"),
            "macd": ta.indicators.get("macd", (None, None, None))[0],
            "macd_signal": ta.indicators.get("macd", (None, None, None))[1],
            "macd_histogram": ta.indicators.get("macd", (None, None, None))[2],
            "sma_20": ta.indicators.get("sma_20"),
            "sma_50": ta.indicators.get("sma_50"),
            "ema_12": ta.indicators.get("ema_12"),
            "ema_26": ta.indicators.get("ema_26"),
            "bb_upper": ta.indicators.get("bb_upper"),
            "bb_middle": ta.indicators.get("bb_middle", ta.indicators.get("sma_20")),
            "bb_lower": ta.indicators.get("bb_lower"),
            "atr_14": ta.indicators.get("atr_14"),
            "volume_sma_20": ta.indicators.get("volume_sma_20"),
            "current_volume": ta.indicators.get("current_volume"),
        },
        "support_levels": [round(s, 2) for s in support[:5]],
        "resistance_levels": [round(r, 2) for r in resistance[:5]],
        "fibonacci": {
            "levels": [round(l, 2) for l in fib_levels],
            "swing_high": round(fib_high, 2),
            "swing_low": round(fib_low, 2),
        },
        "trade_setup": trade_setup,
        "levels": {
            "entry": ta.levels.get("entry"),
            "sl": ta.levels.get("sl"),
            "tp1": ta.levels.get("tp1"),
            "tp2": ta.levels.get("tp2"),
            "tp3": ta.levels.get("tp3"),
        },
        "price_data": [
            {
                "time": t,
                "open": float(o),
                "high": float(h),
                "low": float(l),
                "close": float(c),
                "volume": float(v),
            }
            for t, o, h, l, c, v in zip(
                timestamps, opens, highs, lows, closes, volumes
            )
        ],
        "narrative_context": narrative_prompt,
    }
