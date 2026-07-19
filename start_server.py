#!/usr/bin/env python
"""
start_server.py — Starts the NLPTrader API server and keeps it running.
Usage:
    python start_server.py [--port 8000] [--reload]
"""
import sys, os, subprocess, argparse

BASE = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE)

parser = argparse.ArgumentParser()
parser.add_argument('--port', type=int, default=8000)
parser.add_argument('--reload', action='store_true')
args = parser.parse_args()

env = os.environ.copy()
env['PYTHONPATH'] = BASE

cmd = [sys.executable, '-m', 'uvicorn', 'backend.app.main:app', '--port', str(args.port)]
if args.reload:
    cmd.append('--reload')

proc = subprocess.Popen(cmd, cwd=BASE, env=env)
print(f'Server started (PID={proc.pid}) on http://localhost:{args.port}')
sys.stdout.flush()
proc.wait()
