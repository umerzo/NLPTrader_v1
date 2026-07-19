"""
deduplicator.py — Article deduplication.
"""
from typing import List, Dict, Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.db.models import RawArticle


class Deduplicator:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def filter_new(self, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove articles already in DB (by source + source_id)."""
        if not articles:
            return []

        # Check existing
        source_ids = [(a['source'], a['source_id']) for a in articles]
        stmt = select(RawArticle.source, RawArticle.source_id).where(
            RawArticle.source.in_([s[0] for s in source_ids])
        )
        result = await self.session.execute(stmt)
        existing = set(result.all())

        # Filter
        new_articles = []
        for a in articles:
            if (a['source'], a['source_id']) not in existing:
                new_articles.append(a)
        return new_articles