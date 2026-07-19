"""
sentiment_engine.py — Pure sentiment signal generation.

Input: List of scored articles → Output: SentimentSignal (signal, confidence, details).
No I/O, no external deps. Fully testable.
"""
from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime, timezone
import numpy as np


@dataclass
class SentimentSignal:
    signal: str                 # 'buy' | 'sell' | 'hold'
    confidence: int             # 0-100
    article_count: int
    net_score: float            # -1 to 1
    positive_count: int
    negative_count: int
    neutral_count: int
    top_articles: List[dict]
    recency_weighted: bool = True


def generate_sentiment_signal(
    articles: List[dict],
    half_life_hours: float = 48.0,
    min_articles: int = 3,
) -> SentimentSignal:
    """
    articles: [{'sentiment': 'pos/neg/neu', 'score': 0.87, 'published_at': datetime, 'headline': '', 'url': ''}, ...]
    """
    if len(articles) < min_articles:
        return SentimentSignal('hold', 10, len(articles), 0.0, 0, 0, 0, [])

    now = datetime.now(timezone.utc)
    total_weight = 0.0
    weighted_sum = 0.0
    pos = neg = neu = 0

    for a in articles:
        hours_ago = (now - a['published_at']).total_seconds() / 3600
        weight = 2.0 ** (-hours_ago / half_life_hours)

        if a['sentiment'] == 'positive':
            weighted_sum += a['score'] * weight
            pos += 1
        elif a['sentiment'] == 'negative':
            weighted_sum -= a['score'] * weight
            neg += 1
        else:
            neu += 1
        total_weight += weight

    net = weighted_sum / total_weight if total_weight > 0 else 0.0

    # Volume confidence
    n = len(articles)
    if n >= 20:
        vol_factor = 1.0
    elif n >= 10:
        vol_factor = 0.8
    elif n >= 5:
        vol_factor = 0.6
    else:
        vol_factor = 0.4

    # Thresholds
    if net > 0.15:
        signal = 'buy'
    elif net < -0.15:
        signal = 'sell'
    else:
        signal = 'hold'

    base_conf = min(100, int(abs(net) * 100))
    confidence = int(base_conf * vol_factor)

    top = sorted(articles, key=lambda x: x['published_at'], reverse=True)[:5]
    top_articles = [{'headline': a['headline'], 'sentiment': a['sentiment'],
                     'score': a['score'], 'url': a.get('url'), 'published_at': a['published_at']} for a in top]

    return SentimentSignal(
        signal=signal,
        confidence=confidence,
        article_count=n,
        net_score=net,
        positive_count=pos,
        negative_count=neg,
        neutral_count=neu,
        top_articles=top_articles,
    )