# NLPTrader — 4-Week Capstone Execution Plan

> **Decision Support / Trade Intelligence Dashboard**  
> **Target:** BTC, ETH, XAUUSD, NVDA  
> **Signal Ensemble:** Technical Analysis + Sentiment (FinBERT) + Fundamental (RAG + LLM)  
> **Goal:** Reproducible, calibrated, backtested signal system with professional dashboard

---

## 📁 Clean File Structure (Create on New PC)

```
NLPTrader/
├── .github/workflows/           # CI (optional)
├── alembic/                     # DB migrations
│   ├── versions/
│   └── env.py
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── routes/
│   │   │   │   ├── signals.py
│   │   │   │   ├── history.py
│   │   │   │   ├── backtest.py
│   │   │   │   └── health.py
│   │   │   └── main.py
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   ├── database.py
│   │   │   └── security.py
│   │   ├── db/
│   │   │   ├── models.py
│   │   │   ├── repositories.py
│   │   │   └── session.py
│   │   ├── ingestion/
│   │   │   ├── adapters/
│   │   │   │   ├── finnhub.py
│   │   │   │   └── rss.py
│   │   │   ├── pipeline.py
│   │   │   └── deduplicator.py
│   │   ├── signals/
│   │   │   ├── ta_engine.py
│   │   │   ├── sentiment_engine.py
│   │   │   ├── fundamental_engine.py
│   │   │   ├── combiner.py
│   │   │   └── generator.py
│   │   ├── evaluation/
│   │   │   ├── backtest_engine.py
│   │   │   ├── outcome_tracker.py
│   │   │   └── metrics.py
│   │   ├── llm/
│   │   │   ├── client.py
│   │   │   └── prompts.py
│   │   └── main.py
│   ├── tests/
│   │   ├── test_ta_engine.py
│   │   ├── test_sentiment_engine.py
│   │   ├── test_combiner.py
│   │   └── test_backtest.py
│   ├── scripts/
│   │   ├── run_ingestion.py
│   │   ├── run_signals.py
│   │   ├── run_backtest.py
│   │   └── run_outcomes.py
│   ├── requirements.txt
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── hooks/
│   │   ├── api/
│   │   └── types/
│   ├── package.json
│   └── vite.config.ts
├── data/                        # ChromaDB, SQLite
├── docs/
│   ├── architecture.md
│   ├── backtest_results.md
│   └── demo_script.md
├── .env.example
├── README.md
└── docker-compose.yml
```

---

## 🗓️ Week-by-Week Plan

### **WEEK 1: FOUNDATION (Days 1-7)**

| Day | Task | Deliverable |
|---|---|---|
| 1 | Setup: PostgreSQL (Docker), Alembic, FastAPI skeleton, React+TS+Vite | `docker-compose up -d` works |
| 2 | **Extract TA Engine** from old `api.py` → `signals/ta_engine.py` | Pure functions, unit tests pass |
| 3 | **DB Schema + Migrations** (raw_articles, price_ohlcv, signals, outcomes, model_versions, backtest_runs) | `alembic upgrade head` works |
| 4 | **Sentiment Engine** refactor (FinBERT wrapper, recency-weighted aggregation) | `signals/sentiment_engine.py` tested |
| 5 | **Ingestion Pipeline** (Finnhub + RSS adapters, dedup, FinBERT scoring, ChromaDB ingest) | `python scripts/run_ingestion.py` populates DB |
| 6 | **Signal Generator** (orchestrates TA + Sentiment, saves to `signals` table) | `python scripts/run_signals.py --ticker BTC` |
| 7 | **Outcome Tracker** (cron job, evaluates expired signals, records outcomes) | `python scripts/run_outcomes.py` works |

**Week 1 Success Criteria:** `run_signals.py` generates combined TA+Sentiment signals for 4 tickers, `run_outcomes.py` correctly records results 24h later.

---

### **WEEK 2: BACKTESTING (Days 8-14)**

