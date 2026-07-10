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

from config import FINNHUB_API_KEY, STOCKS, CRYPTO, FOREX, LOOKBACK_DAYS
from relevance import is_relevant, match_symbol

BASE_URL = "https://finnhub.io/api/v1/company-news"      # per-stock news
MARKET_NEWS_URL = "https://finnhub.io/api/v1/news"       # general category news (crypto/forex)


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
                "image": item.get("image"),
                "published_at": _unix_to_iso(item.get("datetime", 0)),
                "fetched_at": now_iso,
            }
        )
    if skipped:
        print(f"    ({skipped} off-topic articles filtered out)")
    return articles


def fetch_category(category):
    """Fetch Finnhub's GENERAL market news for a category ('crypto' or 'forex').
    Free tier doesn't give per-coin/per-pair feeds, so we pull the category then tag.
    Roman Urdu: Free plan per-coin news nahi deta — hum poori crypto/forex news le kar
    har khabar ko uske symbol se khud tag karte hain."""
    params = {"category": category, "token": FINNHUB_API_KEY}
    resp = requests.get(MARKET_NEWS_URL, params=params, timeout=20)
    resp.raise_for_status()
    return resp.json()


def tag_category_news(raw, symbols):
    """Tag each general article to the FIRST symbol it actually mentions; drop the rest."""
    now_iso = datetime.now(timezone.utc).isoformat()
    out = []
    for item in raw:
        if not item.get("headline") or not item.get("url"):
            continue
        sym = match_symbol(symbols, item.get("headline"), item.get("summary"))
        if not sym:
            continue
        out.append(
            {
                "ticker": sym,
                "headline": item.get("headline"),
                "summary": item.get("summary"),
                "source": item.get("source"),
                "url": item.get("url"),
                "image": item.get("image"),
                "published_at": _unix_to_iso(item.get("datetime", 0)),
                "fetched_at": now_iso,
            }
        )
    return out


def fetch_all():
    """Stocks: per-symbol company news. Crypto/Forex: one category call each, then tag.
    Roman Urdu: Stocks ke liye har symbol par call; crypto/forex ke liye ek hi category
    call aur phir tagging — is se API calls bachti hain."""
    all_articles = []

    # --- Stocks (one call per symbol) ---
    for ticker in STOCKS:
        try:
            items = fetch_for_ticker(ticker)
            print(f"  {ticker}: {len(items)} articles")
            all_articles.extend(items)
        except requests.HTTPError as e:
            print(f"  {ticker}: HTTP error -> {e}")
        time.sleep(1.1)  # free tier ~60 calls/min

    # --- Crypto & Forex (one category call each) ---
    for category, symbols in (("crypto", CRYPTO), ("forex", FOREX)):
        try:
            raw = fetch_category(category)
            tagged = tag_category_news(raw, symbols)
            print(f"  {category}: {len(tagged)} tagged from {len(raw)} general articles")
            all_articles.extend(tagged)
        except requests.HTTPError as e:
            print(f"  {category}: HTTP error -> {e}")
        time.sleep(1.1)

    return all_articles
