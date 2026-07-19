"""
pipeline.py — Full ingestion orchestration.

1. Fetch from all adapters
2. Deduplicate
3. Persist to PostgreSQL
4. Score sentiment (FinBERT)
5. Ingest to ChromaDB (RAG)
"""
import asyncio
from typing import List
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.app.ingestion.adapters.finnhub import FinnhubAdapter
from backend.app.ingestion.adapters.rss import RSSAdapter
from backend.app.ingestion.deduplicator import Deduplicator
from backend.app.db.models import RawArticle
from backend.app.db.repositories import ArticleRepository
from backend.app.signals.sentiment_engine import generate_sentiment_signal
from backend.app.signals.fundamental_engine import FundamentalEngine
from backend.app.core.config import get_settings


class IngestionPipeline:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.settings = get_settings()
        self.articles_repo = ArticleRepository(session)
        self.dedup = Deduplicator(session)
        self.finnhub = FinnhubAdapter()
        self.rss = RSSAdapter()
        self.fundamental = FundamentalEngine()

    async def run(self, tickers: List[str] = None, lookback_hours: int = 24) -> dict:
        """Run full ingestion pipeline for tickers."""
        if tickers is None:
            tickers = self.settings.TICKERS

        stats = {"fetched": 0, "new": 0, "scored": 0, "rag_ingested": 0, "errors": []}

        # 1. Fetch from all sources
        all_articles = []
        for ticker in tickers:
            try:
                # Finnhub
                finnhub_articles = await self.finnhub.fetch_company_news(ticker, lookback_hours)
                if ticker in ["BTC", "ETH"]:
                    finnhub_articles += await self.finnhub.fetch_crypto_news(lookback_hours)
                all_articles.extend(finnhub_articles)

                # RSS
                rss_articles = await self.rss.fetch_for_ticker(ticker, lookback_hours)
                all_articles.extend(rss_articles)

                stats["fetched"] += len(finnhub_articles) + len(rss_articles)
            except Exception as e:
                stats["errors"].append(f"{ticker}: {e}")

        # 2. Deduplicate
        new_articles = await self.dedup.filter_new(all_articles)
        stats["new"] = len(new_articles)

        # 3. Persist to PostgreSQL
        if new_articles:
            await self.articles_repo.upsert_many(new_articles)
            await self.session.commit()

        # 4. Score sentiment for new articles (FinBERT)
        scored = await self._score_new_articles()
        stats["scored"] = scored

        # 5. Ingest to ChromaDB for RAG
        rag_count = await self._ingest_to_rag(new_articles)
        stats["rag_ingested"] = rag_count

        return stats

    async def _score_new_articles(self) -> int:
        """Run FinBERT on unscored articles."""
        unscored = await self.articles_repo.get_unscored(limit=self.settings.BATCH_LIMIT)
        if not unscored:
            return 0

        # Load FinBERT in thread (heavy model load)
        def _load_pipeline():
            from transformers import pipeline
            return pipeline(
                "sentiment-analysis",
                model="ProsusAI/finbert",
                truncation=True,
            )

        classifier = await asyncio.to_thread(_load_pipeline)

        def _classify(text: str):
            result = classifier(text)[0]
            return result['label'].lower(), float(result['score'])

        count = 0
        for article in unscored:
            text = (article.headline or "") + ". " + (article.summary or "")
            text = text[:1000]
            try:
                label, score = await asyncio.to_thread(_classify, text)
                article.sentiment = label
                article.sentiment_score = score
                article.sentiment_at = datetime.now(timezone.utc)
                count += 1
            except Exception:
                continue

        await self.session.commit()
        return count

    async def _ingest_to_rag(self, articles: List[dict]) -> int:
        """Ingest articles into ChromaDB for RAG retrieval."""
        count = 0
        for a in articles:
            try:
                await self.fundamental.ingest_article(a)
                count += 1
            except Exception:
                continue
        return count