| Day | Task | Deliverable |
|---|---|---|
| 8 | **Historical Data Loader** (yfinance bulk download 2yrs for 4 tickers, 1h/4h/1d) | `price_ohlcv` populated |
| 9 | **BacktestEngine Core** (walk-forward, no lookahead, signal generation at each step) | `backtest_engine.py` runs |
| 10 | **TA-Only Backtest** (baseline metrics: accuracy, Sharpe, DD, calibration) | `backtest_results/ta_baseline.json` |
| 11 | **Parameter Sweep** (RSI thresholds, SMA periods, confidence weights, half-life) | Best params identified |
| 12 | **Sentiment Backtest** (simulate using actual news archive since ingestion started) | Combined baseline |
| 13 | **Calibration Analysis** (confidence buckets → actual accuracy, reliability diagrams) | Calibration curves |
| 14 | **Document Results** (equity curves, per-ticker, per-horizon, limitations) | `docs/backtest_results.md` |

**Week 2 Success Criteria:** Reproducible backtest showing TA-only vs TA+Sentiment metrics, calibrated confidence.

---

### **WEEK 3: RAG + ENSEMBLE (Days 15-21)**

| Day | Task | Deliverable |
|---|---|---|
| 15 | **ChromaDB Setup** (persistent client, collection, all-MiniLM-L6-v2 embedder) | `fundamental_engine.py` ingests |
| 16 | **Backfill ChromaDB** (ingest all existing articles from `raw_articles`) | 100% articles embedded |
| 17 | **Fundamental Engine** (retrieve top-k → LLM synthesis → narrative + bias + confidence) | `fundamental_engine.py` tested |
| 18 | **Signal Combiner** (weights, conflict penalty, LLM final synthesis) | `combiner.py` with 3 signals |
| 19 | **Integrate & Test** (full ensemble: TA + Sentiment + Fundamental) | `run_signals.py` uses all 3 |
| 20 | **Ensemble Backtest** (compare 3-signal vs 2-signal vs TA-only) | `backtest_results/ensemble.json` |
| 21 | **Model Versioning** (save winning config as `v1.0-ensemble`, tag in DB) | Reproducible model version |

**Week 3 Success Criteria:** 3-signal ensemble beats 2-signal baseline on backtest, model version saved.

---

### **WEEK 4: FRONTEND + POLISH (Days 22-28)**

| Day | Task | Deliverable |
|---|---|---|
| 22 | **API Layer** (FastAPI routes: `/signals`, `/history`, `/backtest`, `/metrics`) | Swagger docs work |
| 23 | **Dashboard Page** (live signals cards, sub-signal breakdown, confidence gauge) | Real-time polling (30s) |
| 24 | **History Page** (filterable table, outcome badges, P&L, export CSV) | Full audit trail |
| 25 | **Backtest Page** (run config form, results viewer, equity curve, calibration chart) | Interactive results |
| 26 | **Charts** (lightweight-charts for TA chart with levels, equity curve) | Professional viz |
| 27 | **Polish** (loading states, error handling, responsive, dark theme) | Production feel |
| 28 | **Demo Prep** (README, architecture diagram, demo script, 5-min video) | Submission ready |

**Week 4 Success Criteria:** Full working dashboard + backtest lab, recorded demo, clean repo.

---

## 🏗️ System Architecture

### Data Flow

```
┌──────────┐    ┌──────────────┐    ┌─────────────┐    ┌──────────────┐
│ SOURCES  │───▶│  INGESTION   │───▶│  POSTGRESQL │◀──▶│  CHROMADB    │
│          │    │  (workers)   │    │  (relational)│    │  (vectors)   │
└──────────┘    └──────────────┘    └─────────────┘    └──────────────┘
       │                │                 │                   │
       ▼                ▼                 ▼                   ▼
  Finnhub          Dedup +           raw_articles        Article
  RSS              FinBERT +         price_ohlcv         embeddings
  (future X)       ChromaDB          signals
                   ingest            outcomes
                                    model_versions
                                    backtest_runs
```

### Signal Generation

