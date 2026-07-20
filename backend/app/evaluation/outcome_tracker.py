import logging
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.models import Signal, Outcome
from backend.app.db.repositories import SignalRepository, OutcomeRepository
from backend.app.ingestion.price_client import get_ohlcv

logger = logging.getLogger(__name__)


async def evaluate_active_signals(session: AsyncSession) -> list[dict]:
    signal_repo = SignalRepository(session)
    outcome_repo = OutcomeRepository(session)

    active_signals = await signal_repo.get_active()
    results = []

    for signal in active_signals:
        try:
            result = await _evaluate_one(session, signal, signal_repo, outcome_repo)
            if result:
                results.append(result)
        except Exception as e:
            logger.error("Outcome evaluation failed for signal %d: %s", signal.id, e)

    return results


async def _evaluate_one(
    session: AsyncSession,
    signal: Signal,
    signal_repo: SignalRepository,
    outcome_repo: OutcomeRepository,
) -> Optional[dict]:
    if signal.signal not in ("buy", "sell"):
        await signal_repo.update_status(signal.id, "expired")
        await session.commit()
        return None

    price_df = get_ohlcv(signal.ticker, timeframe="1h", lookback=5)
    if price_df.empty:
        return None

    entry = float(signal.entry_price) if signal.entry_price else None
    if entry is None:
        await signal_repo.update_status(signal.id, "expired")
        await session.commit()
        return None

    sl = float(signal.stop_loss) if signal.stop_loss else None
    tp1 = float(signal.take_profit_1) if signal.take_profit_1 else None
    tp2 = float(signal.take_profit_2) if signal.take_profit_2 else None
    tp3 = float(signal.take_profit_3) if signal.take_profit_3 else None
    expires_at = signal.expires_at

    is_long = signal.signal == "buy"
    now = datetime.now(timezone.utc)

    # Chronological scan: iterate bars oldest-first
    for i in range(len(price_df)):
        high = float(price_df["high"].iloc[i])
        low = float(price_df["low"].iloc[i])
        close = float(price_df["close"].iloc[i])

        if is_long:
            barrier = _check_barriers_long(high, low, sl, tp1, tp2, tp3)
        else:
            barrier = _check_barriers_short(high, low, sl, tp1, tp2, tp3)

        if barrier:
            return await _record_outcome(
                session, signal_repo, outcome_repo, signal, barrier["price"], barrier["reason"]
            )

    # No barrier hit: check timeout
    latest_close = float(price_df["close"].iloc[-1])
    if expires_at and now >= expires_at:
        return await _record_outcome(
            session, signal_repo, outcome_repo, signal, latest_close, "timeout"
        )

    return None


def _check_barriers_long(
    high: float, low: float,
    sl: Optional[float], tp1: Optional[float], tp2: Optional[float], tp3: Optional[float],
) -> Optional[dict]:
    """Check barriers for a long position on a single bar. TP checked before SL within bar."""
    if tp1 and high >= tp1:
        return {"price": min(high, tp1), "reason": "tp1"}
    if tp2 and high >= tp2:
        return {"price": min(high, tp2), "reason": "tp2"}
    if tp3 and high >= tp3:
        return {"price": min(high, tp3), "reason": "tp3"}
    if sl and low <= sl:
        return {"price": max(low, sl), "reason": "sl"}
    return None


def _check_barriers_short(
    high: float, low: float,
    sl: Optional[float], tp1: Optional[float], tp2: Optional[float], tp3: Optional[float],
) -> Optional[dict]:
    """Check barriers for a short position on a single bar. TP checked before SL within bar."""
    if tp1 and low <= tp1:
        return {"price": max(low, tp1), "reason": "tp1"}
    if tp2 and low <= tp2:
        return {"price": max(low, tp2), "reason": "tp2"}
    if tp3 and low <= tp3:
        return {"price": max(low, tp3), "reason": "tp3"}
    if sl and high >= sl:
        return {"price": min(high, sl), "reason": "sl"}
    return None


async def _record_outcome(
    session: AsyncSession,
    signal_repo: SignalRepository,
    outcome_repo: OutcomeRepository,
    signal: Signal,
    exit_price: float,
    exit_reason: str,
) -> dict:
    entry = float(signal.entry_price) if signal.entry_price else exit_price
    return_pct = round((exit_price - entry) / entry * 100, 2) if entry else 0.0

    if signal.signal == "sell":
        return_pct = -return_pct

    if exit_reason == "timeout":
        outcome_label = "neutral"
    elif exit_reason in ("tp1", "tp2", "tp3"):
        outcome_label = "correct"
    else:
        outcome_label = "incorrect"

    outcome = Outcome(
        signal_id=signal.id,
        outcome=outcome_label,
        exit_price=exit_price,
        exit_reason=exit_reason,
        return_pct=abs(return_pct),
    )
    await outcome_repo.create(outcome)
    await signal_repo.update_status(signal.id, "expired")
    await session.commit()

    result = {
        "signal_id": signal.id,
        "ticker": signal.ticker,
        "outcome": outcome_label,
        "exit_reason": exit_reason,
        "exit_price": exit_price,
        "return_pct": abs(return_pct),
    }
    logger.info("Signal %d (%s): %s via %s (return %.2f%%)", signal.id, signal.ticker, outcome_label, exit_reason, abs(return_pct))
    return result
