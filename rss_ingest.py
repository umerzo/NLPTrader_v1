"""
rss_ingest.py — pull news from many FREE RSS feeds, filter to our symbols, store in the DB.

Flow:  RSS feeds  ->  strip HTML  ->  RELEVANCE FILTER (keep only articles that mention a
tracked symbol, and tag them)  ->  dedupe by url  ->  save to nlptrader.db
Later, sentiment.py scores whatever landed. So the filter runs BEFORE FinBERT — exactly right.
Roman Urdu: Pehle saari RSS news lo, HTML saaf karo, phir relevance filter se sirf wohi
khabrein rakho jo kisi tracked symbol ka zikr karti hain (aur usi symbol se tag kar do),
duplicate hatao, database me daal do. FinBERT baad me chalta hai — filter uss se pehle.

Run with:  python rss_ingest.py
Needs:     pip install feedparser   (already in requirements-pipeline.txt)
"""
import re
import time
import calendar
from datetime import datetime, timezone

import feedparser

from config import TICKERS
from relevance import match_symbol
from db import init_db, save_articles, count_articles

# All FREE. Grouped for readability. Some feeds occasionally change/break — the code skips
# any that fail, so one dead feed never stops the run.
FEEDS = {
    # ---- Markets / equities ----
    "MarketWatch": "https://feeds.marketwatch.com/marketwatch/topstories/",
    "MarketWatch-RT": "https://feeds.marketwatch.com/marketwatch/realtimeheadlines/",
    "CNBC-Top": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114",
    "CNBC-Markets": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=20910258",
    "SeekingAlpha": "https://seekingalpha.com/market_currents.xml",
    "Yahoo-Finance": "https://finance.yahoo.com/news/rssindex",
    # ---- Macro / policy (moves the whole market) ----
    "Fed": "https://www.federalreserve.gov/feeds/press_all.xml",
    "SEC": "https://www.sec.gov/news/pressreleases.rss",
    "EIA-Energy": "https://www.eia.gov/rss/todayinenergy.xml",
    # ---- Crypto ----
    "CoinDesk": "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "Cointelegraph": "https://cointelegraph.com/rss",
    "Decrypt": "https://decrypt.co/feed",
    "BitcoinMag": "https://bitcoinmagazine.com/feed",
    "CryptoSlate": "https://cryptoslate.com/feed/",
    # ---- Forex / commodities ----
    "FXStreet": "https://www.fxstreet.com/rss/news",
    "Investing-Forex": "https://www.investing.com/rss/news_1.rss",
    "Kitco-Gold": "https://www.kitco.com/rss/KitcoNews.xml",
    "OilPrice": "https://oilprice.com/rss/main",
    "Mining": "https://www.mining.com/feed/",
}

# Pretend to be a normal browser so feeds don't 403 us.
USER_AGENT = "Mozilla/5.0 (NLPTrader RSS reader)"
MAX_PER_FEED = 60  # keep runs bounded


def _clean(text):
    """Remove HTML tags and squeeze whitespace — FinBERT wants plain text."""
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", text or "")).strip()


def _published_iso(entry):
    """RSS gives time in many formats; feedparser normalises to a UTC struct. Fall back to now."""
    for key in ("published_parsed", "updated_parsed"):
        t = entry.get(key)
        if t:
            return datetime.fromtimestamp(calendar.timegm(t), tz=timezone.utc).isoformat()
    return datetime.now(timezone.utc).isoformat()


def fetch_feed(name, url):
    """Parse one feed; tag each article to the first tracked symbol it mentions; drop the rest."""
    now_iso = datetime.now(timezone.utc).isoformat()
    parsed = feedparser.parse(url, agent=USER_AGENT)
    kept = []
    for entry in parsed.entries[:MAX_PER_FEED]:
        headline = _clean(entry.get("title"))
        summary = _clean(entry.get("summary", ""))
        link = entry.get("link")
        if not headline or not link:
            continue
        # THE FILTER: only keep news that is actually about one of our symbols.
        sym = match_symbol(TICKERS, headline, summary)
        if not sym:
            continue
        kept.append(
            {
                "ticker": sym,
                "headline": headline,
                "summary": summary,
                "source": name,
                "url": link,
                "published_at": _published_iso(entry),
                "fetched_at": now_iso,
            }
        )
    return kept


def main():
    init_db()
    all_articles = []
    print(f"Reading {len(FEEDS)} RSS feeds...\n")
    for name, url in FEEDS.items():
        try:
            kept = fetch_feed(name, url)
            print(f"  {name:<16} kept {len(kept)} on-topic")
            all_articles.extend(kept)
        except Exception as e:  # a broken feed should never stop the whole run
            print(f"  {name:<16} FAILED ({type(e).__name__}) — skipped")
        time.sleep(0.5)

    new_count = save_articles(all_articles)
    print(f"\nMatched {len(all_articles)} on-topic articles | {new_count} new | "
          f"{count_articles()} total in database")
    print("Next: python sentiment.py  ->  python signal_engine.py  ->  python llm_explain.py")


if __name__ == "__main__":
    main()
