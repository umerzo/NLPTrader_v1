#!/usr/bin/env python
"""
run_all.py — Full pipeline runner for NLPTrader.

Usage:
    python scripts/run_all.py                  # Run everything
    python scripts/run_all.py --skip-ingestion  # Skip news ingestion, just generate signals
    python scripts/run_all.py --tickers BTC,ETH # Specific tickers only

Pipeline:
    1. Price ingestion from yfinance
    2. News ingestion from Finnhub/RSS
    3. Sentiment scoring (FinBERT)
    4. RAG ingestion (ChromaDB)
    5. Signal generation (TA + Sentiment + Fundamental → Combined)
"""
import asyncio
import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def main():
    parser = argparse.ArgumentParser(description="NLPTrader full pipeline runner")
    parser.add_argument("--skip-ingestion", action="store_true", help="Skip news ingestion")
    parser.add_argument("--tickers", default=None, help="Comma-separated tickers (default: all)")
    args = parser.parse_args()

    from backend.app.db.session import async_session_maker
    from backend.app.signals.generator import SignalGenerator
    from backend.app.core.config import get_settings

    settings = get_settings()
    tickers = [t.strip().upper() for t in args.tickers.split(",")] if args.tickers else settings.TICKERS

    print("=" * 50)
    print("  NLPTrader — Full Pipeline Run")
    print("=" * 50)
    print(f"  Ticketers: {', '.join(tickers)}")
    print(f"  Ingestion: {'SKIPPED' if args.skip_ingestion else 'ENABLED'}")
    print("=" * 50)

    async with async_session_maker() as session:
        # Step 1: Ingestion (unless skipped)
        if not args.skip_ingestion:
            print("\n[1/2] Running news ingestion pipeline...")
            from backend.app.ingestion.pipeline import IngestionPipeline
            pipeline = IngestionPipeline(session)
            stats = await pipeline.run(tickers)
            print(f"  Fetched: {stats['fetched']} | New: {stats['new']} | Scored: {stats['scored']} | RAG: {stats['rag_ingested']}")
            if stats['errors']:
                print(f"  Errors: {len(stats['errors'])}")
        else:
            print("\n[1/2] Ingestion skipped.")

        # Step 2: Signal generation
        print("\n[2/2] Generating signals...")
        generator = SignalGenerator(session)
        for ticker in tickers:
            signal = await generator.generate_for_ticker(ticker)
            if signal:
                print(f"  ✓ {ticker}: {signal.combined_signal.upper()} ({signal.combined_confidence}%)")
            else:
                print(f"  ✗ {ticker}: Insufficient data")

        await session.commit()

    print("\n" + "=" * 50)
    print("  Pipeline complete!")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
