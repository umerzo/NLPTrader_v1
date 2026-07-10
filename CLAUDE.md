# CLAUDE.md — project NLPTrader (memory + handoff)

Reference name the user uses: **"project NLPTrader"**.

## Working preferences (persist across sessions)
- **Roman Urdu explanations:** whenever something is logical or worth understanding, add a
  SHORT Roman Urdu explanation alongside the English. Keep it brief.
- User (Abdullah) is **new to AI & programming** — explain the *why*, not just the *what*.
- User wants **honest pushback**, no glazing. Lead with what's wrong/missing first.
- Be **concise and direct**. Skip warm-up sentences.
- Machine: **Windows, 8 GB RAM** (had paging-file/memory issues; FinBERT runs but is tight).

## What the project is
An interpretable financial-news → trading-signal engine. **Decision-support only, NOT auto-
trading, NOT price prediction.** Pipeline:
news → FinBERT sentiment → recency-weighted signal (BUY/HOLD/SELL + volume-aware confidence)
→ LLM grounded explanation (bullets) → FastAPI + HTML dashboard.

## Key improvements over V1
- **Recency weighting:** recent articles (within 48h) get higher weight in signal calculation.
  Exponential decay — news gets halved in influence every 48 hours.
- **Volume-aware confidence:** signals based on 1-5 articles capped at 50% confidence,
  6-15 at 75%, 16+ at 100%. No more false confidence from sparse data.
- **Sample size shown:** every signal card now shows "based on X articles".
- **Data freshness tracking:** dashboard shows "last updated X ago" and warns when data is stale.
- **Streamlit removed:** only FastAPI + HTML frontend maintained. Single frontend to maintain.
- **`sampleSize` field** in all API responses so the frontend can display article count.
- **`/api/status` endpoint** for pipeline health check.
- **`run_pipeline.py`** — one-shot script runs all pipeline steps sequentially.

## Tech stack
Python · SQLite (file db) · FinBERT (ProsusAI/finbert via transformers) · LLM via OpenAI-
compatible API (default **Groq**, free, llama-3.3-70b-versatile) · FastAPI · HTML/DC dashboard.

## Files (all in C:\Users\umarx\Desktop\NLP_OpenCode\NLPTrader\)
- `config.py` — settings; STOCKS/CRYPTO/FOREX (10 each), asset_class_of(), LLM config.
- `db.py` — SQLite schema + all helpers. **Key function:** `ticker_signal_overview()` with
  recency weighting + volume-aware confidence.
- `relevance.py` — company/coin/pair name map; is_relevant(), match_symbol(). Filters off-topic news.
- `ingest.py` — Finnhub: per-stock company-news + general crypto/forex category news (tagged).
- `rss_ingest.py` — pulls 20+ free RSS feeds, filters by relevance, stores to DB.
- `sentiment.py` — FinBERT scoring (BATCH_LIMIT knob).
- `signal_engine.py` — generates per-article signals; prints weighted per-ticker overview.
- `llm_explain.py` — per-ticker grounded bullets (3-5, marked +/-/=). ~1 call per ticker.
- `api.py` — FastAPI backend. Endpoints: /api/dashboard, /api/ticker/{t}, /api/ticker/{t}/regenerate,
  /api/calendar, /api/status.
- `earnings_ingest.py` — Finnhub earnings calendar for stocks.
- `clean_relevance.py` — one-off: delete old off-topic rows from db.
- `main.py` — ingestion step (Finnhub company-news).
- `run_pipeline.py` — runs ALL pipeline steps in sequence (one command).
- `NLPTrader-standalone.html` — bundled DC/React HTML frontend.
- `requirements.txt` — fastapi, uvicorn, requests, python-dotenv, feedparser, openai.
- `app.py` — replaced; now just shows a message pointing to the HTML frontend.

## API endpoints
| Endpoint | Description |
|---|---|
| GET /api/dashboard | Signals (with sampleSize, dataAge), news, stats, confDist, topTickers |
| GET /api/ticker/{t} | Detail: signal, confidence, sampleSize, LLM bullets, top 3 articles |
| POST /api/ticker/{t}/regenerate | Fresh LLM explanation for one ticker |
| GET /api/calendar?offset=N | Month grid of earnings dates |
| GET /api/status | Pipeline health: dataAge, totalArticles, scoredArticles |

## How to run (local)
```powershell
# One-time setup
copy .env.example .env    # then fill in your Finnhub + Groq keys
pip install -r requirements.txt
pip install transformers torch   # for FinBERT (local only)

# Run the full pipeline
python run_pipeline.py

# Start dashboard
uvicorn api:app --reload
# Open http://localhost:8000
```

## What's NOT yet connected in HTML frontend
- eventTypes donut (no event classification yet)
- Accuracy stat (no ground truth labels)
- Stat trends (no history tracking)
- Side-nav pages Watchlist/Analytics/History (placeholders)
- These are visual placeholders in the bundled HTML; the API returns real data.

## Honest reality
- Trading-direction accuracy is ~50-55% (no ground truth tracking).
- Sparklines in UI are DECORATIVE (not real prices).
- Forex data is sparse by design (free tier limitations).
- Relevance filter is keyword-based; some off-topic news may slip through.
