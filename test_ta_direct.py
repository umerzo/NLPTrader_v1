"""
test_ta_direct.py — Directly test TA functions to find the error.
"""
import sys, os, asyncio
sys.path.insert(0, r'C:\Users\umarx\Desktop\NLP_OpenCode\NLPTrader')

import numpy as np
from backend.app.db.session import async_session_maker
from backend.app.db.repositories import PriceRepository
from backend.app.db.models import PriceOHLCV
from backend.app.signals.ta_engine import generate_ta_signal, support_resistance, fibonacci_levels, calculate_trade_setup

async def test_ta(ticker='BTC', timeframe='1h'):
    print(f'\n=== Testing TA for {ticker} {timeframe} ===')
    async with async_session_maker() as session:
        repo = PriceRepository(session)
        bars = await repo.get_latest(ticker, timeframe, limit=200)
        print(f'Got {len(bars)} bars')

        if len(bars) < 30:
            print(f'Insufficient data: {len(bars)} bars')
            # Check distinct timeframes
            try:
                available = await repo.get_distinct_timeframes(ticker)
                print(f'Available: {available}')
            except AttributeError as e:
                print(f'get_distinct_timeframes not available: {e}')
            return

        opens = np.array([float(b.open) for b in reversed(bars)], dtype=np.float64)
        highs = np.array([float(b.high) for b in reversed(bars)], dtype=np.float64)
        lows = np.array([float(b.low) for b in reversed(bars)], dtype=np.float64)
        closes = np.array([float(b.close) for b in reversed(bars)], dtype=np.float64)
        volumes = np.array([float(b.volume) for b in reversed(bars)], dtype=np.float64)

        print(f'Arrays created: opens={len(opens)}, highs={len(highs)}, lows={len(lows)}, closes={len(closes)}, volumes={len(volumes)}')

        try:
            ta = generate_ta_signal(opens, highs, lows, closes, volumes)
            print(f'TA signal: {ta.signal} ({ta.confidence}%)')
            print(f'Reasoning: {ta.reasoning[:80]}')

            support, resistance = support_resistance(highs, lows, 30)
            print(f'Support: {support[:3]}, Resistance: {resistance[:3]}')

            fib_levels, fib_high, fib_low = fibonacci_levels(highs, lows, 90)
            print(f'Fib levels: {len(fib_levels)}')

            trade_setup = calculate_trade_setup(float(closes[-1]), support, resistance, ta.indicators.get('rsi_14'))
            print(f'Trade setup: {trade_setup}')

        except Exception as e:
            import traceback
            print(f'TA error: {e}')
            traceback.print_exc()

        print('OK!')

asyncio.run(test_ta('BTC', '15m'))
asyncio.run(test_ta('BTC', '1h'))
asyncio.run(test_ta('BTC', '4h'))
asyncio.run(test_ta('BTC', '1d'))
