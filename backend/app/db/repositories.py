from datetime import datetime, timezone, timedelta
from typing import Optional
from sqlalchemy import select, func, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.db.models import (
    Ticker, RawArticle, ArticleTicker, PriceOHLCV, Signal, Outcome
)


class TickerRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, ticker: str) -> Optional[Ticker]:
        stmt = select(Ticker).where(Ticker.ticker == ticker)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all_tracked(self) -> list[Ticker]:
        stmt = select(Ticker).where(Ticker.is_actively_tracked == True)
        return list((await self.session.execute(stmt)).scalars())


class ArticleRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def upsert_many(self, articles: list[dict]) -> int:
        from sqlalchemy.dialects.postgresql import insert
        if not articles:
            return 0
        stmt = insert(RawArticle).values(articles)
        stmt = stmt.on_conflict_do_nothing(index_elements=["source", "source_id"])
        result = await self.session.execute(stmt)
        return result.rowcount

    async def get_unscored(self, limit: int = 100) -> list[RawArticle]:
        stmt = select(RawArticle).where(RawArticle.sentiment.is_(None)).limit(limit)
        return list((await self.session.execute(stmt)).scalars())

    async def get_unembedded(self, limit: int = 100) -> list[RawArticle]:
        stmt = select(RawArticle).where(RawArticle.embedding.is_(None)).limit(limit)
        return list((await self.session.execute(stmt)).scalars())

    async def get_by_ticker_since(self, ticker: str, since: datetime, limit: int = 500) -> list[RawArticle]:
        stmt = select(RawArticle).join(
            ArticleTicker, ArticleTicker.article_id == RawArticle.id
        ).where(
            ArticleTicker.ticker == ticker,
            RawArticle.published_at >= since,
            RawArticle.sentiment.is_not(None)
        ).order_by(desc(RawArticle.published_at)).limit(limit)
        return list((await self.session.execute(stmt)).scalars())

    async def get_for_fundamental(self, ticker: str, cutoff: datetime, limit: int = 10) -> list[RawArticle]:
        stmt = select(RawArticle).join(
            ArticleTicker, ArticleTicker.article_id == RawArticle.id
        ).where(
            ArticleTicker.ticker == ticker,
            RawArticle.published_at >= cutoff,
            RawArticle.sentiment.is_not(None)
        ).order_by(desc(RawArticle.published_at)).limit(limit)
        return list((await self.session.execute(stmt)).scalars())

    async def get_by_id(self, article_id: int) -> Optional[RawArticle]:
        stmt = select(RawArticle).where(RawArticle.id == article_id)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def update_embedding(self, article_id: int, embedding: list[float]):
        stmt = select(RawArticle).where(RawArticle.id == article_id)
        result = await self.session.execute(stmt)
        article = result.scalar_one_or_none()
        if article:
            article.embedding = embedding


class ArticleTickerRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def upsert_many(self, mappings: list[dict]) -> int:
        from sqlalchemy.dialects.postgresql import insert
        if not mappings:
            return 0
        stmt = insert(ArticleTicker).values(mappings)
        stmt = stmt.on_conflict_do_nothing(index_elements=["article_id", "ticker"])
        result = await self.session.execute(stmt)
        return result.rowcount


class PriceRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def upsert_bars(self, ticker: str, timeframe: str, bars: list[dict]) -> int:
        from sqlalchemy.dialects.postgresql import insert
        if not bars:
            return 0
        total = 0
        chunk_size = 2000
        for i in range(0, len(bars), chunk_size):
            chunk = bars[i:i + chunk_size]
            values = [
                {"ticker": ticker, "timeframe": timeframe, **b}
                for b in chunk
            ]
            stmt = insert(PriceOHLCV).values(values)
            stmt = stmt.on_conflict_do_update(
                index_elements=["ticker", "timeframe", "ts"],
                set_={"open": stmt.excluded.open, "high": stmt.excluded.high,
                      "low": stmt.excluded.low, "close": stmt.excluded.close,
                      "volume": stmt.excluded.volume}
            )
            result = await self.session.execute(stmt)
            total += result.rowcount
        return total

    async def get_latest(self, ticker: str, timeframe: str, limit: int = 500) -> list[PriceOHLCV]:
        stmt = select(PriceOHLCV).where(
            PriceOHLCV.ticker == ticker,
            PriceOHLCV.timeframe == timeframe
        ).order_by(desc(PriceOHLCV.ts)).limit(limit)
        return list((await self.session.execute(stmt)).scalars())

    async def get_range(self, ticker: str, timeframe: str,
                        start: datetime, end: datetime) -> list[PriceOHLCV]:
        stmt = select(PriceOHLCV).where(
            PriceOHLCV.ticker == ticker,
            PriceOHLCV.timeframe == timeframe,
            PriceOHLCV.ts >= start,
            PriceOHLCV.ts <= end
        ).order_by(PriceOHLCV.ts)
        return list((await self.session.execute(stmt)).scalars())

    async def get_distinct_timeframes(self, ticker: str) -> list:
        stmt = select(PriceOHLCV.timeframe).where(
            PriceOHLCV.ticker == ticker
        ).distinct()
        rows = (await self.session.execute(stmt)).all()
        return sorted([r[0] for r in rows])

    async def get_latest_price(self, ticker: str) -> Optional[float]:
        stmt = select(PriceOHLCV.close).where(
            PriceOHLCV.ticker == ticker
        ).order_by(desc(PriceOHLCV.ts)).limit(1)
        result = await self.session.execute(stmt)
        row = result.one_or_none()
        return float(row[0]) if row else None


class SignalRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, signal: Signal) -> Signal:
        self.session.add(signal)
        await self.session.flush()
        return signal

    async def get_active(self, ticker: Optional[str] = None) -> list[Signal]:
        stmt = select(Signal).where(Signal.status == "active")
        if ticker:
            stmt = stmt.where(Signal.ticker == ticker)
        stmt = stmt.order_by(desc(Signal.generated_at))
        return list((await self.session.execute(stmt)).scalars())

    async def get_by_id(self, signal_id: int) -> Optional[Signal]:
        stmt = select(Signal).where(Signal.id == signal_id)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_history(self, ticker: Optional[str] = None,
                          status: Optional[str] = None,
                          limit: int = 100, offset: int = 0) -> list[Signal]:
        stmt = select(Signal)
        if ticker:
            stmt = stmt.where(Signal.ticker == ticker)
        if status:
            stmt = stmt.where(Signal.status == status)
        stmt = stmt.order_by(desc(Signal.generated_at)).limit(limit).offset(offset)
        return list((await self.session.execute(stmt)).scalars())

    async def get_expired_pending_outcome(self) -> list[Signal]:
        now = datetime.now(timezone.utc)
        stmt = select(Signal).where(
            Signal.status == "active",
        ).join(Outcome, Outcome.signal_id == Signal.id, isouter=True).where(Outcome.id.is_(None))
        return list((await self.session.execute(stmt)).scalars())

    async def update_status(self, signal_id: int, status: str):
        stmt = select(Signal).where(Signal.id == signal_id)
        result = await self.session.execute(stmt)
        signal = result.scalar_one_or_none()
        if signal:
            signal.status = status


class OutcomeRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, outcome: Outcome) -> Outcome:
        self.session.add(outcome)
        await self.session.flush()
        return outcome

    async def get_summary(self, ticker: Optional[str] = None) -> dict:
        from sqlalchemy import case
        stmt = select(
            func.count(Signal.id).label("total"),
            func.sum(case((Outcome.outcome == "correct", 1), else_=0)).label("correct"),
            func.sum(case((Outcome.outcome == "incorrect", 1), else_=0)).label("incorrect"),
            func.sum(case((Outcome.outcome == "neutral", 1), else_=0)).label("neutral"),
            func.avg(case((Outcome.outcome == "correct", Outcome.return_pct))).label("avg_return"),
        ).join(Outcome, Outcome.signal_id == Signal.id)
        if ticker:
            stmt = stmt.where(Signal.ticker == ticker)
        result = await self.session.execute(stmt)
        row = result.one()
        total = row.total or 0
        correct = row.correct or 0
        return {
            "total_signals": total,
            "correct": correct,
            "incorrect": row.incorrect or 0,
            "neutral": row.neutral or 0,
            "accuracy": round(correct / total * 100, 1) if total else 0,
            "avg_return_pct": round(float(row.avg_return or 0), 2),
        }

