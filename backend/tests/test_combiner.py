from backend.app.signals.combiner import SignalCombiner, SubSignal


def _sig(source, signal, conf=80, details=None):
    return SubSignal(source=source, signal=signal, confidence=conf, details=details or {})


def test_decision_table_all_rows():
    c = SignalCombiner()

    # 3 buy, 0 sell → buy, full agreement, no conflict
    r = c.combine(_sig("ta", "buy", 80), _sig("sentiment", "buy", 70), _sig("fundamental", "buy", 90), 100.0)
    assert r.signal == "buy", "3-0 should be buy"
    assert not r.conflict_penalty_applied

    # 0 buy, 3 sell → sell, full agreement, no conflict
    r = c.combine(_sig("ta", "sell", 80), _sig("sentiment", "sell", 70), _sig("fundamental", "sell", 90), 100.0)
    assert r.signal == "sell", "0-3 should be sell"
    assert not r.conflict_penalty_applied

    # 2 buy, 0 sell → buy, 2/3, no conflict
    r = c.combine(_sig("ta", "buy", 80), _sig("sentiment", "buy", 70), _sig("fundamental", "hold", 50), 100.0)
    assert r.signal == "buy", "2-0 should be buy"
    assert not r.conflict_penalty_applied

    # 0 buy, 2 sell → sell, 2/3, no conflict
    r = c.combine(_sig("ta", "sell", 80), _sig("sentiment", "sell", 70), _sig("fundamental", "hold", 50), 100.0)
    assert r.signal == "sell", "0-2 should be sell"
    assert not r.conflict_penalty_applied

    # 2 buy, 1 sell → buy, 2/3, conflict
    r = c.combine(_sig("ta", "buy", 80), _sig("sentiment", "buy", 70), _sig("fundamental", "sell", 90), 100.0)
    assert r.signal == "buy", "2-1 should be buy (majority)"
    assert r.conflict_penalty_applied

    # 1 buy, 2 sell → sell, 2/3, conflict
    r = c.combine(_sig("ta", "sell", 80), _sig("sentiment", "sell", 70), _sig("fundamental", "buy", 90), 100.0)
    assert r.signal == "sell", "1-2 should be sell (majority)"
    assert r.conflict_penalty_applied

    # 1 buy, 1 sell → hold
    r = c.combine(_sig("ta", "buy", 80), _sig("sentiment", "sell", 70), _sig("fundamental", "hold", 50), 100.0)
    assert r.signal == "hold", "1-1 should be hold"

    # 1 buy, 0 sell → hold (no majority)
    r = c.combine(_sig("ta", "buy", 80), _sig("sentiment", "hold", 50), _sig("fundamental", "hold", 50), 100.0)
    assert r.signal == "hold", "1-0 should be hold"

    # 0 buy, 1 sell → hold (no majority)
    r = c.combine(_sig("ta", "hold", 50), _sig("sentiment", "sell", 70), _sig("fundamental", "hold", 50), 100.0)
    assert r.signal == "hold", "0-1 should be hold"

    # 0 buy, 0 sell → hold
    r = c.combine(_sig("ta", "hold", 50), _sig("sentiment", "hold", 50), _sig("fundamental", "hold", 50), 100.0)
    assert r.signal == "hold", "0-0 should be hold"


def test_levels_never_leak_when_ta_disagrees():
    c = SignalCombiner()
    # TA says sell, sentiment+fundamental say buy → final= buy, TA levels must NOT appear
    r = c.combine(
        _sig("ta", "sell", 80, details={"levels": {"entry": 105, "sl": 110, "tp1": 95}}),
        _sig("sentiment", "buy", 70),
        _sig("fundamental", "buy", 90),
        current_price=100.0,
    )
    assert r.signal == "buy"
    assert r.entry_price is None, "TA sell levels must not leak into buy signal"
    assert r.stop_loss is None


def test_levels_attached_when_ta_agrees():
    c = SignalCombiner()
    r = c.combine(
        _sig("ta", "buy", 80, details={"levels": {"entry": 100, "sl": 95, "tp1": 110, "tp2": 115, "tp3": 120}}),
        _sig("sentiment", "buy", 70),
        _sig("fundamental", "buy", 90),
        current_price=100.0,
    )
    assert r.signal == "buy"
    assert r.entry_price == 100
    assert r.stop_loss == 95


def test_levels_omitted_on_hold():
    c = SignalCombiner()
    r = c.combine(
        _sig("ta", "buy", 80, details={"levels": {"entry": 100, "sl": 95, "tp1": 110}}),
        _sig("sentiment", "hold", 50),
        _sig("fundamental", "hold", 50),
        current_price=100.0,
    )
    assert r.signal == "hold"
    assert r.entry_price is None


def test_confidence_formula():
    c = SignalCombiner()
    r = c.combine(
        _sig("ta", "buy", 100),
        _sig("sentiment", "buy", 100),
        _sig("fundamental", "buy", 100),
        current_price=100.0,
    )
    # Full agreement: (100*0.4 + 100*0.3 + 100*0.3) * 1.0 = 100, *1.0 = 100, clamped to 95
    assert r.confidence == 95

    # Same with conflict penalty
    r = c.combine(
        _sig("ta", "buy", 100),
        _sig("sentiment", "buy", 100),
        _sig("fundamental", "sell", 100),
        current_price=100.0,
    )
    # (100*0.4 + 100*0.3 + 100*0.3) * 2/3 * 0.5 = 100 * 2/3 * 0.5 = 33.33
    assert r.confidence == 33
