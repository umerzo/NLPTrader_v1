"""Test that dedup query filters on exact (source, source_id) pairs."""
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from sqlalchemy import select, tuple_
from backend.app.ingestion.deduplicator import Deduplicator
from backend.app.db.models import RawArticle


@pytest.mark.asyncio
async def test_filter_new_uses_composite_key_query():
    session = AsyncMock()
    session.execute = AsyncMock()

    fake_execute = MagicMock()
    fake_execute.all.return_value = [("finnhub", "abc123")]
    session.execute.return_value = fake_execute

    dedup = Deduplicator(session)
    articles = [
        {"source": "finnhub", "source_id": "abc123", "headline": "exists"},
        {"source": "finnhub", "source_id": "def456", "headline": "new"},
        {"source": "reuters", "source_id": "xyz789", "headline": "also new"},
    ]

    result = await dedup.filter_new(articles)

    assert len(result) == 2
    assert result[0]["source_id"] == "def456"
    assert result[1]["source_id"] == "xyz789"

    call_stmt = session.execute.call_args[0][0]
    call_str = str(call_stmt.compile(compile_kwargs={"literal_binds": False}))

    assert "raw_articles.source, raw_articles.source_id" in call_str, \
        "Query must SELECT both source and source_id"
    assert "(raw_articles.source, raw_articles.source_id) IN" in call_str, \
        "Query must use composite (source, source_id) tuple IN filter, not just source"
