"""
backtest_engine.py — Walk-forward backtesting engine.

Pure evaluation: no lookahead, reproducible, calibrated.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import List, Optional
import numpy as np
import pandas as pd

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.models import PriceOHLCV, RawArticle, Signal, BacktestRun
from backend.app.db.repositories import PriceRepository, ArticleRepository
from backend.app.signals.ta_engine import generate_ta_signal, TASignal
from backend.app.signals.sentiment_engine import generate_sentiment_signal, SentimentSignal
from backend.app.signals.fundamental_engine import FundamentalEngine, FundamentalSignal
from backend.app.signals.combiner import SignalCombiner, SubSignal
from backend.app.core.config import get_settings


@dataclass
class BacktestTrade:
    ticker: str
    signal_time: datetime
    horizon_hours: int
    signal: str
    confidence: int
    entry_price: float
    exit_price: float
    price_change_pct: float
    correct: bool
    max_favorable_pct: float
    max_adverse_pct: float
    hit_sl: bool
    hit_tp1: bool


@dataclass
class BacktestResult:
    total_signals: int
    accuracy: float
    profit_factor: float
    sharpe_ratio: float
    max_drawdown: float
    calibration: List[dict]
    by_ticker: dict
    by_horizon: dict
    by_signal_type: dict
    equity_curve: List[dict]
    trades: List[BacktestTrade]


class BacktestEngine:
    def __init__(self, session: AsyncSession, model_version: str):
        self.session = session
        self.model_version = model_version
        self.settings = get_settings()
        self.prices = PriceRepository(session)
        self.articles = ArticleRepository(session)
        self.fundamental = FundamentalEngine()
        self.combiner = SignalCombiner()

    async def run(self, config: dict) -> BacktestResult:
        """
        Walk-forward backtest:
        For each timestamp in range:
          1. Get price data UP TO that timestamp
          2. Get news UP TO that timestamp
          3. Generate signal
          4. Evaluate at each horizon
        """
        tickers = config.get("tickers", ["BTC", "ETH", "XAUUSD", "NVDA"])
        start = datetime.fromisoformat(config["start_date"]).replace(tzinfo=timezone.utc)
        end = datetime.fromisoformat(config["end_date"]).replace(tzinfo=timezone.utc)
        timeframe = config.get("timeframe", "1h")
        horizons = config.get("horizons", [4, 24, 48])
        step_hours = config.get("step_hours", 4)  # Signal frequency

        all_trades = []

        for ticker in tickers:
            # Load all price data for this ticker (once)
            price_bars = await self.prices.get_range(ticker, timeframe, start, end)
            if len(price_bars) < 100:
                continue

            # Load all articles for this ticker (once)
            all_articles = await self.articles.get_by_ticker_since(ticker, start, limit=5000)

            # Walk forward
            current = start + timedelta(hours=100)  # Warmup period
            while current <= end:
                # Get price data up to current
                historical_bars = [b for b in price_bars if b.timestamp <= current]
                if len(historical_bars) < 50:
                    current += timedelta(hours=step_hours)
                    continue

                # Get articles up to current
                historical_articles = [a for a in all_articles if a.published_at <= current]

                # Generate signal
                signal = await self._generate_historical_signal(
                    ticker, current, historical_bars, historical_articles
                )
                if not signal or signal.signal == 'hold':
                    current += timedelta(hours=step_hours)
                    continue

                # Evaluate at each horizon
                for horizon in horizons:
                    trade = await self._evaluate_trade(signal, price_bars, current, horizon)
                    if trade:
                        all_trades.append(trade)

                current += timedelta(hours=step_hours)

        return self._compute_metrics(all_trades)

    async def _generate_historical_signal(
        self,
        ticker: str,
        as_of: datetime,
        price_bars: List[PriceOHLCV],
        articles: List[RawArticle],
    ) -> Optional[Signal]:
        """Generate signal using only data available at `as_of`."""
        # Price arrays (chronological)
        closes = np.array([float(b.close) for b in price_bars], dtype=np.float64)
        highs = np.array([float(b.high) for b in price_bars], dtype=np.float64)
        lows = np.array([float(b.low) for b in price_bars], dtype=np.float64)
        opens = np.array([float(b.open) for b in price_bars], dtype=np.float64)
        volumes = np.array([float(b.volume) for b in price_bars], dtype=np.float64)

        # TA Signal
        ta_result: TASignal = generate_ta_signal(opens, highs, lows, closes, volumes)
        ta_sub = SubSignal('ta', ta_result.confidence, 'ta', {
            'reasoning': ta_result.reasoning,
            'levels': ta_result.levels,
        })

        # Sentiment Signal
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
        })

        # Fundamental Signal
        current_price = float(closes[-1])
        fund_result: FundamentalSignal = await self.fundamental.generate_signal(ticker, current_price)
        fund_sub = SubSignal('fundamental', fund_result.confidence, 'fundamental', {
            'narrative': fund_result.narrative,
            'key_themes': fund_result.key_themes,
            'risks': fund_result.risks,
        })

        # Combine
        combined = self.combiner.combine(ta_sub, sent_sub, fund_sub, current_price, ta_result.regime)

        # Build Signal-like object for evaluation
        class HistSignal:
            pass
        sig = HistSignal()
        sig.ticker = ticker
        sig.signal = combined.signal
        sig.confidence = combined.confidence
        sig.regime = combined.regime
        sig.current_price = current_price
        sig.entry_price = combined.entry_price
        sig.stop_loss = combined.stop_loss
        sig.take_profit_1 = combined.take_profit_1
        sig.generated_at = as_of
        return sig

    async def _evaluate_trade(
        self,
        signal,
        all_bars: List[PriceOHLCV],
        signal_time: datetime,
        horizon_hours: int,
    ) -> Optional[BacktestTrade]:
        target_time = signal_time + timedelta(hours=horizon_hours)

        future_bars = [b for b in all_bars if signal_time < b.timestamp <= target_time]
        if not future_bars:
            return None

        entry = signal.entry_price or signal.current_price
        exit_price = float(future_bars[-1].close)

        highs = [float(b.high) for b in future_bars]
        lows = [float(b.low) for b in future_bars]

        if signal.signal == 'buy':
            max_fav = (max(highs) - entry) / entry * 100
            max_adv = (entry - min(lows)) / entry * 100
            change = (exit_price - entry) / entry * 100
            correct = change >= 0.5
            hit_sl = signal.stop_loss and min(lows) <= signal.stop_loss
            hit_tp1 = signal.take_profit_1 and max(highs) >= signal.take_profit_1
        elif signal.signal == 'sell':
            max_fav = (entry - min(lows)) / entry * 100
            max_adv = (max(highs) - entry) / entry * 100
            change = (entry - exit_price) / entry * 100
            correct = change >= 0.5
            hit_sl = signal.stop_loss and max(highs) >= signal.stop_loss
            hit_tp1 = signal.take_profit_1 and min(lows) <= signal.take_profit_1
        else:
            return None

        return BacktestTrade(
            ticker=signal.ticker,
            signal_time=signal_time,
            horizon_hours=horizon_hours,
            signal=signal.signal,
            confidence=signal.confidence,
            entry_price=entry,
            exit_price=exit_price,
            price_change_pct=change,
            correct=correct,
            max_favorable_pct=max_fav,
            max_adverse_pct=max_adv,
            hit_sl=hit_sl,
            hit_tp1=hit_tp1,
        )

    def _compute_metrics(self, trades: List[BacktestTrade]) -> BacktestResult:
        if not trades:
            return BacktestResult(0, 0, 0, 0, 0, [], {}, {}, {}, [], [])

        df = pd.DataFrame([t.__dict__ for t in trades])

        total = int(len(df))
        accuracy = float(round(df['correct'].mean() * 100, 1))
        avg_return = float(df['price_change_pct'].mean())

        winners = float(df[df['price_change_pct'] > 0]['price_change_pct'].sum())
        losers = float(abs(df[df['price_change_pct'] <= 0]['price_change_pct'].sum()))
        profit_factor = round(winners / losers, 2) if losers > 0 else 999.99

        returns = df['price_change_pct'] * 0.02
        sharpe = float(round(returns.mean() / returns.std() * np.sqrt(252), 2)) if returns.std() > 0 else 0.0

        equity = (1 + returns).cumprod()
        running_max = equity.cummax()
        max_dd = float(round((equity / running_max - 1).min() * 100, 1))

        # Calibration
        df['conf_bucket'] = pd.cut(df['confidence'],
                                   bins=[0, 30, 50, 70, 85, 100],
                                   labels=['0-30', '30-50', '50-70', '70-85', '85-100'])
        calib = df.groupby('conf_bucket', observed=True).agg(
            count=('correct', 'size'),
            accuracy=('correct', 'mean'),
            avg_return=('price_change_pct', 'mean'),
        ).reset_index()
        calibration = [
            {"conf_bucket": str(r['conf_bucket']), "count": int(r['count']),
             "accuracy": float(round(r['accuracy'] * 100, 1)), "avg_return": float(r['avg_return'])}
            for _, r in calib.iterrows()
        ]

        by_ticker = {
            str(t): {"count": int(v['count']), "accuracy": float(round(v['accuracy'] * 100, 1)),
                     "avg_return": float(v['avg_return'])}
            for t, v in df.groupby('ticker').agg(
                count=('correct', 'size'),
                accuracy=('correct', 'mean'),
                avg_return=('price_change_pct', 'mean'),
            ).to_dict('index').items()
        }

        by_horizon = {
            int(h): {"count": int(v['count']), "accuracy": float(round(v['accuracy'] * 100, 1)),
                     "avg_return": float(v['avg_return'])}
            for h, v in df.groupby('horizon_hours').agg(
                count=('correct', 'size'),
                accuracy=('correct', 'mean'),
                avg_return=('price_change_pct', 'mean'),
            ).to_dict('index').items()
        }

        by_signal = {
            str(s): {"count": int(v['count']), "accuracy": float(round(v['accuracy'] * 100, 1)),
                     "avg_return": float(v['avg_return'])}
            for s, v in df.groupby('signal').agg(
                count=('correct', 'size'),
                accuracy=('correct', 'mean'),
                avg_return=('price_change_pct', 'mean'),
            ).to_dict('index').items()
        }

        equity_curve = [
            {"time": t.isoformat(), "equity": float(e)}
            for t, e in zip(df['signal_time'], equity)
        ]

        return BacktestResult(
            total_signals=total,
            accuracy=accuracy,
            profit_factor=profit_factor,
            sharpe_ratio=sharpe,
            max_drawdown=max_dd,
            calibration=calibration,
            by_ticker=by_ticker,
            by_horizon=by_horizon,
            by_signal_type=by_signal,
            equity_curve=equity_curve,
            trades=trades,
        )