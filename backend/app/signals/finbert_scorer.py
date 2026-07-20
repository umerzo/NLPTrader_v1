import logging
from datetime import datetime, timezone
from typing import Optional
import asyncio

logger = logging.getLogger(__name__)

_pipeline: Optional[object] = None
_load_counter = 0

def _get_pipeline():
    global _pipeline, _load_counter
    if _pipeline is None:
        logger.info("Loading FinBERT pipeline (first call)")
        from transformers import pipeline
        _pipeline = pipeline(
            "sentiment-analysis",
            model="ProsusAI/finbert",
            truncation=True,
        )
        _load_counter += 1
    return _pipeline


async def score_articles(articles: list[dict]) -> list[dict]:
    if not articles:
        return []

    classifier = await asyncio.to_thread(_get_pipeline)
    texts = [
        (a.get("headline", "") + ". " + (a.get("summary", "") or "")).strip()[:1000]
        for a in articles
    ]

    try:
        results = await asyncio.to_thread(classifier, texts)
    except Exception as e:
        logger.error("FinBERT batch scoring failed for %d articles: %s", len(articles), e)
        for a in articles:
            aid = a.get("id") or a.get("source_id", "?")
            logger.warning("  failed article: id=%s source=%s", aid, a.get("source", "?"))
        return articles

    scored = []
    for article, result in zip(articles, results):
        label = result["label"].lower()
        score = float(result["score"])
        if label == "positive":
            sentiment = "positive"
        elif label == "negative":
            sentiment = "negative"
        else:
            sentiment = "neutral"
        scored.append({
            **article,
            "sentiment": sentiment,
            "sentiment_score": score,
            "sentiment_scored_at": datetime.now(timezone.utc),
        })

    return scored


def get_load_count() -> int:
    return _load_counter
