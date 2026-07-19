"""
rss.py — RSS feed adapter for news ingestion.
"""
from typing import List, Dict, Any
from datetime import datetime, timezone
import feedparser
import hashlib
from backend.app.core.config import get_settings


# Curated RSS feeds for financial news
RSS_FEEDS = {
    "BTC": [
        "https://cointelegraph.com/rss/tag/bitcoin",
        "https://cryptonews.net/rss/bitcoin.htm",
        "https://bitcoinmagazine.com/.rss/full/",
    ],
    "ETH": [
        "https://cointelegraph.com/rss/tag/ethereum",
        "https://cryptonews.net/rss/ethereum.htm",
    ],
    "XAUUSD": [
        "https://www.kitco.com/rss/KitcoNews.xml",
        "https://www.gold.org/rss.xml",
    ],
    "NVDA": [
        "https://feeds.finance.yahoo.com/rss/2.0/headline?s=NVDA&region=US&lang=en-US",
        "https://www.marketwatch.com/rss/topstories",
    ],
    "general": [
        "https://www.cnbc.com/id/100003114/device/rss/rss.html",
        "https://feeds.marketwatch.com/marketwatch/topstories/",
        "https://feeds.bloomberg.com/markets/news.rss",
        "https://www.reuters.com/business/finance/rss",
    ],
}


class RSSAdapter:
    def __init__(self):
        self.settings = get_settings()

    async def fetch_for_ticker(self, ticker: str, lookback_hours: int = 24) -> List[Dict[str, Any]]:
        """Fetch RSS articles for a specific ticker."""
        urls = RSS_FEEDS.get(ticker, []) + RSS_FEEDS.get("general", [])
        all_articles = []

        for url in urls:
            try:
                articles = await self._parse_feed(url, ticker, lookback_hours)
                all_articles.extend(articles)
            except Exception:
                continue

        return all_articles

    async def _parse_feed(self, url: str, default_ticker: str, lookback_hours: int) -> List[Dict[str, Any]]:
        feed = feedparser.parse(url)
        articles = []
        cutoff = datetime.now(timezone.utc) - __import__('datetime').timedelta(hours=lookback_hours)

        for entry in feed.entries:
            # Parse published date
            pub_dt = None
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                pub_dt = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
            elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                pub_dt = datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)

            if not pub_dt or pub_dt < cutoff:
                continue

            # Extract content
            headline = entry.get('title', '')
            summary = entry.get('summary', entry.get('description', ''))
            link = entry.get('link', '')

            # Generate deterministic source_id
            source_id = hashlib.sha256(f"{url}{link}".encode()).hexdigest()[:16]

            articles.append({
                "source": f"rss_{url.split('/')[2]}",
                "source_id": source_id,
                "url": link,
                "ticker": default_ticker,
                "headline": headline,
                "summary": summary,
                "source_name": feed.feed.get('title', url),
                "image": "",
                "published_at": pub_dt,
                "raw_json": dict(entry),
            })
        return articles