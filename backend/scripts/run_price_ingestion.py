#!/usr/bin/env python
"""
run_price_ingestion.py — Fetch OHLCV data from yfinance.
Usage: python scripts/run_price_ingestion.py [--tickers BTC,ETH] [--days 30]
"""
import asyncio
import argparse
import sys
import os
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.app.db.session import async_session_maker
from backend.app.db.repositories import PriceRepository


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tickers", default="BTC,ETH,XAUUSD,NVDA")
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--timeframe", default="1d", choices=["1d"])
    args = parser.parse_args()

    tickers = [t.strip().upper() for t in args.tickers.split(",")]
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=args.days)

    async with async_session_maker() as session:
        repo = PriceRepository(session)
        
        for ticker in tickers:
            print(f"Fetching {ticker} ({args.timeframe}) for last {args.days} days...")
            try:
                # Map ticker to yfinance symbol
                yf_symbol = ticker
                if ticker == "BTC":
                    yf_symbol = "BTC-USD"
                elif ticker == "ETH":
                    yf_symbol = "ETH-USD"
                elif ticker == "XAUUSD":
                    yf_symbol = "GC=F"  # Gold futures
                
                def _fetch():
                    import yfinance as yf
                    return yf.download(yf_symbol, start=start, end=end, interval=args.timeframe, progress=False, auto_adjust=True)
                
                df = await asyncio.to_thread(_fetch)
                
                if df.empty:
                    print(f"  No data for {ticker} (symbol: {yf_symbol})")
                    continue
                
                bars = []
                for ts, row in df.iterrows():
                    bars.append({
                        "timestamp": ts.to_pydatetime().replace(tzinfo=timezone.utc),
                        "open": float(row["Open"]),
                        "high": float(row["High"]),
                        "low": float(row["Low"]),
                        "close": float(row["Close"]),
                        "volume": float(row["Volume"]),
                    })
                
                count = await repo.upsert_bars(ticker, args.timeframe, bars)
                await session.commit()
                print(f"  Inserted {count} bars for {ticker}")
                
            except Exception as e:
                print(f"  Error for {ticker}: {e}")
                await session.rollback()

    print("\nPrice ingestion complete!")


if __name__ == "__main__":
    asyncio.run(main())