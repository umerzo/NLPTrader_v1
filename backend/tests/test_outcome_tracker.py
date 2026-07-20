import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch, MagicMock
from decimal import Decimal

from backend.app.evaluation.outcome_tracker import evaluate_active_signals, _check_barriers_long, _check_barriers_short
from backend.app.db.models import Signal


def _make_df(opens, highs, lows, closes):
    """Build a mock DataFrame with given price arrays."""
    import pandas as pd
    df = pd.DataFrame({
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes,
    })
    return df


@pytest.fixture
def mock_session():
    return AsyncMock()


@pytest.fixture
def active_buy_signal():
    now = datetime.now(timezone.utc)
    return Signal(
        id=1, ticker="AAPL", signal="buy", confidence=70,
        entry_price=Decimal("150.00"), stop_loss=Decimal("145.00"),
        take_profit_1=Decimal("155.00"), take_profit_2=Decimal("160.00"), take_profit_3=Decimal("170.00"),
        expires_at=now + timedelta(hours=48), status="active",
    )


@pytest.fixture
def active_sell_signal():
    now = datetime.now(timezone.utc)
    return Signal(
        id=2, ticker="TSLA", signal="sell", confidence=65,
        entry_price=Decimal("200.00"), stop_loss=Decimal("210.00"),
        take_profit_1=Decimal("190.00"), take_profit_2=Decimal("180.00"), take_profit_3=Decimal("170.00"),
        expires_at=now + timedelta(hours=48), status="active",
    )


# --- Unit tests for barrier helpers ---

def test_barriers_long_tp1_hit():
    result = _check_barriers_long(high=156.0, low=149.0, sl=145.0, tp1=155.0, tp2=160.0, tp3=170.0)
    assert result is not None
    assert result["reason"] == "tp1"


def test_barriers_long_sl_hit():
    result = _check_barriers_long(high=151.0, low=144.0, sl=145.0, tp1=155.0, tp2=160.0, tp3=170.0)
    assert result is not None
    assert result["reason"] == "sl"


def test_barriers_long_tp_before_sl_same_bar():
    """Within a single bar, TP takes priority over SL."""
    result = _check_barriers_long(high=156.0, low=144.0, sl=145.0, tp1=155.0, tp2=160.0, tp3=170.0)
    assert result is not None
    assert result["reason"] == "tp1"


def test_barriers_long_no_hit():
    result = _check_barriers_long(high=152.0, low=148.0, sl=145.0, tp1=155.0, tp2=160.0, tp3=170.0)
    assert result is None


def test_barriers_short_tp1_hit():
    result = _check_barriers_short(high=205.0, low=188.0, sl=210.0, tp1=190.0, tp2=180.0, tp3=170.0)
    assert result is not None
    assert result["reason"] == "tp1"


def test_barriers_short_sl_hit():
    result = _check_barriers_short(high=212.0, low=198.0, sl=210.0, tp1=190.0, tp2=180.0, tp3=170.0)
    assert result is not None
    assert result["reason"] == "sl"


def test_barriers_short_tp_before_sl_same_bar():
    result = _check_barriers_short(high=212.0, low=188.0, sl=210.0, tp1=190.0, tp2=180.0, tp3=170.0)
    assert result is not None
    assert result["reason"] == "tp1"


def test_barriers_short_no_hit():
    result = _check_barriers_short(high=205.0, low=195.0, sl=210.0, tp1=190.0, tp2=180.0, tp3=170.0)
    assert result is None


# --- Integration tests for evaluate_active_signals ---

@pytest.mark.asyncio
async def test_evaluate_active_empty(mock_session):
    with patch("backend.app.evaluation.outcome_tracker.SignalRepository") as mock_signal_repo_cls, \
         patch("backend.app.evaluation.outcome_tracker.OutcomeRepository") as mock_outcome_repo_cls:
        mock_signal_repo = AsyncMock()
        mock_signal_repo.get_active = AsyncMock(return_value=[])
        mock_signal_repo_cls.return_value = mock_signal_repo
        mock_outcome_repo_cls.return_value = AsyncMock()
        results = await evaluate_active_signals(mock_session)
        assert results == []


