import logging
from typing import Optional
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.ingestion.adapters.finnhub import FinnhubAdapter
from backend.app.ingestion.adapters.rss import RSSAdapter
from backend.app.ingestion.deduplicator import Deduplicator
from backend.app.ingestion.entity_mapper import map_article_tickers
from backend.app.db.models import RawArticle, ArticleTicker, Ticker
from backend.app.db.repositories import ArticleRepository, ArticleTickerRepository
from backend.app.signals.finbert_scorer import score_articles
from backend.app.signals.embedder import embed_text
from backend.app.core.config import get_settings

logger = logging.getLogger(__name__)


class IngestionPipeline:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.settings = get_settings()
        self.articles_repo = ArticleRepository(session)
        self.article_ticker_repo = ArticleTickerRepository(session)
        self.dedup = Deduplicator(session)
        self.finnhub = FinnhubAdapter()
        self.rss = RSSAdapter()

    async def run(self, tickers: list[str] | None = None, lookback_hours: int = 24) -> dict:
        if tickers is None:
            tickers = self.settings.TICKERS

        stats: dict = {"fetched": 0, "new": 0, "scored": 0, "embedded": 0, "mapped": 0, "errors": [], "_lookback": lookback_hours}

        all_articles = await self._fetch_all(tickers, stats)
        new_articles = await self._dedup(all_articles, stats)
        await self._persist(new_articles, stats)
        await self._score_unscored(stats)
        await self._embed_new(stats)
        await self._map_entities(stats)

        return stats

    async def run_single_ticker(self, ticker: str, lookback_hours: int = 24) -> dict:
        ticker = ticker.upper()
        stats: dict = {"fetched": 0, "new": 0, "scored": 0, "embedded": 0, "mapped": 0, "errors": [], "_lookback": lookback_hours}

        articles = await self._fetch_single(ticker, stats)
        new_articles = await self._dedup(articles, stats)
        await self._persist(new_articles, stats)
        await self._score_unscored(stats)
        await self._embed_new(stats)
        await self._map_entities(stats)

        return stats

    async def _fetch_all(self, tickers: list[str], stats: dict) -> list[dict]:
        all_articles = []
        for ticker in tickers:
            try:
                results = await self._fetch_single(ticker, stats)
                all_articles.extend(results)
            except Exception as e:
                stats["errors"].append(f"{ticker}: {e}")
        return all_articles

    async def _fetch_single(self, ticker: str, stats: dict) -> list[dict]:
        articles = []
        lookback = stats.get("_lookback", 24)
        finnhub = await self.finnhub.fetch_company_news(ticker, lookback)
        if ticker in ("BTC", "ETH"):
            finnhub += await self.finnhub.fetch_crypto_news(lookback)
        articles.extend(finnhub)
        rss = await self.rss.fetch_for_ticker(ticker, lookback)
        articles.extend(rss)
        stats["fetched"] = stats.get("fetched", 0) + len(articles)
        return articles

    async def _dedup(self, articles: list[dict], stats: dict) -> list[dict]:
        new = await self.dedup.filter_new(articles)
        stats["new"] = len(new)
        return new

    RAW_ARTICLE_COLUMNS = {"source", "source_id", "url", "headline", "summary", "published_at"}

    async def _persist(self, articles: list[dict], stats: dict):
        if not articles:
            return
        filtered = [{k: v for k, v in a.items() if k in self.RAW_ARTICLE_COLUMNS} for a in articles]
        await self.articles_repo.upsert_many(filtered)
        await self.session.commit()

    async def _score_unscored(self, stats: dict):
        unscored = await self.articles_repo.get_unscored(limit=self.settings.BATCH_LIMIT)
        if not unscored:
            return
        unscored_dicts = [
            {"id": a.id, "source": a.source, "source_id": a.source_id,
             "headline": a.headline, "summary": a.summary}
            for a in unscored
        ]
        scored = await score_articles(unscored_dicts)
        for s in scored:
            stmt = select(RawArticle).where(RawArticle.id == s["id"])
            result = await self.session.execute(stmt)
            article = result.scalar_one_or_none()
            if article:
                article.sentiment = s["sentiment"]
                article.sentiment_score = s["sentiment_score"]
                article.sentiment_scored_at = s["sentiment_scored_at"]
        await self.session.commit()
        stats["scored"] = len(scored)

    async def _embed_new(self, stats: dict):
        unembedded = await self.articles_repo.get_unembedded(limit=self.settings.BATCH_LIMIT)
        count = 0
        for article in unembedded:
            try:
                text = f"{article.headline}. {article.summary or ''}"[:1000]
                article.embedding = embed_text(text)
                count += 1
            except Exception as e:
                logger.error("Embedding failed for article %d: %s", article.id, e)
        if count:
            await self.session.commit()
        stats["embedded"] = count

    async def _map_entities(self, stats: dict):
        known_result = await self.session.execute(
            select(Ticker.ticker).where(Ticker.is_actively_tracked == True)
        )
        known_tickers = {row[0] for row in known_result.all()}
        if not known_tickers:
            known_tickers = set(self.settings.TICKERS)

        stmt = select(RawArticle).outerjoin(
            ArticleTicker, ArticleTicker.article_id == RawArticle.id
        ).where(ArticleTicker.article_id.is_(None)).limit(self.settings.BATCH_LIMIT)

        result = await self.session.execute(stmt)
        unmapped = result.scalars().all()

        mappings = []
        for article in unmapped:
            try:
                links = map_article_tickers(article.headline, article.summary, known_tickers)
                for link in links:
                    if link["ticker"] not in known_tickers:
                        continue
                    mappings.append({
                        "article_id": article.id,
                        "ticker": link["ticker"],
                        "event_type": link["event_type"],
                        "relevance": link["relevance"],
                    })
            except Exception as e:
                logger.error("Entity mapping failed for article %d: %s", article.id, e)

        if mappings:
            await self.article_ticker_repo.upsert_many(mappings)
            await self.session.commit()
        stats["mapped"] = len(mappings)
