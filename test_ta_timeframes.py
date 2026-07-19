"""
test_ta_timeframes.py — Tests the TA & prices endpoints using FastAPI TestClient.
Run: $env:PYTHONPATH="..."; python test_ta_timeframes.py
"""
import sys, os, json
sys.path.insert(0, r'C:\Users\umarx\Desktop\NLP_OpenCode\NLPTrader')

from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)

# 1. Ingest 15m data
print('Ingesting 15m BTC...', end=' ', flush=True)
r = client.post('/prices/ingest?ticker=BTC&timeframe=15m')
data = r.json()
print(f'{data.get("bars_inserted", data)} bars' if r.status_code < 400 else f'Error {r.status_code}: {data}')

# 2. Ingest 4h data (aggregated from 1h)
print('Ingesting 4h BTC...', end=' ', flush=True)
r = client.post('/prices/ingest?ticker=BTC&timeframe=4h')
data = r.json()
print(f'{data.get("bars_inserted", data)} bars' if r.status_code < 400 else f'Error {r.status_code}: {data}')

# 3. Test TA for all timeframes
print()
for tf in ['15m', '1h', '4h', '1d']:
    r = client.get(f'/ta/analyze?ticker=BTC&timeframe={tf}')
    if r.status_code < 400:
        d = r.json()
        print(f'TA {tf:3s}: {d["signal"]} ({d["confidence"]}%) — {d["reasoning"][:80]}')
    else:
        print(f'TA {tf:3s}: Error {r.status_code} — {r.json()}')

print('\nDone.')
