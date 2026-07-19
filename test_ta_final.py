"""
test_ta_verify.py — Simple verification that 15m and 4h TA work.
Starts a server subprocess, ingests, and tests.
"""
import sys, os, subprocess, time, urllib.request, json, signal

BASE = r'C:\Users\umarx\Desktop\NLP_OpenCode\NLPTrader'
os.chdir(BASE)

proc = subprocess.Popen(
    [sys.executable, '-m', 'uvicorn', 'backend.app.main:app', '--port', '8005', '--log-level', 'warning'],
    cwd=BASE,
    env={**os.environ, 'PYTHONPATH': BASE},
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
)

def base(url=''):
    return f'http://localhost:8005{url}'

for i in range(20):
    time.sleep(1)
    try:
        r = urllib.request.urlopen(base('/docs'), timeout=2)
        if r.status == 200: break
    except: continue
else:
    print('Server failed'); proc.terminate(); sys.exit(1)

print('Server started.')

def test_get(path):
    try:
        r = urllib.request.urlopen(base(path), timeout=120)
        return r.json()
    except urllib.error.HTTPError as e:
        return {'_error': str(e.code), '_body': e.read().decode()[:300]}
    except Exception as e:
        return {'_error': str(e)[:200]}

def test_post(path):
    req = urllib.request.Request(base(path), method='POST', data=b'{}', headers={'Content-Type': 'application/json'})
    try:
        r = urllib.request.urlopen(req, timeout=300)
        return r.json()
    except urllib.error.HTTPError as e:
        return {'_error': str(e.code), '_body': e.read().decode()[:300]}
    except Exception as e:
        return {'_error': str(e)[:200]}

# Ingest 15m
print('Ingesting 15m...', end=' ', flush=True)
result = test_post('/prices/ingest?ticker=BTC&timeframe=15m')
print(result.get('bars_inserted', result))

# Ingest 4h
print('Ingesting 4h...', end=' ', flush=True)
result = test_post('/prices/ingest?ticker=BTC&timeframe=4h')
print(result.get('bars_inserted', result))

# Test TA
print()
for tf in ['15m', '1h', '4h', '1d']:
    result = test_get(f'/ta/analyze?ticker=BTC&timeframe={tf}')
    sig = result.get('signal', 'ERROR')
    conf = result.get('confidence', '')
    reason = result.get('reasoning', '')[:80]
    print(f'TA {tf:3s}: {sig} {conf}% — {reason}')

proc.terminate()
proc.wait()
print('\nDone.')
