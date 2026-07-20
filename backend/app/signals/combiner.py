import logging
from dataclasses import dataclass
from typing import Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


@dataclass
class SubSignal:
    source: str
    confidence: int
    signal: str
    details: dict


@dataclass
class CombinedSignal:
    signal: str
    confidence: int
    reasoning: str
    regime: str
    model_version: str
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit_1: Optional[float] = None
    take_profit_2: Optional[float] = None
    take_profit_3: Optional[float] = None
    conflict_penalty_applied: bool = False


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
        sub_signals = [ta, sentiment, fundamental]
        signals = [s.signal for s in sub_signals]
        buy_votes = signals.count('buy')
        sell_votes = signals.count('sell')

        base_signal, agreement_factor, conflict_penalty_applies = self._decision_table(buy_votes, sell_votes)

        weighted_conf = sum(s.confidence * self.weights[s.source] for s in sub_signals)
        weighted_conf *= agreement_factor
        if conflict_penalty_applies:
            weighted_conf *= self.conflict_penalty
        regime_mult = self._regime_multiplier(regime, base_signal)
        weighted_conf *= regime_mult
        confidence = max(5, min(95, int(weighted_conf)))

        levels = self._get_levels(ta, base_signal, current_price)

        reasoning = self._synthesize(sub_signals, base_signal, confidence, regime, buy_votes, sell_votes, conflict_penalty_applies)

        return CombinedSignal(
            signal=base_signal,
            confidence=confidence,
            reasoning=reasoning,
            regime=regime,
            model_version="v1",
            entry_price=levels.get('entry'),
            stop_loss=levels.get('sl'),
            take_profit_1=levels.get('tp1'),
            take_profit_2=levels.get('tp2'),
            take_profit_3=levels.get('tp3'),
            conflict_penalty_applied=conflict_penalty_applies,
        )

    def _decision_table(self, buy_votes: int, sell_votes: int) -> tuple:
        match (buy_votes, sell_votes):
            case (3, 0):
                return ('buy', 1.0, False)
            case (0, 3):
                return ('sell', 1.0, False)
            case (2, 0):
                return ('buy', 2/3, False)
            case (0, 2):
                return ('sell', 2/3, False)
            case (2, 1):
                return ('buy', 2/3, True)
            case (1, 2):
                return ('sell', 2/3, True)
            case _:
                return ('hold', 0.0, False)

    def _get_levels(self, ta: SubSignal, base_signal: str, current_price: float) -> dict:
        levels: dict = {'entry': None, 'sl': None, 'tp1': None, 'tp2': None, 'tp3': None}
        if base_signal not in ('buy', 'sell'):
            return levels
        if ta.signal != base_signal:
            logger.info("TA disagreed (%s) with final signal (%s) — omitting TA levels", ta.signal, base_signal)
            return levels

        ta_levels = ta.details.get('levels', {})
        entry = ta_levels.get('entry')
        sl = ta_levels.get('sl')
        if entry is None or sl is None:
            return levels

        if base_signal == 'buy' and sl >= entry:
            logger.warning("Buy setup has SL (%.2f) >= entry (%.2f) — omitting levels", sl, entry)
            return levels
        if base_signal == 'sell' and sl <= entry:
            logger.warning("Sell setup has SL (%.2f) <= entry (%.2f) — omitting levels", sl, entry)
            return levels

        return {
            'entry': entry,
            'sl': sl,
            'tp1': ta_levels.get('tp1'),
            'tp2': ta_levels.get('tp2'),
            'tp3': ta_levels.get('tp3'),
        }

    def _regime_multiplier(self, regime: str, signal: str) -> float:
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

    def _synthesize(self, sub_signals, final_signal, confidence, regime, buy_votes, sell_votes, conflict):
        parts = []
        ta = next(s for s in sub_signals if s.source == 'ta')
        if ta.details.get('reasoning'):
            parts.append(f"Technical: {ta.details['reasoning']}")
        sent = next(s for s in sub_signals if s.source == 'sentiment')
        art_count = sent.details.get('article_count', 0)
        net = sent.details.get('net_score', 0)
        parts.append(f"Sentiment: {art_count} articles (net {net:+.2f})")
        fund = next(s for s in sub_signals if s.source == 'fundamental')
        if fund.details.get('narrative'):
            parts.append(f"Fundamental: {fund.details['narrative']}")
        if buy_votes > 0 and sell_votes > 0:
            parts.append(f"Vote split: {buy_votes} buy / {sell_votes} sell — conflict penalty applied")
        if regime != 'unknown':
            parts.append(f"Regime: {regime}")
        return " | ".join(parts)
