from unittest.mock import AsyncMock, MagicMock, patch
import numpy as np
import pytest
from datetime import datetime, timezone, timedelta
from backend.app.signals.embedder import embed_text, retrieve_relevant_articles, _model


def reset_singleton():
    import backend.app.signals.embedder as emb
    emb._model = None


@pytest.mark.asyncio
async def test_singleton_embedder():
    reset_singleton()
    assert _model is None

    mock_model = MagicMock()
    mock_model.encode.return_value = np.array([0.1, 0.2, 0.3])

    with patch("sentence_transformers.SentenceTransformer", return_value=mock_model):
        result1 = embed_text("test text")
        assert len(result1) == 3
        assert isinstance(result1, list)
        assert result1[0] == 0.1

        from backend.app.signals.embedder import _model as m
        assert m is not None

        result2 = embed_text("more text")
        assert len(result2) == 3

    assert mock_model.encode.call_count == 2


@pytest.mark.asyncio
async def test_retrieve_relevant_articles():
    reset_singleton()

    mock_session = AsyncMock()
    fake_result = MagicMock()
    fake_result.all.return_value = [
        MagicMock(id=1, headline="Apple beats earnings", summary="Great quarter",
                  published_at=datetime.now(timezone.utc), sentiment="positive",
                  sentiment_score=0.95, event_type="EARNINGS", distance=0.1),
        MagicMock(id=2, headline="Apple stock rises", summary="Up 5%",
                  published_at=datetime.now(timezone.utc), sentiment="positive",
                  sentiment_score=0.80, event_type=None, distance=0.2),
        MagicMock(id=3, headline="Apple supplier news", summary="供应链 update",
                  published_at=datetime.now(timezone.utc), sentiment="neutral",
                  sentiment_score=0.50, event_type="OTHER", distance=0.3),
    ]
    mock_session.execute.return_value = fake_result

    mock_model = MagicMock()
    mock_model.encode.return_value = np.array([0.1] * 384)

    with patch("sentence_transformers.SentenceTransformer", return_value=mock_model):
        results = await retrieve_relevant_articles(
            mock_session, "AAPL", "earnings report", top_k=3, lookback_days=30
        )

    assert len(results) == 3
    assert results[0]["id"] == 1
    assert results[0]["distance"] < results[1]["distance"]
    assert results[1]["distance"] < results[2]["distance"]
    assert results[0]["sentiment"] == "positive"
