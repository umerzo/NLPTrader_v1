"""
finnhub.py — Finnhub API adapter for news ingestion.
"""
from typing import List, Dict, Any
from datetime import datetime, timezone
import httpx
from backend.app.core.config import get_settings


class FinnhubAdapter:
    BASE_URL = "https://finnhub.io/api/v1"

    def __init__(self):
        self.settings = get_settings()
        self.client = httpx.AsyncClient(timeout=30.0)

    async def fetch_company_news(self, ticker: str, lookback_hours: int = 24) -> List[Dict[str, Any]]:
        """Fetch company-specific news from Finnhub."""
        if not self.settings.FINNHUB_API_KEY:
            return []

        params = {
            "symbol": ticker,
            "from": (datetime.now(timezone.utc).date() - __import__('datetime').timedelta(days=1)).isoformat(),
            "token": self.settings.FINNHUB_API_KEY,
        }

        try:
            resp = await self.client.get(f"{self.BASE_URL}/company-news", params=params)
            resp.raise_for_status()
            data = resp.json()
        except Exception:
            return []

        articles = []
        for item in data:
            # Filter by time
            pub_ts = item.get('datetime', 0)
            pub_dt = datetime.fromtimestamp(pub_ts, tz=timezone.utc)
            if (datetime.now(timezone.utc) - pub_dt).total_seconds() / 3600 > lookback_hours:
                continue

            articles.append({
                "source": "finnhub",
                "source_id": str(item.get('id', item.get('url', ''))),
                "url": item.get('url', ''),
                "ticker": ticker,
                "headline": item.get('headline', ''),
                "summary": item.get('summary', ''),
                "published_at": pub_dt,
                "raw_json": item,
            })
        return articles

    async def fetch_crypto_news(self, lookback_hours: int = 24) -> List[Dict[str, Any]]:
        """Fetch general crypto news."""
        if not self.settings.FINNHUB_API_KEY:
            return []

        try:
            resp = await self.client.get(
                f"{self.BASE_URL}/news",
                params={"category": "crypto", "token": self.settings.FINNHUB_API_KEY}
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception:
            return []

        articles = []
        for item in data:
            pub_ts = item.get('datetime', 0)
            pub_dt = datetime.fromtimestamp(pub_ts, tz=timezone.utc)
            if (datetime.now(timezone.utc) - pub_dt).total_seconds() / 3600 > lookback_hours:
                continue

            # Map to relevant crypto tickers
            for ticker in ["BTC", "ETH", "SOL", "XRP", "BNB"]:
                if ticker.lower() in (item.get('headline', '') + item.get('summary', '')).lower():
                    articles.append({
                        "source": "finnhub_crypto",
                        "source_id": f"{item.get('id', item.get('url', ''))}_{ticker}",
                        "url": item.get('url', ''),
                        "ticker": ticker,
                        "headline": item.get('headline', ''),
                        "summary": item.get('summary', ''),
                        "published_at": pub_dt,
                        "raw_json": item,
                    })
        return articles

    async def close(self):
        await self.client.aclose()