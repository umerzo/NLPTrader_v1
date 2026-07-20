from typing import Any
from sqlalchemy import select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.db.models import RawArticle


class Deduplicator:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def filter_new(self, articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not articles:
            return []

        pairs = [(a["source"], a["source_id"]) for a in articles]
        stmt = select(RawArticle.source, RawArticle.source_id).where(
            tuple_(RawArticle.source, RawArticle.source_id).in_(pairs)
        )
        result = await self.session.execute(stmt)
        existing = set(result.all())

        return [a for a in articles if (a["source"], a["source_id"]) not in existing]
