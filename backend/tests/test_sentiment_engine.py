from datetime import datetime, timezone, timedelta
from backend.app.signals.sentiment_engine import generate_sentiment_signal


def test_future_date_clamped_to_zero():
    now = datetime.now(timezone.utc)
    articles = [
        {
            "published_at": now + timedelta(hours=5),
            "sentiment": "positive",
            "score": 0.9,
            "headline": "Future article",
            "url": "http://example.com/1",
        },
        {
            "published_at": now - timedelta(hours=1),
            "sentiment": "positive",
            "score": 0.8,
            "headline": "Recent article",
            "url": "http://example.com/2",
        },
    ]
    result = generate_sentiment_signal(articles, half_life_hours=48, min_articles=1)
    assert result.article_count == 2
    assert result.net_score > 0, "Should have positive net score"


def test_future_date_not_higher_weight_than_just_now():
    now = datetime.now(timezone.utc)
    articles_future = [
        {
            "published_at": now + timedelta(hours=10),
            "sentiment": "positive",
            "score": 1.0,
            "headline": "Future",
            "url": "http://example.com/f",
        },
    ]
    articles_now = [
        {
            "published_at": now,
            "sentiment": "positive",
            "score": 1.0,
            "headline": "Now",
            "url": "http://example.com/n",
        },
    ]
    result_future = generate_sentiment_signal(articles_future, half_life_hours=48, min_articles=1)
    result_now = generate_sentiment_signal(articles_now, half_life_hours=48, min_articles=1)
    assert result_future.confidence == result_now.confidence, \
        "Future-dated article weight should be clamped to same as 'just now'"