```
                    ┌──────────────┐
                    │ PRICE DATA   │ (from price_ohlcv)
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │  TA ENGINE   │ → TASignal {signal, conf, levels, reasoning}
                    └──────┬───────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
       ┌────────────┐ ┌────────────┐ ┌────────────┐
       │  NEWS      │ │ CHROMADB   │ │  REGIME    │
       │  ARTICLES  │ │  RETRIEVAL │ │  (optional)│
       └─────┬──────┘ └─────┬──────┘ └─────┬──────┘
             │              │              │
       ┌─────▼──────┐ ┌─────▼──────┐ ┌─────▼──────┐
       │ SENTIMENT  │ │FUNDAMENTAL │ │  REGIME    │
       │  ENGINE    │ │  ENGINE    │ │  ADJUST    │
       └─────┬──────┘ └─────┬──────┘ └─────┬──────┘
             │              │              │
             └──────────────┼──────────────┘
                            ▼
                   ┌─────────────────┐
                   │   COMBINER      │
                   │  • Vote count   │
                   │  • Weights      │
                   │  • Conflict pen │
                   │  • LLM synthesis│
                   └────────┬────────┘
                            │
                   ┌────────▼────────┐
                   │ COMBINED SIGNAL │
                   │ • signal/conf   │
                   │ • sub-signals   │
                   │ • entry/sl/tp   │
                   │ • reasoning     │
                   │ • model_version │
                   └────────┬────────┘
                            │
                   ┌────────▼────────┐
                   │  PERSIST        │
                   │ signals table   │
                   │ outcomes (later)│
                   └─────────────────┘
```

### Evaluation Loop

```
    ┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
    │  ACTIVE      │     │  FETCH       │     │  EVALUATE    │     │  RECORD      │
    │  SIGNALS     │────▶│  CURRENT     │────▶│  OUTCOME     │────▶│  OUTCOMES    │
    │  (expired)   │     │  PRICE       │     │  • correct?  │     │  + CALIBRATE │
    └──────────────┘     └──────────────┘     │  • max fav   │     └──────────────┘
                                              │  • max adv   │
                                              │  • hit SL/TP │
                                              └──────────────┘
                                                        │
                                                        ▼
                                              ┌──────────────┐
                                              │  BACKTEST    │
                                              │  ENGINE      │
                                              │  (walk-fwd)  │
                                              └──────────────┘
```

---

## ⚙️ Key Technical Decisions (Locked In)

