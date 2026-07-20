from typing import Optional
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.session import get_db
from backend.app.db.repositories import OutcomeRepository

router = APIRouter(prefix="/api/outcomes", tags=["outcomes"])


@router.get("/summary")
async def get_outcomes_summary(
    ticker: Optional[str] = None,
    session: AsyncSession = Depends(get_db),
):
    """Live accuracy/win-rate stats for the dashboard."""
    repo = OutcomeRepository(session)
    return await repo.get_summary(ticker.upper() if ticker else None)