@pytest.mark.asyncio
async def test_hold_signal_expired_immediately(mock_session):
    hold = Signal(id=3, ticker="MSFT", signal="hold", confidence=50, expires_at=datetime.now(timezone.utc) + timedelta(hours=24), status="active")
    with patch("backend.app.evaluation.outcome_tracker.SignalRepository") as mock_signal_repo_cls, \
         patch("backend.app.evaluation.outcome_tracker.OutcomeRepository") as mock_outcome_repo_cls:
        mock_signal_repo = AsyncMock()
        mock_signal_repo.get_active = AsyncMock(return_value=[hold])
        mock_signal_repo_cls.return_value = mock_signal_repo
        mock_outcome_repo_cls.return_value = AsyncMock()
        results = await evaluate_active_signals(mock_session)
        assert results == []
        mock_signal_repo.update_status.assert_called_once_with(3, "expired")


@pytest.mark.asyncio
async def test_no_entry_price_expires(mock_session):
    s = Signal(id=4, ticker="GOOG", signal="buy", confidence=60, expires_at=datetime.now(timezone.utc) + timedelta(hours=24), entry_price=None, status="active")
    with patch("backend.app.evaluation.outcome_tracker.SignalRepository") as mock_signal_repo_cls, \
         patch("backend.app.evaluation.outcome_tracker.OutcomeRepository") as mock_outcome_repo_cls:
        mock_signal_repo = AsyncMock()
        mock_signal_repo.get_active = AsyncMock(return_value=[s])
        mock_signal_repo_cls.return_value = mock_signal_repo
        mock_outcome_repo_cls.return_value = AsyncMock()
        results = await evaluate_active_signals(mock_session)
        assert results == []
        mock_signal_repo.update_status.assert_called_once_with(4, "expired")


@pytest.mark.asyncio
async def test_buy_hit_stop_loss(mock_session, active_buy_signal):
    """Price sequence crosses SL: low drops to 144 (<145 SL)."""
    df = _make_df(
        opens=[151, 150, 149, 148, 147],
        highs=[152, 151, 150, 149, 148],
        lows=[150, 149, 148, 147, 144],
        closes=[151, 150, 149, 148, 145],
    )
    with patch("backend.app.evaluation.outcome_tracker.get_ohlcv") as mock_get_ohlcv, \
         patch("backend.app.evaluation.outcome_tracker.SignalRepository") as mock_signal_repo_cls, \
         patch("backend.app.evaluation.outcome_tracker.OutcomeRepository") as mock_outcome_repo_cls:
        mock_get_ohlcv.return_value = df
        mock_signal_repo = AsyncMock()
        mock_signal_repo.get_active = AsyncMock(return_value=[active_buy_signal])
        mock_signal_repo_cls.return_value = mock_signal_repo
        mock_outcome_repo_cls.return_value = AsyncMock()
        results = await evaluate_active_signals(mock_session)
        assert len(results) == 1
        assert results[0]["outcome"] == "incorrect"
        assert results[0]["exit_reason"] == "sl"


@pytest.mark.asyncio
async def test_buy_hit_tp1(mock_session, active_buy_signal):
    """Price sequence hits TP1: high reaches 156 (>155 TP1)."""
    df = _make_df(
        opens=[151, 152, 153, 154, 155],
        highs=[152, 153, 154, 155, 156],
        lows=[150, 151, 152, 153, 154],
        closes=[151, 152, 153, 154, 155],
    )
    with patch("backend.app.evaluation.outcome_tracker.get_ohlcv") as mock_get_ohlcv, \
         patch("backend.app.evaluation.outcome_tracker.SignalRepository") as mock_signal_repo_cls, \
         patch("backend.app.evaluation.outcome_tracker.OutcomeRepository") as mock_outcome_repo_cls:
        mock_get_ohlcv.return_value = df
        mock_signal_repo = AsyncMock()
        mock_signal_repo.get_active = AsyncMock(return_value=[active_buy_signal])
        mock_signal_repo_cls.return_value = mock_signal_repo
        mock_outcome_repo_cls.return_value = AsyncMock()
        results = await evaluate_active_signals(mock_session)
        assert len(results) == 1
        assert results[0]["outcome"] == "correct"
        assert results[0]["exit_reason"] == "tp1"


