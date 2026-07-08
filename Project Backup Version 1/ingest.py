"""
ingest.py — fetch financial news from Finnhub and shape it for our database.

Finnhub's company-news endpoint:
    GET https://finnhub.io/api/v1/company-news?symbol=AAPL&from=YYYY-MM-DD&to=YYYY-MM-DD&token=KEY
Returns a list of articles, each like:
    {"datetime": 1700000000, "headline": "...", "summary": "...",
     "source": "...", "url": "...", "related": "AAPL", ...}
"""
import time
from datetime import datetime, timedelta, timezone

import requests

from config import FINNHUB_API_KEY, TICKERS, LOOKBACK_DAYS
from relevance import is_relevant

BASE_URL = "https://finnhub.io/api/v1/company-news"


def _unix_to_iso(unix_seconds):
    """Finnhub gives time as a unix number; we store a readable UTC string.
    Roman Urdu: Finnhub time ko number (unix) me deta hai — hum use padhne layak
    UTC date-time string me convert kar lete hain taake baad me samajhna aasaan ho."""
    return datetime.fromtimestamp(unix_seconds, tz=timezone.utc).isoformat()


def fetch_for_ticker(ticker):
    """Fetch recent news for one ticker and return a list of clean dicts."""
    today = datetime.now(timezone.utc).date()
    start = today - timedelta(days=LOOKBACK_DAYS)

    params = {
        "symbol": ticker,
        "from": start.isoformat(),
        "to": today.isoformat(),
        "token": FINNHUB_API_KEY,
    }
    resp = requests.get(BASE_URL, params=params, timeout=20)
    resp.raise_for_status()  # turns an HTTP error (e.g. bad key) into a clear exception
    raw = resp.json()

    now_iso = datetime.now(timezone.utc).isoformat()
    articles = []
    skipped = 0
    for item in raw:
        # Skip junk entries that have no headline or url.
        if not item.get("headline") or not item.get("url"):
            continue
        # Relevance gate: drop news that isn't actually about this company.
        # Roman Urdu: Yahan ghair-mutaaliqa khabrein chhaant deti hain, taake sentiment saaf rahe.
        if not is_relevant(ticker, item.get("headline"), item.get("summary")):
            skipped += 1
            continue
        articles.append(
            {
                "ticker": ticker,
                "headline": item.get("headline"),
                "summary": item.get("summary"),
                "source": item.get("source"),
                "url": item.get("url"),
                "published_at": _unix_to_iso(item.get("datetime", 0)),
                "fetched_at": now_iso,
            }
        )
    if skipped:
        print(f"    ({skipped} off-topic articles filtered out)")
    return articles


def fetch_all():
    """Loop over every ticker in config. Small sleep to respect the free-tier rate limit.
    Roman Urdu: Har ticker ke beech thora sa ruk jate hain (sleep) taake free plan ki
    rate limit cross na ho aur Finnhub humein block na kare."""
    all_articles = []
    for ticker in TICKERS:
        try:
            items = fetch_for_ticker(ticker)
            print(f"  {ticker}: {len(items)} articles fetched")
            all_articles.extend(items)
        except requests.HTTPError as e:
            print(f"  {ticker}: HTTP error -> {e}")
        time.sleep(1.1)  # free tier allows ~60 calls/min; 1.1s is safe
    return all_articles
