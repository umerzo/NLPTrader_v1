"""
repositories.py — Data access layer. Pure async SQLAlchemy.
No business logic, just CRUD + queries.
"""
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any
from sqlalchemy import select, func, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.db.models import (
    RawArticle, PriceOHLCV, Signal, Outcome, ModelVersion, BacktestRun
)


class ArticleRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def upsert_many(self, articles: List[dict]) -> int:
        """Bulk upsert articles. Returns count of new rows."""
        from sqlalchemy.dialects.postgresql import insert
        if not articles:
            return 0
        stmt = insert(RawArticle).values(articles)
        stmt = stmt.on_conflict_do_nothing(index_elements=["source", "source_id"])
        result = await self.session.execute(stmt)
        return result.rowcount

    async def get_unscored(self, limit: int = 100) -> List[RawArticle]:
        stmt = select(RawArticle).where(RawArticle.sentiment.is_(None)).limit(limit)
        return list((await self.session.execute(stmt)).scalars())

    async def get_by_ticker_since(self, ticker: str, since: datetime, limit: int = 500) -> List[RawArticle]:
        stmt = select(RawArticle).where(
            RawArticle.ticker == ticker,
            RawArticle.published_at >= since,
            RawArticle.sentiment.is_not(None)
        ).order_by(desc(RawArticle.published_at)).limit(limit)
        return list((await self.session.execute(stmt)).scalars())

    async def get_for_fundamental(self, ticker: str, cutoff: datetime, limit: int = 10) -> List[RawArticle]:
        stmt = select(RawArticle).where(
            RawArticle.ticker == ticker,
            RawArticle.published_at >= cutoff,
            RawArticle.sentiment.is_not(None)
        ).order_by(desc(RawArticle.published_at)).limit(limit)
        return list((await self.session.execute(stmt)).scalars())


class PriceRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def upsert_bars(self, ticker: str, timeframe: str, bars: List[dict]) -> int:
        """bars: list of {timestamp, open, high, low, close, volume}"""
        from sqlalchemy.dialects.postgresql import insert
        if not bars:
            return 0
        total = 0
        chunk_size = 2000  # keep under asyncpg 32767 param limit (~14 params/row with on_conflict)
        for i in range(0, len(bars), chunk_size):
            chunk = bars[i:i + chunk_size]
            values = [
                {"ticker": ticker, "timeframe": timeframe, **b}
                for b in chunk
            ]
            stmt = insert(PriceOHLCV).values(values)
            stmt = stmt.on_conflict_do_update(
                index_elements=["ticker", "timeframe", "timestamp"],
                set_={"open": stmt.excluded.open, "high": stmt.excluded.high,
                      "low": stmt.excluded.low, "close": stmt.excluded.close,
                      "volume": stmt.excluded.volume}
            )
            result = await self.session.execute(stmt)
            total += result.rowcount
        return total

    async def get_latest(self, ticker: str, timeframe: str, limit: int = 500) -> List[PriceOHLCV]:
        stmt = select(PriceOHLCV).where(
            PriceOHLCV.ticker == ticker,
            PriceOHLCV.timeframe == timeframe
        ).order_by(desc(PriceOHLCV.timestamp)).limit(limit)
        return list((await self.session.execute(stmt)).scalars())

    async def get_range(self, ticker: str, timeframe: str,
                        start: datetime, end: datetime) -> List[PriceOHLCV]:
        stmt = select(PriceOHLCV).where(
            PriceOHLCV.ticker == ticker,
            PriceOHLCV.timeframe == timeframe,
            PriceOHLCV.timestamp >= start,
            PriceOHLCV.timestamp <= end
        ).order_by(PriceOHLCV.timestamp)
        return list((await self.session.execute(stmt)).scalars())

    async def get_distinct_timeframes(self, ticker: str) -> list:
        stmt = select(PriceOHLCV.timeframe).where(
            PriceOHLCV.ticker == ticker
        ).distinct()
        rows = (await self.session.execute(stmt)).all()
        return sorted([r[0] for r in rows])


class SignalRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, signal: Signal) -> Signal:
        self.session.add(signal)
        await self.session.flush()
        return signal

    async def get_active(self, ticker: Optional[str] = None) -> List[Signal]:
        stmt = select(Signal).where(Signal.status == "active")
        if ticker:
            stmt = stmt.where(Signal.ticker == ticker)
        stmt = stmt.order_by(desc(Signal.generated_at))
        return list((await self.session.execute(stmt)).scalars())

    async def get_expired_pending_outcome(self) -> List[Signal]:
        now = datetime.now(timezone.utc)
        stmt = select(Signal).where(
            Signal.status == "active",
            Signal.expires_at <= now
        ).join(Outcome, Outcome.signal_id == Signal.id, isouter=True).where(Outcome.id.is_(None))
        return list((await self.session.execute(stmt)).scalars())

    async def get_by_model_version(self, version: str, limit: int = 1000) -> List[Signal]:
        stmt = select(Signal).where(Signal.model_version == version).order_by(desc(Signal.generated_at)).limit(limit)
        return list((await self.session.execute(stmt)).scalars())


class OutcomeRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, outcome: Outcome) -> Outcome:
        self.session.add(outcome)
        await self.session.flush()
        return outcome

    async def get_summary(self, ticker: Optional[str] = None) -> Dict[str, Any]:
        """Accuracy, calibration, P&L summary."""
        from sqlalchemy import case
        stmt = select(
            func.count(Signal.id).label("total"),
            func.sum(case((Outcome.outcome == "correct", 1), else_=0)).label("correct"),
            func.avg(case((Outcome.outcome == "correct", Outcome.price_change_pct))).label("avg_return"),
        ).join(Outcome, Outcome.signal_id == Signal.id)
        if ticker:
            stmt = stmt.where(Signal.ticker == ticker)
        result = await self.session.execute(stmt)
        row = result.one()
        total = row.total or 0
        correct = row.correct or 0
        return {
            "total_signals": total,
            "accuracy": round(correct / total * 100, 1) if total else 0,
            "avg_return_pct": round(float(row.avg_return or 0), 2),
        }


class ModelVersionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, version: str, config: dict, description: str = "", parent: str = None) -> ModelVersion:
        mv = ModelVersion(version=version, config=config, description=description, parent_version=parent)
        self.session.add(mv)
        await self.session.flush()
        return mv

    async def get_active(self) -> Optional[ModelVersion]:
        stmt = select(ModelVersion).where(ModelVersion.is_active == True)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_by_version(self, version: str) -> Optional[ModelVersion]:
        stmt = select(ModelVersion).where(ModelVersion.version == version)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def set_active(self, version: str):
        await self.session.execute(
            ModelVersion.__table__.update().values(is_active=False).where(ModelVersion.is_active == True)
        )
        await self.session.execute(
            ModelVersion.__table__.update().values(is_active=True).where(ModelVersion.version == version)
        )