from unittest.mock import patch, MagicMock
import pytest
from backend.app.signals.finbert_scorer import score_articles, get_load_count, _pipeline, _get_pipeline


def reset_singleton():
    import backend.app.signals.finbert_scorer as fs
    fs._pipeline = None
    fs._load_counter = 0


def test_get_pipeline_singleton():
    reset_singleton()
    assert _pipeline is None
    assert get_load_count() == 0

    with patch("transformers.pipeline") as mock_pipeline_fn:
        mock_instance = MagicMock()
        mock_pipeline_fn.return_value = mock_instance

        result1 = _get_pipeline()
        assert get_load_count() == 1
        assert result1 is mock_instance

        result2 = _get_pipeline()
        assert get_load_count() == 1
        assert result2 is result1

        mock_pipeline_fn.assert_called_once()


@pytest.mark.asyncio
async def test_batch_scoring():
    reset_singleton()

    mock_classifier = MagicMock()
    mock_classifier.return_value = [
        {"label": "positive", "score": 0.95},
        {"label": "negative", "score": 0.88},
    ]

    articles = [
        {"headline": "Great news for Apple", "summary": "", "source": "test", "source_id": "1"},
        {"headline": "Terrible quarter for Tesla", "summary": "", "source": "test", "source_id": "2"},
    ]

    with patch("transformers.pipeline", return_value=mock_classifier) as mock_pipe:
        result = await score_articles(articles)
        assert len(result) == 2
        assert result[0]["sentiment"] == "positive"
        assert result[1]["sentiment"] == "negative"
        mock_classifier.assert_called_once()


@pytest.mark.asyncio
async def test_handles_empty():
    reset_singleton()
    result = await score_articles([])
    assert result == []
