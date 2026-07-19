"""
health.py — Health check endpoints.
"""
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.session import get_db
from backend.app.core.config import get_settings

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/")
async def health_check():
    return {"status": "ok", "service": "nlptrader-api"}


@router.get("/db")
async def db_health(session: AsyncSession = Depends(get_db)):
    try:
        await session.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        return {"status": "error", "database": str(e)}


@router.get("/llm")
async def llm_health():
    from backend.app.llm.client import LLMClient
    client = LLMClient()
    try:
        # Quick test call
        await client.complete("ping", max_tokens=5)
        return {"status": "ok", "llm": "available"}
    except Exception as e:
        return {"status": "error", "llm": str(e)}


@router.get("/chromadb")
async def chromadb_health():
    import chromadb
    from chromadb.config import Settings as ChromaSettings
    settings = get_settings()
    try:
        client = chromadb.PersistentClient(
            path=settings.CHROMA_PERSIST_DIR,
            settings=ChromaSettings(anonymized_telemetry=False)
        )
        client.heartbeat()
        return {"status": "ok", "chromadb": "connected"}
    except Exception as e:
        return {"status": "error", "chromadb": str(e)}


@router.get("/full")
async def full_health(
    session: AsyncSession = Depends(get_db),
):
    """Aggregate health check for load balancers."""
    from backend.app.core.config import get_settings
    settings = get_settings()
    checks = {}

    # DB
    try:
        await session.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {e}"

    # LLM
    from backend.app.llm.client import LLMClient
    try:
        client = LLMClient()
        await client.complete("ping", max_tokens=5)
        checks["llm"] = "ok"
    except Exception as e:
        checks["llm"] = f"error: {e}"

    # ChromaDB
    try:
        import chromadb
        from chromadb.config import Settings as ChromaSettings
        c = chromadb.PersistentClient(
            path=settings.CHROMA_PERSIST_DIR,
            settings=ChromaSettings(anonymized_telemetry=False)
        )
        c.heartbeat()
        checks["chromadb"] = "ok"
    except Exception as e:
        checks["chromadb"] = f"error: {e}"

    all_ok = all(v == "ok" for v in checks.values())
    return {"status": "ok" if all_ok else "degraded", "checks": checks}