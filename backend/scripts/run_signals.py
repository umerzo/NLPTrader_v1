#!/usr/bin/env python
"""
run_signals.py - Generate signals for all tickers.
Usage: python scripts/run_signals.py [--tickers BTC,ETH] [--model v1.0-ensemble]
"""
import asyncio
import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.app.db.session import async_session_maker
from backend.app.signals.generator import SignalGenerator


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tickers", default="BTC,ETH,XAUUSD,NVDA")
    args = parser.parse_args()

    tickers = [t.strip().upper() for t in args.tickers.split(",")]

    async with async_session_maker() as session:
        generator = SignalGenerator(session)
        for ticker in tickers:
            signal = await generator.generate_for_ticker(ticker)
            if signal:
                print(f"[OK] {ticker}: {signal.combined_signal.upper()} ({signal.combined_confidence}%) - {signal.combined_reasoning[:80]}...")
            else:
                print(f"[--] {ticker}: Insufficient data")
        await session.commit()


if __name__ == "__main__":
    asyncio.run(main())