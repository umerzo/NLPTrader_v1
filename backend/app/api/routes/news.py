from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from backend.app.db.session import get_db
from backend.app.db.models import RawArticle

router = APIRouter(prefix="/api/news", tags=["news"])


@router.get("/articles")
async def get_articles(
    ticker: str | None = Query(None, description="Filter by ticker"),
    limit: int = Query(50, le=200),
    offset: int = 0,
    session: AsyncSession = Depends(get_db),
):
    """Paginated articles with optional ticker filter."""
    from sqlalchemy.orm import joinedload

    stmt = select(RawArticle).options(joinedload(RawArticle.ticker_links))
    if ticker:
        ticker = ticker.upper()
        stmt = stmt.where(RawArticle.ticker_links.any(ticker=ticker))

    count_stmt = select(RawArticle.id)
    if ticker:
        count_stmt = count_stmt.where(RawArticle.ticker_links.any(ticker=ticker))
    total = len((await session.execute(count_stmt)).all())

    stmt = stmt.order_by(desc(RawArticle.published_at)).limit(limit).offset(offset)
    rows = (await session.execute(stmt)).unique().scalars().all()

    return {
        "items": [
            {
                "id": a.id,
                "source": a.source,
                "headline": a.headline,
                "summary": a.summary,
                "published_at": a.published_at.isoformat(),
                "sentiment": a.sentiment,
                "sentiment_score": float(a.sentiment_score) if a.sentiment_score else None,
                "url": a.url,
                "ticker": a.ticker_links[0].ticker if a.ticker_links else None,
            }
            for a in rows
        ],
        "total": total,
    }


@router.get("/{ticker}")
async def get_news(
    ticker: str,
    limit: int = Query(50, le=200),
    offset: int = 0,
    session: AsyncSession = Depends(get_db),
):
    """Paginated articles + sentiment badge per article for a ticker."""
    ticker = ticker.upper()

    stmt = select(RawArticle).where(
        RawArticle.ticker_links.any(ticker=ticker)
    )

    count_stmt = select(RawArticle.id).where(
        RawArticle.ticker_links.any(ticker=ticker)
    )
    total = len((await session.execute(count_stmt)).all())

    stmt = stmt.order_by(desc(RawArticle.published_at)).limit(limit).offset(offset)
    rows = (await session.execute(stmt)).scalars().all()

    return {
        "items": [
            {
                "id": a.id,
                "source": a.source,
                "headline": a.headline,
                "summary": a.summary,
                "published_at": a.published_at.isoformat(),
                "sentiment": a.sentiment,
                "sentiment_score": float(a.sentiment_score) if a.sentiment_score else None,
                "url": a.url,
                "tickers": [tl.ticker for tl in a.ticker_links],
            }
            for a in rows
        ],
        "total": total,
    }
