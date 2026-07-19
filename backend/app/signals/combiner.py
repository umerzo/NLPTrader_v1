"""
combiner.py — Ensemble signal combination logic.

Pure functions: SubSignal + SubSignal + SubSignal → CombinedSignal.
No I/O, fully testable.
"""
from dataclasses import dataclass
from typing import Optional, List
from datetime import datetime, timezone


@dataclass
class SubSignal:
    source: str           # 'ta' | 'sentiment' | 'fundamental'
    confidence: int       # 0-100
    signal: str           # 'buy' | 'sell' | 'hold'
    details: dict         # Engine-specific details


@dataclass
class CombinedSignal:
    signal: str                   # 'buy' | 'sell' | 'hold'
    confidence: int               # 0-100
    reasoning: str                # Human-readable synthesis
    regime: str                   # Market regime context
    prediction_horizon: str       # e.g., "24h"
    model_version: str            # e.g., "v1.0-ensemble"
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit_1: Optional[float] = None
    take_profit_2: Optional[float] = None
    take_profit_3: Optional[float] = None


class SignalCombiner:
    def __init__(self):
        self.weights = {
            'ta': 0.4,
            'sentiment': 0.3,
            'fundamental': 0.3,
        }
        self.conflict_penalty = 0.5

    def combine(
        self,
        ta: SubSignal,
        sentiment: SubSignal,
        fundamental: SubSignal,
        current_price: float,
        regime: str = 'unknown',
    ) -> CombinedSignal:
        """Main combination logic."""
        sub_signals = [ta, sentiment, fundamental]

        # 1. Vote counting
        signals = [s.signal for s in sub_signals]
        buy_votes = signals.count('buy')
        sell_votes = signals.count('sell')

        # 2. Determine base signal from agreement
        if buy_votes >= 2 and sell_votes == 0:
            base_signal = 'buy'
            agreement = buy_votes / 3
        elif sell_votes >= 2 and buy_votes == 0:
            base_signal = 'sell'
            agreement = sell_votes / 3
        else:
            base_signal = 'hold'
            agreement = 0.33

        # 3. Weighted confidence
        weighted_conf = sum(
            s.confidence * self.weights[s.source]
            for s in sub_signals
        ) * agreement

        # 4. Conflict penalty
        if buy_votes > 0 and sell_votes > 0:
            weighted_conf *= self.conflict_penalty

        # 5. Regime adjustment
        regime_mult = self._regime_multiplier(regime, base_signal)
        weighted_conf *= regime_mult

        confidence = max(5, min(95, int(weighted_conf)))

        # 6. Get levels from TA (only valid for directional signals)
        levels = ta.details.get('levels', {}) if ta.signal in ('buy', 'sell') else {}

        # 7. Synthesize reasoning
        reasoning = self._synthesize(sub_signals, base_signal, confidence, regime)

        return CombinedSignal(
            signal=base_signal,
            confidence=confidence,
            reasoning=reasoning,
            regime=regime,
            prediction_horizon="24h",
            model_version="v1.0-ensemble",
            entry_price=levels.get('entry'),
            stop_loss=levels.get('sl'),
            take_profit_1=levels.get('tp1'),
            take_profit_2=levels.get('tp2'),
            take_profit_3=levels.get('tp3'),
        )

    def _regime_multiplier(self, regime: str, signal: str) -> float:
        """Adjust confidence based on market regime."""
        if regime == 'bull' and signal == 'buy':
            return 1.1
        elif regime == 'bear' and signal == 'sell':
            return 1.1
        elif regime == 'bear' and signal == 'buy':
            return 0.7
        elif regime == 'high_vol':
            return 0.8
        elif regime == 'chop':
            return 0.9
        elif regime == 'crisis':
            return 0.5
        return 1.0

    def _synthesize(
        self,
        sub_signals: List[SubSignal],
        final_signal: str,
        confidence: int,
        regime: str,
    ) -> str:
        """Build human-readable reasoning."""
        parts = []

        # TA reasoning
        ta = next(s for s in sub_signals if s.source == 'ta')
        if ta.details.get('reasoning'):
            parts.append(f"Technical: {ta.details['reasoning']}")

        # Sentiment summary
        sent = next(s for s in sub_signals if s.source == 'sentiment')
        art_count = sent.details.get('article_count', 0)
        net = sent.details.get('net_score', 0)
        parts.append(f"Sentiment: {art_count} articles (net {net:+.2f})")

        # Fundamental narrative
        fund = next(s for s in sub_signals if s.source == 'fundamental')
        if fund.details.get('narrative'):
            parts.append(f"Fundamental: {fund.details['narrative']}")

        # Conflict note
        signals = [s.signal for s in sub_signals]
        if signals.count('buy') > 0 and signals.count('sell') > 0:
            parts.append("⚠️ Sub-signals conflict — confidence reduced")

        # Regime note
        if regime != 'unknown':
            parts.append(f"Regime: {regime}")

        return " | ".join(parts)