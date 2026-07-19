#!/usr/bin/env python
"""
run_server.py — Start NLPTrader API, ingest missing price timeframes, verify.
Usage:
    python run_server.py [--port 8000]
"""
import sys, os, time, subprocess, urllib.request, json, signal, argparse

BASE = r'C:\Users\umarx\Desktop\NLP_OpenCode\NLPTrader'
os.chdir(BASE)

parser = argparse.ArgumentParser()
parser.add_argument('--port', type=int, default=8000)
args = parser.parse_args()
PORT = args.port

proc = subprocess.Popen(
    [sys.executable, '-m', 'uvicorn', 'backend.app.main:app', '--port', str(PORT), '--log-level', 'warning'],
    cwd=BASE,
    env={**os.environ, 'PYTHONPATH': BASE},
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
)

def server_url(path=''):
    return f'http://localhost:{PORT}{path}'

def test_get(url):
    try:
        r = urllib.request.urlopen(url, timeout=30)
        return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        return {'error': body[:500]}
    except Exception as e:
        return {'error': str(e)[:200]}

def test_post(url, data=b'{}'):
    req = urllib.request.Request(url, method='POST', data=data, headers={'Content-Type': 'application/json'})
    try:
        r = urllib.request.urlopen(req, timeout=60)
        return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return {'error': str(e.code) + ': ' + e.read().decode()[:300]}
    except Exception as e:
        return {'error': str(e)[:200]}

# Wait for startup
print('Starting server...', end=' ', flush=True)
for i in range(30):
    time.sleep(1)
    try:
        r = urllib.request.urlopen(server_url('/docs'), timeout=2)
        if r.status == 200:
            print('OK')
            break
    except Exception:
        continue
else:
    print('FAILED')
    stdout, stderr = proc.communicate(timeout=3)
    print('STDERR:', stderr.decode()[:2000])
    sys.exit(1)

# Verify routes
docs = urllib.request.urlopen(server_url('/openapi.json'), timeout=5).read().decode()
routes_ok = all(r in docs for r in ['/ta/analyze', '/prices/ingest', '/news/analyze-sentiment', '/news/articles', '/signals/active'])
print(f'Routes: {"ALL OK" if routes_ok else "MISSING"}')

# Ingest 15m data
print('Ingesting 15m BTC...', end=' ', flush=True)
r = test_post(server_url('/prices/ingest?ticker=BTC&timeframe=15m'))
print(f'{r.get("bars_inserted", "error")} bars')

# Ingest 4h data
print('Ingesting 4h BTC...', end=' ', flush=True)
r = test_post(server_url('/prices/ingest?ticker=BTC&timeframe=4h'))
print(f'{r.get("bars_inserted", "error")} bars')

# Test TA for all timeframes
print()
for tf in ['15m', '1h', '4h', '1d']:
    r = test_get(server_url(f'/ta/analyze?ticker=BTC&timeframe={tf}'))
    signal = r.get('signal', 'ERROR')
    conf = r.get('confidence', '')
    reason = r.get('reasoning', '')
    print(f'TA {tf:3s}: {signal} {conf}% — {reason[:80] if reason else r}')

print(f'\nTests complete. Shutting down...')
proc.terminate()
try:
    proc.wait(timeout=5)
except subprocess.TimeoutExpired:
    proc.kill()
    proc.wait()
print('Done.')
