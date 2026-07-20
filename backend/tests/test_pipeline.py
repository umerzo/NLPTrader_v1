from unittest.mock import AsyncMock, patch
import pytest
from backend.app.ingestion.pipeline import IngestionPipeline


@pytest.mark.asyncio
async def test_run_single_ticker_calls_all_steps():
    session = AsyncMock()

    pipeline = IngestionPipeline(session)

    with patch.object(pipeline, "_fetch_single", return_value=[{"source": "test", "source_id": "1"}]) as mock_fetch:
        with patch.object(pipeline, "_dedup", return_value=[{"source": "test", "source_id": "1"}]) as mock_dedup:
            with patch.object(pipeline, "_persist") as mock_persist:
                with patch.object(pipeline, "_score_unscored") as mock_score:
                    with patch.object(pipeline, "_embed_new") as mock_embed:
                        with patch.object(pipeline, "_map_entities") as mock_map:

                            result = await pipeline.run_single_ticker("AAPL")

                            mock_fetch.assert_called_once()
                            mock_dedup.assert_called_once()
                            mock_persist.assert_called_once()
                            mock_score.assert_called_once()
                            mock_embed.assert_called_once()
                            mock_map.assert_called_once()

                            assert "fetched" in result
                            assert "new" in result
                            assert "scored" in result
                            assert "embedded" in result
                            assert "mapped" in result
                            assert "errors" in result


@pytest.mark.asyncio
async def test_run_single_ticker_uppercases():
    session = AsyncMock()
    pipeline = IngestionPipeline(session)

    with patch.object(pipeline, "_fetch_single", return_value=[]) as mock_fetch:
        with patch.object(pipeline, "_dedup", return_value=[]):
            with patch.object(pipeline, "_persist"):
                with patch.object(pipeline, "_score_unscored"):
                    with patch.object(pipeline, "_embed_new"):
                        with patch.object(pipeline, "_map_entities"):
                            await pipeline.run_single_ticker("aapl")
                            args, _ = mock_fetch.call_args
                            assert args[0] == "AAPL", "Ticker should be uppercased"
