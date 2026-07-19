"""
news.py — FastAPI route for news/articles.
"""
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from sqlalchemy.orm import selectinload
import json
import asyncio

from backend.app.db.session import get_db
from backend.app.db.models import RawArticle
from backend.app.llm.client import LLMClient

router = APIRouter(prefix="/news", tags=["news"])


def _extract_llm_analysis(article: RawArticle) -> Optional[dict]:
    if article.raw_json and isinstance(article.raw_json, dict):
        return article.raw_json.get("llm_analysis")
    return None


@router.get("/articles")
async def get_articles(
    ticker: Optional[str] = None,
    limit: int = Query(50, le=200),
    offset: int = 0,
    session: AsyncSession = Depends(get_db),
):
    """Get news articles, optionally filtered by ticker."""
    count_stmt = select(RawArticle.id)
    if ticker:
        count_stmt = count_stmt.where(RawArticle.ticker == ticker.upper())
    total = len((await session.execute(count_stmt)).all())

    stmt = select(RawArticle)
    if ticker:
        stmt = stmt.where(RawArticle.ticker == ticker.upper())
    stmt = stmt.order_by(desc(RawArticle.published_at)).limit(limit).offset(offset)
    rows = (await session.execute(stmt)).scalars().all()

    return {
        "items": [
            {
                "id": a.id,
                "ticker": a.ticker,
                "source": a.source,
                "headline": a.headline,
                "summary": a.summary,
                "author": a.author,
                "published_at": a.published_at.isoformat(),
                "sentiment": a.sentiment,
                "sentiment_score": float(a.sentiment_score) if a.sentiment_score else None,
                "url": a.url,
                "llm_analysis": _extract_llm_analysis(a),
            }
            for a in rows
        ],
        "total": total,
    }


@router.post("/analyze-sentiment")
async def analyze_sentiment(
    limit: int = Query(20, le=100),
    session: AsyncSession = Depends(get_db),
):
    """Run LLM-based sentiment analysis on articles missing it.

    Scans for articles where raw_json->>'llm_analysis' is null,
    sends headline+summary to the LLM, and stores the result
    (label, confidence, reasoning) in raw_json['llm_analysis'].
    """
    llm = LLMClient()

    stmt = (
        select(RawArticle)
        .where(RawArticle.raw_json.is_(None) | ~RawArticle.raw_json.has_key("llm_analysis"))
        .order_by(desc(RawArticle.published_at))
        .limit(limit)
    )
    rows = (await session.execute(stmt)).scalars().all()

    results = []
    for article in rows:
        text = (article.headline or "") + ". " + (article.summary or "")
        text = text[:1500]
        if not text.strip():
            continue

        prompt = f"""Analyze the financial impact of this news article on the asset {article.ticker}. Classify as BULLISH, BEARISH, or NEUTRAL.

Article:
{text}

Return a JSON object with:
- "label": one of "BULLISH", "BEARISH", "NEUTRAL"
- "confidence": float between 0.0 and 1.0
- "reasoning": one sentence explaining the classification"""

        try:
            response = await llm.complete(
                prompt=prompt,
                system_prompt="You are a financial news analyst. Classify news sentiment for trading decisions.",
                temperature=0.2,
                max_tokens=200,
                response_format="json",
            )
            parsed = json.loads(response.strip())
            label = parsed.get("label", "NEUTRAL").upper()
            confidence = float(parsed.get("confidence", 0.5))
            reasoning = parsed.get("reasoning", "")

            # Validate label
            if label not in ("BULLISH", "BEARISH", "NEUTRAL"):
                label = "NEUTRAL"

            current = dict(article.raw_json) if article.raw_json and isinstance(article.raw_json, dict) else {}
            current["llm_analysis"] = {
                "label": label,
                "confidence": confidence,
                "reasoning": reasoning,
            }
            article.raw_json = current
            results.append({
                "id": article.id,
                "headline": article.headline[:80],
                "llm_analysis": article.raw_json["llm_analysis"],
            })
        except Exception as e:
            results.append({
                "id": article.id,
                "headline": article.headline[:80] if article.headline else "",
                "error": str(e),
            })

        # Small delay to avoid rate limiting
        await asyncio.sleep(0.5)

    await session.commit()

    return {
        "analyzed": len(results),
        "results": results,
    }
