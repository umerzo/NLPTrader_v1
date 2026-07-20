import logging
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, text, Float
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

_model = None

def _get_embedder():
    global _model
    if _model is None:
        logger.info("Loading SentenceTransformer model (first call)")
        from sentence_transformers import SentenceTransformer
        from backend.app.core.config import settings
        _model = SentenceTransformer(settings.EMBEDDING_MODEL)
    return _model


def embed_text(text: str) -> list[float]:
    model = _get_embedder()
    return model.encode(text).tolist()


async def retrieve_relevant_articles(
    session: AsyncSession,
    ticker: str,
    query_text: str,
    top_k: int = 10,
    lookback_days: int = 7,
) -> list[dict]:
    from backend.app.db.models import RawArticle, ArticleTicker

    query_emb = embed_text(query_text)
    cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)
    emb_str = "[" + ",".join(f"{x:.8f}" for x in query_emb) + "]"

    sql = text("""
        SELECT ra.id, ra.headline, ra.summary, ra.published_at,
               ra.sentiment, ra.sentiment_score,
               at.event_type,
               ra.embedding <=> CAST(:query_emb AS vector) AS distance
        FROM raw_articles ra
        JOIN article_tickers at ON at.article_id = ra.id
        WHERE at.ticker = :ticker
          AND ra.published_at >= :cutoff
          AND ra.embedding IS NOT NULL
        ORDER BY distance ASC
        LIMIT :top_k
    """)

    result = await session.execute(
        sql,
        {
            "query_emb": emb_str,
            "ticker": ticker,
            "cutoff": cutoff,
            "top_k": top_k,
        },
    )
    rows = result.all()

    return [
        {
            "id": r.id,
            "headline": r.headline,
            "summary": r.summary,
            "published_at": r.published_at.isoformat() if hasattr(r.published_at, 'isoformat') else str(r.published_at),
            "sentiment": r.sentiment,
            "sentiment_score": float(r.sentiment_score) if r.sentiment_score else None,
            "event_type": r.event_type,
            "distance": float(r.distance),
        }
        for r in rows
    ]
