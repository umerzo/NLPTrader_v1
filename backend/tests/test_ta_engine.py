from backend.app.signals.ta_engine import calculate_trade_setup


def test_buy_signal_returns_buy_setup():
    """When signal='buy', even if RSI suggests sell, return buy setup or None, never sell."""
    support = [100.0, 95.0, 90.0]
    resistance = [110.0, 115.0, 120.0]
    result = calculate_trade_setup('buy', 105.0, support, resistance, rsi=65)
    if result is not None:
        assert result["direction"] == "buy"
        assert result["entry"] == 105.0


def test_sell_signal_returns_sell_setup():
    """When signal='sell', even if RSI suggests buy, return sell setup or None, never buy."""
    support = [100.0, 95.0, 90.0]
    resistance = [110.0, 115.0, 120.0]
    result = calculate_trade_setup('sell', 105.0, support, resistance, rsi=35)
    if result is not None:
        assert result["direction"] == "sell"
        assert result["entry"] == 105.0


def test_hold_returns_none():
    result = calculate_trade_setup('hold', 105.0, [100.0], [110.0], rsi=50)
    assert result is None


def test_buy_gated_by_rsi_position():
    """Buy setup only when RSI < 45 and position < 0.4."""
    support = [100.0]
    resistance = [110.0]
    result = calculate_trade_setup('buy', 105.0, support, resistance, rsi=50)
    assert result is None, "RSI 50 is not < 45, should return None"

    result = calculate_trade_setup('buy', 106.0, support, resistance, rsi=40)
    assert result is None, "Position 0.6 is not < 0.4, should return None"


def test_sell_gated_by_rsi_position():
    """Sell setup only when RSI > 55 and position > 0.6."""
    support = [100.0]
    resistance = [110.0]
    result = calculate_trade_setup('sell', 105.0, support, resistance, rsi=50)
    assert result is None, "RSI 50 is not > 55, should return None"

    result = calculate_trade_setup('sell', 104.0, support, resistance, rsi=60)
    assert result is None, "Position 0.4 is not > 0.6, should return None"


def test_no_support_resistance_returns_none():
    result = calculate_trade_setup('buy', 105.0, [], [], rsi=40)
    assert result is None


def test_never_returns_wrong_direction():
    """Old logic would produce 'sell' with RSI > 55 & pos > 0.6,
    but input signal='buy' must never return a sell-direction setup."""
    support = [100.0]
    resistance = [110.0]
    result = calculate_trade_setup('buy', 106.0, support, resistance, rsi=60)
    assert result is None or result["direction"] == "buy"
    if result:
        assert result["direction"] == "buy"

    result = calculate_trade_setup('sell', 103.0, support, resistance, rsi=40)
    assert result is None or result["direction"] == "sell"
    if result:
        assert result["direction"] == "sell"
