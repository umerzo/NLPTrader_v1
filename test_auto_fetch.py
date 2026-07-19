"""
test_auto_fetch.py — Tests TA with auto-fetch (no manual ingestion needed).
"""
import sys, os, asyncio
sys.path.insert(0, r'C:\Users\umarx\Desktop\NLP_OpenCode\NLPTrader')

import numpy as np
from backend.app.db.session import async_session_maker
from backend.app.db.repositories import PriceRepository

async def check_state(ticker='BTC', timeframe='15m'):
    async with async_session_maker() as session:
        repo = PriceRepository(session)
        bars = await repo.get_latest(ticker, timeframe, limit=5)
        print(f'{timeframe}: {len(bars)} bars in DB')
        return len(bars) >= 30

async def main():
    # Check initial state
    print('=== Before auto-fetch ===')
    for tf in ['15m', '4h', '1h', '1d']:
        await check_state('BTC', tf)

    # Now simulate what the TA endpoint does: auto-fetch if missing
    print('\n=== Auto-fetching missing timeframes ===')
    from backend.app.api.routes.ta import _auto_fetch_bars
    async with async_session_maker() as session:
        repo = PriceRepository(session)
        for tf in ['15m', '4h']:
            bars = await repo.get_latest('BTC', tf, limit=5)
            if len(bars) < 5:
                raw = await _auto_fetch_bars('BTC', tf, repo)
                if raw:
                    print(f'{tf}: auto-fetched {len(raw)} bars')
                    await session.commit()
                else:
                    print(f'{tf}: yfinance returned empty')

    # Check state after
    print('\n=== After auto-fetch ===')
    async with async_session_maker() as session:
        repo = PriceRepository(session)
        for tf in ['15m', '4h', '1h', '1d']:
            bars = await repo.get_latest('BTC', tf, limit=5)
            print(f'{tf}: {len(bars)} bars in DB')

    # Test TA
    print('\n=== Testing TA endpoint ===')
    from backend.app.signals.ta_engine import generate_ta_signal
    async with async_session_maker() as session:
        repo = PriceRepository(session)
        for tf in ['15m', '1h', '4h', '1d']:
            bars_orm = await repo.get_latest('BTC', tf, limit=200)
            bars = [{
                "open": float(b.open), "high": float(b.high),
                "low": float(b.low), "close": float(b.close),
                "volume": float(b.volume),
            } for b in bars_orm]
            if len(bars) >= 30:
                opens = np.array([b["open"] for b in reversed(bars)], dtype=np.float64)
                highs = np.array([b["high"] for b in reversed(bars)], dtype=np.float64)
                lows = np.array([b["low"] for b in reversed(bars)], dtype=np.float64)
                closes = np.array([b["close"] for b in reversed(bars)], dtype=np.float64)
                volumes = np.array([b["volume"] for b in reversed(bars)], dtype=np.float64)
                ta = generate_ta_signal(opens, highs, lows, closes, volumes)
                print(f'TA {tf:3s}: {ta.signal} ({ta.confidence}%) — {ta.reasoning[:60]}')
            else:
                print(f'TA {tf:3s}: {len(bars)} bars (need 30)')

asyncio.run(main())