@pytest.mark.asyncio
async def test_sell_hit_tp1(mock_session, active_sell_signal):
    """Short: price drops to 188 (<190 TP1)."""
    df = _make_df(
        opens=[198, 196, 194, 192, 190],
        highs=[200, 198, 196, 194, 192],
        lows=[197, 195, 193, 191, 188],
        closes=[198, 196, 194, 192, 190],
    )
    with patch("backend.app.evaluation.outcome_tracker.get_ohlcv") as mock_get_ohlcv, \
         patch("backend.app.evaluation.outcome_tracker.SignalRepository") as mock_signal_repo_cls, \
         patch("backend.app.evaluation.outcome_tracker.OutcomeRepository") as mock_outcome_repo_cls:
        mock_get_ohlcv.return_value = df
        mock_signal_repo = AsyncMock()
        mock_signal_repo.get_active = AsyncMock(return_value=[active_sell_signal])
        mock_signal_repo_cls.return_value = mock_signal_repo
        mock_outcome_repo_cls.return_value = AsyncMock()
        results = await evaluate_active_signals(mock_session)
        assert len(results) == 1
        assert results[0]["outcome"] == "correct"
        assert results[0]["exit_reason"] == "tp1"


@pytest.mark.asyncio
async def test_sell_hit_sl(mock_session, active_sell_signal):
    """Short: price rises to 212 (>210 SL)."""
    df = _make_df(
        opens=[202, 204, 206, 208, 210],
        highs=[204, 206, 208, 210, 212],
        lows=[200, 202, 204, 206, 208],
        closes=[202, 204, 206, 208, 210],
    )
    with patch("backend.app.evaluation.outcome_tracker.get_ohlcv") as mock_get_ohlcv, \
         patch("backend.app.evaluation.outcome_tracker.SignalRepository") as mock_signal_repo_cls, \
         patch("backend.app.evaluation.outcome_tracker.OutcomeRepository") as mock_outcome_repo_cls:
        mock_get_ohlcv.return_value = df
        mock_signal_repo = AsyncMock()
        mock_signal_repo.get_active = AsyncMock(return_value=[active_sell_signal])
        mock_signal_repo_cls.return_value = mock_signal_repo
        mock_outcome_repo_cls.return_value = AsyncMock()
        results = await evaluate_active_signals(mock_session)
        assert len(results) == 1
        assert results[0]["outcome"] == "incorrect"
        assert results[0]["exit_reason"] == "sl"


@pytest.mark.asyncio
async def test_timeout_no_barrier_hit(mock_session):
    """Expired signal with no barrier hit -> neutral/timeout."""
    now = datetime.now(timezone.utc)
    expired = Signal(
        id=5, ticker="NVDA", signal="buy", confidence=75,
        entry_price=Decimal("100.00"), stop_loss=Decimal("90.00"),
        take_profit_1=Decimal("110.00"),
        expires_at=now - timedelta(hours=1), status="active",
    )
    df = _make_df(
        opens=[101, 102, 103, 102, 101],
        highs=[102, 103, 104, 103, 102],
        lows=[100, 101, 102, 101, 100],
        closes=[101, 102, 103, 102, 101],
    )
    with patch("backend.app.evaluation.outcome_tracker.get_ohlcv") as mock_get_ohlcv, \
         patch("backend.app.evaluation.outcome_tracker.SignalRepository") as mock_signal_repo_cls, \
         patch("backend.app.evaluation.outcome_tracker.OutcomeRepository") as mock_outcome_repo_cls:
        mock_get_ohlcv.return_value = df
        mock_signal_repo = AsyncMock()
        mock_signal_repo.get_active = AsyncMock(return_value=[expired])
        mock_signal_repo_cls.return_value = mock_signal_repo
        mock_outcome_repo = AsyncMock()
        mock_outcome_repo.create = AsyncMock()
        mock_outcome_repo_cls.return_value = mock_outcome_repo
        results = await evaluate_active_signals(mock_session)
        assert len(results) == 1
        assert results[0]["outcome"] == "neutral"
        assert results[0]["exit_reason"] == "timeout"


