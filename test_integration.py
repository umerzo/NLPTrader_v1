"""
Quick integration test: start server, test endpoints, shutdown.
Run with: $env:PYTHONPATH = "..."; python test_integration.py
"""
import sys, os, time, subprocess, urllib.request, json, signal

BASE = r'C:\Users\umarx\Desktop\NLP_OpenCode\NLPTrader'
os.chdir(BASE)

proc = subprocess.Popen(
    [sys.executable, '-m', 'uvicorn', 'backend.app.main:app', '--port', '8001'],
    cwd=BASE,
    env={**os.environ, 'PYTHONPATH': BASE},
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
)

# Wait for startup
for i in range(30):
    time.sleep(1)
    try:
        r = urllib.request.urlopen('http://localhost:8001/docs', timeout=2)
        if r.status == 200:
            print('Server started.')
            break
    except Exception as e:
        if i == 0:
            print(f'Waiting... ({e})')
        continue
else:
    print('Server failed to start')
    stdout, stderr = proc.communicate(timeout=5)
    print('STDOUT:', stdout.decode()[:1000])
    print('STDERR:', stderr.decode()[:2000])
    proc.terminate()
    sys.exit(1)

def test(url):
    try:
        r = urllib.request.urlopen(url, timeout=30)
        return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return {'ERROR': e.code, 'body': e.read().decode()[:300]}
    except Exception as e:
        return {'ERROR': str(e)[:200]}

# Re-ingest 15m and 4h data
print('\n--- Ingesting 15m data ---')
req = urllib.request.Request('http://localhost:8001/prices/ingest?ticker=BTC&timeframe=15m', method='POST', data=b'{}', headers={'Content-Type': 'application/json'})
r = test(req)
print(r)

print('\n--- Ingesting 4h data ---')
req = urllib.request.Request('http://localhost:8001/prices/ingest?ticker=BTC&timeframe=4h', method='POST', data=b'{}', headers={'Content-Type': 'application/json'})
r = test(req)
print(r)

# Test TA
print('\n--- TA 15m ---')
r = test('http://localhost:8001/ta/analyze?ticker=BTC&timeframe=15m')
print(r.get('signal'), r.get('confidence'), r.get('reasoning','')[:60] if 'reasoning' in r else r)

print('\n--- TA 4h ---')
r = test('http://localhost:8001/ta/analyze?ticker=BTC&timeframe=4h')
print(r.get('signal'), r.get('confidence'), r.get('reasoning','')[:60] if 'reasoning' in r else r)

print('\n--- TA 1h (control) ---')
r = test('http://localhost:8001/ta/analyze?ticker=BTC&timeframe=1h')
print(r.get('signal'), r.get('confidence'), r.get('reasoning','')[:60] if 'reasoning' in r else r)

proc.terminate()
proc.wait()
print('\nDone.')
