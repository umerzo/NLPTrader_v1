"""
backtest.py — Backtest API routes.
"""
import asyncio
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from backend.app.db.session import get_db

router = APIRouter(prefix="/backtest", tags=["backtest"])


class BacktestConfig(BaseModel):
    tickers: List[str] = ["BTC", "ETH", "XAUUSD", "NVDA"]
    start_date: str  # ISO format
    end_date: str
    timeframe: str = "1h"
    horizons: List[int] = [4, 24, 48]
    model_version: Optional[str] = None


class BacktestRunResponse(BaseModel):
    run_id: int
    status: str
    message: str


# In-memory job tracking (replace with Redis/DB in production)
BACKTEST_JOBS = {}


@router.post("/run", response_model=BacktestRunResponse)
async def run_backtest(
    config: BacktestConfig,
    session: AsyncSession = Depends(get_db),
):
    """Start a backtest run in background."""
    from backend.app.evaluation.backtest_engine import BacktestEngine
    from backend.app.db.models import BacktestRun
    from backend.app.db.repositories import ModelVersionRepository

    # Validate model version
    if config.model_version:
        mv_repo = ModelVersionRepository(session)
        mv = await mv_repo.get_by_version(config.model_version)
        if not mv:
            raise HTTPException(404, f"Model version {config.model_version} not found")
    else:
        mv_repo = ModelVersionRepository(session)
        mv = await mv_repo.get_active()
        if not mv:
            raise HTTPException(400, "No active model version found")

    # Create run record
    run = BacktestRun(
        model_version=mv.version,
        config=config.model_dump(),
        status="running",
    )
    session.add(run)
    await session.flush()

    run_id = run.id
    BACKTEST_JOBS[run_id] = {"status": "running", "progress": 0}

    # Run in background (async task, not BackgroundTasks — that doesn't support coroutines)
    asyncio.create_task(_run_backtest_task(run_id, config, mv.version))

    return BacktestRunResponse(run_id=run_id, status="running", message="Backtest started")


async def _run_backtest_task(run_id: int, config: BacktestConfig, model_version: str):
    """Background task for backtest."""
    from dataclasses import asdict
    from backend.app.evaluation.backtest_engine import BacktestEngine
    from backend.app.db.session import async_session_maker
    from backend.app.db.models import BacktestRun

    async with async_session_maker() as session:
        try:
            engine = BacktestEngine(session, model_version)
            result = await engine.run(config.model_dump())

            # Update run record
            await session.execute(
                BacktestRun.__table__.update()
                .where(BacktestRun.id == run_id)
                .values(
                    completed_at=datetime.now(),
                    metrics=asdict(result),
                    status="completed",
                )
            )
            await session.commit()
            BACKTEST_JOBS[run_id] = {"status": "completed", "result": asdict(result)}

        except Exception as e:
            await session.execute(
                BacktestRun.__table__.update()
                .where(BacktestRun.id == run_id)
                .values(status="failed", metrics={"error": str(e)})
            )
            await session.commit()
            BACKTEST_JOBS[run_id] = {"status": "failed", "error": str(e)}


@router.get("/runs")
async def list_backtest_runs(
    session: AsyncSession = Depends(get_db),
):
    """List all backtest runs."""
    from sqlalchemy import select, desc
    from backend.app.db.models import BacktestRun
    stmt = select(BacktestRun).order_by(desc(BacktestRun.started_at)).limit(50)
    result = await session.execute(stmt)
    runs = result.scalars().all()
    return [
        {
            "id": r.id,
            "model_version": r.model_version,
            "started_at": r.started_at.isoformat(),
            "completed_at": r.completed_at.isoformat() if r.completed_at else None,
            "status": r.status,
            "config": r.config,
        }
        for r in runs
    ]


@router.get("/runs/{run_id}")
async def get_backtest_results(
    run_id: int,
    session: AsyncSession = Depends(get_db),
):
    """Get detailed backtest results."""
    from sqlalchemy import select
    from backend.app.db.models import BacktestRun
    stmt = select(BacktestRun).where(BacktestRun.id == run_id)
    result = await session.execute(stmt)
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(404, "Backtest run not found")

    return {
        "id": run.id,
        "model_version": run.model_version,
        "started_at": run.started_at.isoformat(),
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "status": run.status,
        "config": run.config,
        "metrics": run.metrics,
    }


@router.get("/jobs/{run_id}/status")
async def get_backtest_job_status(run_id: int):
    """Poll for backtest job status."""
    job = BACKTEST_JOBS.get(run_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return job