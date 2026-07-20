"""
backtest.py — Backtest API routes (out of scope per PROJECT_SPEC.md §1).
"""
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/backtest", tags=["backtest"])


@router.get("/runs")
async def backtest_runs():
    return []

@router.get("")
async def backtest_not_implemented():
    raise HTTPException(501, "Backtesting is out of scope per PROJECT_SPEC.md §1")