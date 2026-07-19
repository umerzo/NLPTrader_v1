"""
main.py — FastAPI application entry point.
Thin layer: routes only, all business logic in signals/ingestion/evaluation packages.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.routes import signals, backtest, health, ta, news, prices
from backend.app.db.session import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()
    yield
    # Shutdown (cleanup if needed)


app = FastAPI(
    title="NLPTrader API",
    description="Decision Support / Trade Intelligence Dashboard",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS for local frontend dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router)
app.include_router(signals.router)
app.include_router(backtest.router)
app.include_router(ta.router)
app.include_router(news.router)
app.include_router(prices.router)


@app.get("/")
async def root():
    return {
        "service": "NLPTrader API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health/full",
    }