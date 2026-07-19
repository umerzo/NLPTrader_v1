#!/usr/bin/env python
"""
run_ingestion.py — Run news ingestion pipeline.
Usage: python scripts/run_ingestion.py [--tickers BTC,ETH] [--hours 24]
"""
import asyncio
import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.app.db.session import async_session_maker
from backend.app.ingestion.pipeline import IngestionPipeline


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tickers", default="BTC,ETH,XAUUSD,NVDA")
    parser.add_argument("--hours", type=int, default=24)
    args = parser.parse_args()

    tickers = [t.strip().upper() for t in args.tickers.split(",")]

    async with async_session_maker() as session:
        pipeline = IngestionPipeline(session)
        stats = await pipeline.run(tickers, args.hours)

    print(f"\n{'='*40}")
    print(f"INGESTION COMPLETE")
    print(f"{'='*40}")
    print(f"Fetched:      {stats['fetched']}")
    print(f"New articles: {stats['new']}")
    print(f"Scored:       {stats['scored']}")
    print(f"RAG ingested: {stats['rag_ingested']}")
    if stats['errors']:
        print(f"Errors:       {len(stats['errors'])}")
        for e in stats['errors']:
            print(f"  - {e}")


if __name__ == "__main__":
    asyncio.run(main())