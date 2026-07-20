import logging
from unittest.mock import patch, MagicMock
import pytest
import pandas as pd
from backend.app.ingestion.price_client import get_ohlcv, _cache


def make_mock_df():
    df = pd.DataFrame({
        "Open": [150.0],
        "High": [155.0],
        "Low": [149.0],
        "Close": [153.0],
        "Volume": [1000000],
    }, index=pd.DatetimeIndex([pd.Timestamp.now()]))
    return df


@pytest.fixture(autouse=True)
def clear_cache():
    _cache.clear()


def test_returns_cached_data_on_yfinance_failure(caplog):
    caplog.set_level(logging.WARNING)

    with patch("backend.app.ingestion.price_client.yf.Ticker") as mock_ticker:
        mock_ticker.return_value.history.return_value = make_mock_df()
        result_first = get_ohlcv("AAPL", "1d", 5)
        assert not result_first.empty

    with patch("backend.app.ingestion.price_client.yf.Ticker") as mock_ticker:
        mock_ticker.return_value.history.side_effect = Exception("API timeout")
        result_second = get_ohlcv("AAPL", "1d", 5)
        assert not result_second.empty
        assert "open" in result_second.columns
        assert result_second["open"].iloc[0] == 150.0

    assert "yfinance failed for AAPL" in caplog.text
    assert "Returning cached data for AAPL" in caplog.text


def test_returns_empty_df_on_first_failure(caplog):
    caplog.set_level(logging.WARNING)

    with patch("backend.app.ingestion.price_client.yf.Ticker") as mock_ticker:
        mock_ticker.return_value.history.side_effect = Exception("Network error")
        result = get_ohlcv("UNKNOWN", "1d", 5)
        assert result.empty
        assert list(result.columns) == ["timestamp", "open", "high", "low", "close", "volume"]

    assert "yfinance failed for UNKNOWN" in caplog.text
