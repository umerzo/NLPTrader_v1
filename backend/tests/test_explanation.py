from unittest.mock import AsyncMock, patch
import pytest
from backend.app.llm.client import LLMClient
from backend.app.signals.explanation import generate_explanation


@pytest.mark.asyncio
async def test_returns_none_on_llm_failure():
    with patch.object(LLMClient, "complete", new_callable=AsyncMock) as mock_complete:
        mock_complete.side_effect = Exception("API down")

        result = await generate_explanation(
            signal="buy",
            confidence=75,
            ticker="AAPL",
            current_price=150.0,
            ta_signal="buy",
            ta_confidence=80,
            sentiment_signal="buy",
            sentiment_confidence=70,
            fundamental_signal="hold",
            fundamental_confidence=50,
        )

        assert result.explanation is None
        assert "buy" in result.raw_prompt
        assert "75" in result.raw_prompt


@pytest.mark.asyncio
async def test_prompt_contains_signal_and_confidence():
    with patch.object(LLMClient, "complete", new_callable=AsyncMock) as mock_complete:
        mock_complete.return_value = "This is the explanation."

        result = await generate_explanation(
            signal="sell",
            confidence=60,
            ticker="TSLA",
            current_price=200.0,
            ta_signal="sell",
            ta_confidence=50,
            sentiment_signal="hold",
            sentiment_confidence=40,
            fundamental_signal="sell",
            fundamental_confidence=70,
        )

        assert result.explanation == "This is the explanation."
        assert "SELL" in result.raw_prompt
        assert "60" in result.raw_prompt
        assert "TSLA" in result.raw_prompt
        assert result.model_used is not None