@pytest.mark.asyncio
async def test_tp1_before_sl_chronologically(mock_session):
    """Price hits TP1 in bar 2, then SL in bar 4 — tracker must report TP1 (hit first).

    Signal: entry=150, TP1=155, SL=145
    Bar 1: H=152 L=149 (no hit)
    Bar 2: H=156 (>155 TP1!), L=150 — TP1 hit
    Bar 3: H=155 L=148
    Bar 4: H=149 L=144 (<145 SL!) — SL hit, but TP1 already won
    """
    now = datetime.now(timezone.utc)
    signal = Signal(
        id=6, ticker="AAPL", signal="buy", confidence=70,
        entry_price=Decimal("150.00"), stop_loss=Decimal("145.00"),
        take_profit_1=Decimal("155.00"),
        expires_at=now + timedelta(hours=48), status="active",
    )
    df = _make_df(
        opens=[150, 151, 153, 148],
        highs=[152, 156, 155, 149],
        lows=[149, 150, 148, 144],
        closes=[151, 155, 149, 145],
    )
    with patch("backend.app.evaluation.outcome_tracker.get_ohlcv") as mock_get_ohlcv, \
         patch("backend.app.evaluation.outcome_tracker.SignalRepository") as mock_signal_repo_cls, \
         patch("backend.app.evaluation.outcome_tracker.OutcomeRepository") as mock_outcome_repo_cls:
        mock_get_ohlcv.return_value = df
        mock_signal_repo = AsyncMock()
        mock_signal_repo.get_active = AsyncMock(return_value=[signal])
        mock_signal_repo_cls.return_value = mock_signal_repo
        mock_outcome_repo_cls.return_value = AsyncMock()
        results = await evaluate_active_signals(mock_session)
        assert len(results) == 1
        assert results[0]["exit_reason"] == "tp1", f"Expected tp1 but got {results[0]['exit_reason']}"
        assert results[0]["outcome"] == "correct"


@pytest.mark.asyncio
async def test_sl_before_tp1_chronologically(mock_session):
    """Price hits SL in bar 2, then TP1 in bar 4 — must report SL.

    Signal: entry=150, TP1=155, SL=145
    Bar 1: H=152 L=149 (no hit)
    Bar 2: H=151 L=144 (<145 SL!) — SL hit
    Bar 3: H=154 L=145
    Bar 4: H=156 (>155 TP1!) — TP1 would be hit but SL already won
    """
    now = datetime.now(timezone.utc)
    signal = Signal(
        id=7, ticker="AAPL", signal="buy", confidence=70,
        entry_price=Decimal("150.00"), stop_loss=Decimal("145.00"),
        take_profit_1=Decimal("155.00"),
        expires_at=now + timedelta(hours=48), status="active",
    )
    df = _make_df(
        opens=[150, 149, 147, 152],
        highs=[152, 151, 154, 156],
        lows=[149, 144, 145, 150],
        closes=[151, 148, 150, 155],
    )
    with patch("backend.app.evaluation.outcome_tracker.get_ohlcv") as mock_get_ohlcv, \
         patch("backend.app.evaluation.outcome_tracker.SignalRepository") as mock_signal_repo_cls, \
         patch("backend.app.evaluation.outcome_tracker.OutcomeRepository") as mock_outcome_repo_cls:
        mock_get_ohlcv.return_value = df
        mock_signal_repo = AsyncMock()
        mock_signal_repo.get_active = AsyncMock(return_value=[signal])
        mock_signal_repo_cls.return_value = mock_signal_repo
        mock_outcome_repo_cls.return_value = AsyncMock()
        results = await evaluate_active_signals(mock_session)
        assert len(results) == 1
        assert results[0]["exit_reason"] == "sl", f"Expected sl but got {results[0]['exit_reason']}"
        assert results[0]["outcome"] == "incorrect"
