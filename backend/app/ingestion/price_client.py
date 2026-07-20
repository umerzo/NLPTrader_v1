import logging
from datetime import datetime, timezone
import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

_cache: dict[tuple[str, str], dict] = {}

def get_ohlcv(ticker: str, timeframe: str = "1d", lookback: int = 365) -> pd.DataFrame:
    cache_key = (ticker.upper(), timeframe)
    try:
        yf_ticker = yf.Ticker(ticker)
        df = yf_ticker.history(period=f"{lookback}d", interval=_to_yf_interval(timeframe))
        if df.empty:
            raise ValueError(f"yfinance returned empty DataFrame for {ticker} [{timeframe}]")
        df = df.reset_index()
        ts_col = "Date" if "Date" in df.columns else ("Datetime" if "Datetime" in df.columns else df.columns[0])
        df.rename(columns={ts_col: "timestamp", "Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume"}, inplace=True)
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        result = df[["timestamp", "open", "high", "low", "close", "volume"]].copy()
        _cache[cache_key] = {"data": result, "cached_at": datetime.now(timezone.utc)}
        return result
    except Exception as e:
        logger.warning("yfinance failed for %s [%s]: %s", ticker, timeframe, e)
        cached = _cache.get(cache_key)
        if cached is not None:
            logger.warning("Returning cached data for %s [%s] from %s", ticker, timeframe, cached["cached_at"])
            return cached["data"]
        return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])


def _to_yf_interval(timeframe: str) -> str:
    mapping = {
        "1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m",
        "1h": "60m", "4h": "1h",
        "1d": "1d", "1wk": "1wk", "1mo": "1mo",
    }
    return mapping.get(timeframe, "1d")
