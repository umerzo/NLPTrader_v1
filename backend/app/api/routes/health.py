from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.session import get_db

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
async def health_check():
    return {"status": "ok", "service": "nlptrader-api"}


@router.get("/health/db")
async def db_health(session: AsyncSession = Depends(get_db)):
    try:
        await session.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        return {"status": "error", "database": str(e)}


@router.get("/health/llm")
async def llm_health():
    from backend.app.llm.client import LLMClient
    client = LLMClient()
    try:
        await client.complete("ping", max_tokens=5)
        return {"status": "ok", "llm": "available"}
    except Exception as e:
        return {"status": "error", "llm": str(e)}
