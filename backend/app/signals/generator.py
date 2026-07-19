"""
generator.py — Signal Generation Orchestrator.

Coordinates: Price fetch → TA → Sentiment → Fundamental → Combine → Persist.
Pure orchestration, no business logic in this file.
"""
from datetime import datetime, timezone, timedelta
from typing import Optional
import numpy as np
from sqlalchemy import select

from backend.app.db.session import get_db
from backend.app.db.models import RawArticle, Signal as SignalModel
from backend.app.db.repositories import ArticleRepository, PriceRepository, SignalRepository
from backend.app.signals.ta_engine import generate_ta_signal, TASignal
from backend.app.signals.sentiment_engine import generate_sentiment_signal, SentimentSignal
from backend.app.signals.fundamental_engine import FundamentalEngine, FundamentalSignal
from backend.app.signals.combiner import SignalCombiner, SubSignal
from backend.app.core.config import get_settings


class SignalGenerator:
    def __init__(self, session):
        self.session = session
        self.articles = ArticleRepository(session)
        self.prices = PriceRepository(session)
        self.signals = SignalRepository(session)
        self.settings = get_settings()
        self.fundamental = FundamentalEngine()
        self.combiner = SignalCombiner()

    async def generate_for_ticker(self, ticker: str) -> Optional[SignalModel]:
        """Full pipeline for one ticker."""
        # 1. Fetch price data (1h timeframe for TA)
        price_bars = await self.prices.get_latest(ticker, "1h", limit=200)
        if len(price_bars) < 50:
            return None

        # Convert to numpy arrays (chronological: oldest first)
        opens = np.array([float(b.open) for b in reversed(price_bars)], dtype=np.float64)
        highs = np.array([float(b.high) for b in reversed(price_bars)], dtype=np.float64)
        lows = np.array([float(b.low) for b in reversed(price_bars)], dtype=np.float64)
        closes = np.array([float(b.close) for b in reversed(price_bars)], dtype=np.float64)
        volumes = np.array([float(b.volume) for b in reversed(price_bars)], dtype=np.float64)
        current_price = float(closes[-1])

        # 2. Generate sub-signals
        ta_result: TASignal = generate_ta_signal(opens, highs, lows, closes, volumes)
        ta_sub = SubSignal('ta', ta_result.confidence, 'ta', {
            'reasoning': ta_result.reasoning,
            'levels': ta_result.levels,
            'indicators': ta_result.indicators,
        })

        # Sentiment: fetch scored articles from last 7 days
        since = datetime.now(timezone.utc) - timedelta(days=7)
        articles = await self.articles.get_by_ticker_since(ticker, since, limit=200)
        scored_articles = [
            {'sentiment': a.sentiment, 'score': float(a.sentiment_score or 0),
             'published_at': a.published_at, 'headline': a.headline, 'url': a.url}
            for a in articles if a.sentiment
        ]
        sent_result: SentimentSignal = generate_sentiment_signal(
            scored_articles,
            half_life_hours=self.settings.SENTIMENT_HALF_LIFE_HOURS,
            min_articles=self.settings.MIN_ARTICLES_FOR_SENTIMENT,
        )
        sent_sub = SubSignal('sentiment', sent_result.confidence, 'sentiment', {
            'article_count': sent_result.article_count,
            'net_score': sent_result.net_score,
            'positive_count': sent_result.positive_count,
            'negative_count': sent_result.negative_count,
        })

        # Fundamental (RAG + LLM)
        fund_result: FundamentalSignal = await self.fundamental.generate_signal(ticker, current_price)
        fund_sub = SubSignal('fundamental', fund_result.confidence, 'fundamental', {
            'narrative': fund_result.narrative,
            'key_themes': fund_result.key_themes,
            'risks': fund_result.risks,
            'catalyst': fund_result.catalyst,
        })

        # 3. Combine
        combined = self.combiner.combine(
            ta_sub, sent_sub, fund_sub,
            current_price=current_price,
            regime=ta_result.regime,
        )

        # 4. Persist
        signal_row = SignalModel(
            ticker=ticker,
            model_version=combined.model_version,
            ta_signal=ta_result.signal,
            ta_confidence=ta_result.confidence,
            ta_details=ta_sub.details,
            sentiment_signal=sent_result.signal,
            sentiment_confidence=sent_result.confidence,
            sentiment_details=sent_sub.details,
            fundamental_signal=fund_result.signal,
            fundamental_confidence=fund_result.confidence,
            fundamental_details=fund_sub.details,
            combined_signal=combined.signal,
            combined_confidence=combined.confidence,
            combined_reasoning=combined.reasoning,
            prediction_horizon=combined.prediction_horizon,
            entry_price=combined.entry_price,
            stop_loss=combined.stop_loss,
            take_profit_1=combined.take_profit_1,
            take_profit_2=combined.take_profit_2,
            take_profit_3=combined.take_profit_3,
            regime=combined.regime,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=self.settings.PREDICTION_HORIZON_HOURS),
        )
        self.session.add(signal_row)
        await self.session.flush()
        return signal_row