| Decision | Choice | Rationale |
|---|---|---|
| **DB** | PostgreSQL (Docker) | Concurrent access, proper types, JSONB, migrations |
| **Vector DB** | ChromaDB (local persistent) | No server, Python-native, good enough for 10k docs |
| **Embedding** | `all-MiniLM-L6-v2` (384-dim) | Fast, 80MB, runs on CPU, good semantic quality |
| **LLM** | Groq (Llama-3.3-70B) + Gemini fallback | Free tier, OpenAI-compatible, fast |
| **TA Library** | Pure NumPy/Pandas (no TA-Lib) | No C deps, fully testable, transparent |
| **Backtest** | Walk-forward, event-driven | No lookahead, realistic, reproducible |
| **Frontend** | React 18 + TypeScript + Vite + TanStack Query | Modern, typed, fast dev, industry standard |
| **Charts** | `lightweight-charts` (TradingView's lib) | Professional, performant, small bundle |
| **Scheduling** | Cron (system) or APScheduler | Simple, reliable, no Celery complexity |
| **Config** | `.env` + `model_versions` table | Runtime params in DB, secrets in env |

---

## 📦 What to Copy from Old PC

### COPY THESE (Reference Only)

```
├── NLPTrader/ingest.py           → reference for Finnhub adapter
├── NLPTrader/rss_ingest.py       → reference for RSS adapter
├── NLPTrader/relevance.py        → reference for ticker mapping
├── NLPTrader/sentiment.py        → reference for FinBERT wrapper
├── NLPTrader/llm_explain.py      → reference for LLM prompts
├── NLPTrader/llm_fallback.py     → reference for Groq/Gemini client
├── NLPTrader/config.py           → reference for ticker lists
├── NLPTrader/db.py               → reference for outcome tracking logic
├── NLPTrader/api.py lines 652-1158  → TA engine math (EXTRACT THIS)
├── NLPTrader/NLPTrader_Analysis_Report.md  → context
└── NLPTrader/requirements.txt    → dependency list
```

### DO NOT COPY

```
├── api.py (monolith - rewrite)
├── dashboard.html / standalone.html (legacy)
├── signal_engine.py (naive - rewrite)
├── main.py / run_pipeline.py (replace with scripts/)
├── db.py (inline SQL - use repositories)
├── *.db files (fresh start)
├── __pycache__ / .venv
```

---

## 🚀 Day 1 Commands (New PC)

```bash
# 1. Clone fresh
git clone <your-repo> NLPTrader && cd NLPTrader

# 2. Start infra
docker-compose up -d  # postgres, chroma (optional)

# 3. Backend setup
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # fill in FINNHUB_API_KEY, LLM_API_KEY

# 4. Run migrations
alembic upgrade head

# 5. Frontend setup
cd ../frontend
npm install
npm run dev  # should show blank React app

# 6. Verify
cd ../backend
python -m pytest tests/ -v  # should pass (even if empty)
python scripts/run_ingestion.py --tickers BTC,ETH,XAUUSD,NVDA --hours 24
```

---

## 📋 Definition of Done (Per Week)

| Week | Must Have | Nice to Have |
|---|---|---|
| 1 | TA+Sentiment signals generate + persist, outcomes track | Regime detection |
| 2 | Backtest runs, outputs JSON metrics, calibration plot | Multi-horizon |
| 3 | 3-signal ensemble beats 2-signal, model version saved | X/Twitter ingestion |
| 4 | Dashboard + History + Backtest pages work, demo recorded | Auth, websockets |

---

## ⚠️ Risks & Mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| Finnhub rate limits | High | Cache responses, respect limits, add RSS fallback |
| LLM API failures | Medium | Retry with exponential backoff, Gemini fallback |
| ChromaDB memory | Low | `all-MiniLM-L6-v2` is small, 10k docs < 100MB |
| Backtest lookahead bugs | High | Unit test with synthetic data where answer is known |
| News archive too short | Medium | Backtest TA-only first, add sentiment when 3+ months data |
| Scope creep | Very High | **Stick to the 4-week plan. No new features after Week 2.** |

---

## 🎯 Final Deliverables (Submission Package)

```
NLPTrader/
├── README.md                    # Architecture, run commands, results summary
├── docs/
│   ├── architecture.md          # This diagram + decisions
│   ├── backtest_results.md      # Tables, charts, calibration curves
│   └── demo_script.md           # 5-min walkthrough script
├── backend/                     # Working API + signal engine + backtest
├── frontend/                    # Working React dashboard
├── docker-compose.yml           # One-command infra
└── demo.mp4                     # 5-min recorded demo
```

---

## 🎬 Demo Script (5 Minutes)

```
1. "Here's the live dashboard" → shows 4 tickers with combined signals
2. "Each signal breaks down into TA / Sentiment / Fundamental" → click modal
3. "Here's the backtest: 2 years, walk-forward, no lookahead" → equity curve
4. "Most importantly: calibration" → 70% confidence bucket = 68% actual accuracy
5. "Here's the model version that produced this" → reproducible config
6. "Limitations: no regime detection, 24h horizon only, news archive starts Jan 2024"
```

---

## 📝 Database Schema (Reference)

```sql
-- raw_articles: immutable, append-only news storage
CREATE TABLE raw_articles (
    id              BIGSERIAL PRIMARY KEY,
    source          TEXT NOT NULL,
    source_id       TEXT NOT NULL,
    url             TEXT UNIQUE NOT NULL,
    ticker          TEXT NOT NULL,
    headline        TEXT NOT NULL,
    summary         TEXT,
    author          TEXT,
    published_at    TIMESTAMPTZ NOT NULL,
    fetched_at      TIMESTAMPTZ DEFAULT NOW(),
    raw_json        JSONB,
    UNIQUE(source, source_id)
);

-- price_ohlcv: historical and live price data
CREATE TABLE price_ohlcv (
    id              BIGSERIAL PRIMARY KEY,
    ticker          TEXT NOT NULL,
    timeframe       TEXT NOT NULL,
    timestamp       TIMESTAMPTZ NOT NULL,
    open            NUMERIC NOT NULL,
    high            NUMERIC NOT NULL,
    low             NUMERIC NOT NULL,
    close           NUMERIC NOT NULL,
    volume          NUMERIC NOT NULL,
    source          TEXT DEFAULT 'yfinance',
    UNIQUE(ticker, timeframe, timestamp)
);

-- signals: every signal generation attempt
CREATE TABLE signals (
    id                      BIGSERIAL PRIMARY KEY,
    ticker                  TEXT NOT NULL,
    generated_at            TIMESTAMPTZ DEFAULT NOW(),
    model_version           TEXT NOT NULL,
    
    ta_signal               TEXT,
    ta_confidence           SMALLINT,
    ta_details              JSONB,
    
    sentiment_signal        TEXT,
    sentiment_confidence    SMALLINT,
    sentiment_details       JSONB,
    
    fundamental_signal      TEXT,
    fundamental_confidence  SMALLINT,
    fundamental_details     JSONB,
    
    combined_signal         TEXT NOT NULL,
    combined_confidence     SMALLINT NOT NULL,
    combined_reasoning      TEXT,
    prediction_horizon      INTERVAL NOT NULL,
    entry_price             NUMERIC,
    stop_loss               NUMERIC,
    take_profit_1           NUMERIC,
    take_profit_2           NUMERIC,
    take_profit_3           NUMERIC,
    
    status                  TEXT DEFAULT 'active',
    expires_at              TIMESTAMPTZ
);

-- outcomes: linked to signal, not ticker
CREATE TABLE outcomes (
    id                      BIGSERIAL PRIMARY KEY,
    signal_id               BIGINT REFERENCES signals(id) ON DELETE CASCADE,
    checked_at              TIMESTAMPTZ DEFAULT NOW(),
    current_price           NUMERIC NOT NULL,
    price_change_pct        NUMERIC NOT NULL,
    outcome                 TEXT NOT NULL,  -- 'correct', 'incorrect', 'neutral', 'pending'
    hours_elapsed           NUMERIC NOT NULL,
    max_favorable_pct       NUMERIC,
    max_adverse_pct         NUMERIC,
    hit_sl                  BOOLEAN DEFAULT FALSE,
    hit_tp1                 BOOLEAN DEFAULT FALSE,
    hit_tp2                 BOOLEAN DEFAULT FALSE,
    hit_tp3                 BOOLEAN DEFAULT FALSE
);

-- model_versions: reproducibility
CREATE TABLE model_versions (
    version         TEXT PRIMARY KEY,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    description     TEXT,
    config          JSONB NOT NULL,
    is_active       BOOLEAN DEFAULT FALSE,
    parent_version  TEXT REFERENCES model_versions(version)
);

-- backtest_runs: experiment tracking
CREATE TABLE backtest_runs (
    id              BIGSERIAL PRIMARY KEY,
    model_version   TEXT REFERENCES model_versions(version),
    started_at      TIMESTAMPTZ DEFAULT NOW(),
    completed_at    TIMESTAMPTZ,
    config          JSONB,
    metrics         JSONB,
    status          TEXT DEFAULT 'running'
);
```

---

## 🔑 Environment Variables (.env.example)

```bash
# Database
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/nlptrader
CHROMA_PERSIST_DIR=./data/chromadb

# APIs
FINNHUB_API_KEY=your_finnhub_key
LLM_API_KEY=your_groq_key
LLM_BASE_URL=https://api.groq.com/openai/v1
LLM_MODEL=llama-3.3-70b-versatile
GEMINI_API_KEY=your_gemini_key  # fallback

# Settings
TICKERS=BTC,ETH,XAUUSD,NVDA
LOOKBACK_HOURS=24
PREDICTION_HORIZON_HOURS=24
BATCH_LIMIT=100

# Weights (sum to 1.0)
TA_WEIGHT=0.4
SENTIMENT_WEIGHT=0.3
FUNDAMENTAL_WEIGHT=0.3

# Thresholds
SENTIMENT_HALF_LIFE_HOURS=48
MIN_ARTICLES_FOR_SENTIMENT=3
CONFLICT_PENALTY=0.5
```

---

**Copy this file to `PROJECT_PLAN.md` on your new PC. It's your north star for 4 weeks.**

**Day 1 Goal:** `docker-compose up` → `alembic upgrade head` → `run_ingestion.py` works. Everything else builds on that.

Good luck. This is a legitimately impressive capstone if you execute the plan.