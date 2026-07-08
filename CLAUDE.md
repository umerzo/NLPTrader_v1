# CLAUDE.md — project NLPTrader (memory + handoff)

Reference name the user uses: **"project NLPTrader"**.

## Working preferences (persist across sessions)
- **Roman Urdu explanations:** whenever something is logical or worth understanding, add a
  SHORT Roman Urdu explanation alongside the English. Keep it brief.
- User (Abdullah) is **new to AI & programming** — explain the *why*, not just the *what*.
- User wants **honest pushback**, no glazing. Lead with what's wrong/missing first.
- Be **concise and direct**. Skip warm-up sentences.
- Hard constraint that shaped scope: **1–4 weeks, solo, beginner**. Keep it simple.
- Machine: **Windows, 8 GB RAM** (had paging-file/memory issues; FinBERT runs but is tight).

## What the project is
An interpretable financial-news → trading-signal engine. **Decision-support only, NOT auto-
trading, NOT price prediction.** Pipeline:
news → FinBERT sentiment → rule-based signal (BUY/HOLD/SELL + confidence) → LLM grounded
explanation (bullets) → Streamlit dashboard.

## Honest reality (agreed, keep in capstone writeup)
- Trading-direction accuracy out-of-sample is only ~50–55%. Do NOT claim market-beating returns.
- Flashy backtest numbers online = look-ahead bias + ignored costs. We frame honesty as the
  project's strength.
- This is a well-cloned tutorial pattern; the differentiator is the grounded explanation layer.
- Sparklines in the UI are DECORATIVE (not real prices). Forex data is sparse by design.

## Tech stack
Python · SQLite (file db) · FinBERT (ProsusAI/finbert via transformers) · LLM via OpenAI-
compatible API (default **Groq**, free, llama-3.3-70b-versatile; DeepSeek/OpenAI also work by
changing 3 .env values) · Streamlit dashboard (glassmorphism, 3 sections, right control bar).

## Files (all in E:\nlptrader\)
- `config.py` — settings; defines STOCKS/CRYPTO/FOREX (10 each), asset_class_of(), LLM config.
- `db.py` — SQLite schema + all helpers (articles + ticker_signals tables).
- `relevance.py` — company/coin/pair name map; is_relevant(), match_symbol(). Filters off-topic news.
- `ingest.py` — Finnhub: per-stock company-news + general crypto/forex category news (tagged).
- `sentiment.py` — FinBERT scoring (BATCH_LIMIT knob; loads model w/ use_safetensors, 1 thread).
- `signal_engine.py` — rule signal (MIN_CONFIDENCE=0.60) + per-ticker net-score overview.
- `llm_explain.py` — per-ticker grounded bullets (3–5, marked +/-/=). ~1 call per ticker (cheap).
- `app.py` — Streamlit dashboard. Hides Refresh button when torch absent (hosted demo).
- `clean_relevance.py` — one-off: delete old off-topic rows from existing db.
- `main.py` — runs ingestion (steps 1–2).
- `requirements.txt` (slim, for deploy) · `requirements-pipeline.txt` (torch/transformers/openai, local).
- `.env` (secrets, NOT committed) · `.gitignore` (ships nlptrader.db, hides .env).
- `DEPLOY.md` — deploy guide (Streamlit Community Cloud, display-only snapshot).

## Universes
- Stocks (10): AAPL MSFT NVDA AMZN GOOGL META TSLA AVGO JPM V
- Crypto (10): BTC ETH SOL XRP BNB ADA DOGE AVAX LINK DOT
- Forex (10): EURUSD GBPUSD USDJPY USDCHF AUDUSD USDCAD NZDUSD EURGBP EURJPY GBPJPY

## How to run (local)
```
python clean_relevance.py        # once, scrub old off-topic rows (type yes)
python main.py                   # fetch news
python sentiment.py              # repeat until "Nothing to score" (bump BATCH_LIMIT to finish faster)
python signal_engine.py
python llm_explain.py            # needs LLM_API_KEY (Groq) in .env
streamlit run app.py             # dashboard; or use the in-app Refresh button after first run
```
Naming gotcha solved: the signal file is `signal_engine.py` (NOT signal.py — collided with
Python's built-in `signal` module).

## V1 additions (HTML frontend + FastAPI) — this is the current primary frontend
- `api.py` (FastAPI) serves the DB as JSON and serves the standalone HTML.
  - GET /api/dashboard (signals, news+url, stats, confDist, topTickers)
  - GET /api/ticker/{t} (stored bullets + top-3 credibility-ranked articles)
  - POST /api/ticker/{t}/regenerate (fresh LLM explanation on demand)
  - GET /api/calendar?offset=N (month grid of upcoming earnings, tagged with live signal)
- `NLPTrader-standalone.html` — bundled DC/React single file, BOUND to api.py via fetch()
  with mock fallback. Edited by unpacking the `__bundler/template` block (JSON string) and
  re-encoding with `</`->`<\/`. Features: real signal cards, clickable signal rows -> detail
  modal (why + article links + Regenerate button), clickable news (opens source), Events
  Calendar month grid (click ticker -> modal).
- `earnings_ingest.py` — Finnhub free earnings calendar for the 10 stocks -> earnings table.
- Streamlit `app.py` still works independently; its Refresh button now runs the FULL pipeline
  incl. rss_ingest + earnings_ingest.
- Run the HTML frontend:  uvicorn api:app --reload  -> http://localhost:8000
- Not-yet-connected in HTML: eventTypes donut (no event classification), Accuracy (no ground
  truth), stat trends (no history), side-nav pages Watchlist/Analytics/History/etc. (placeholders).

## Status (V1 — 2026-07-01)
- Full pipeline + BOTH frontends (Streamlit and HTML/FastAPI) working locally with real data.
- Backups: NLPTraderV0_Streamlit.zip (Streamlit only), NLPTraderV1.zip (everything).
- Deploy package ready; NOT yet deployed (user will do GitHub + Streamlit Cloud).
- Note: shell mount can lag behind Edit-tool writes; verify with a grep before trusting shell.

## Open / next ideas
1. Run `clean_relevance.py` again — a little mis-tagged news (e.g. SpaceX bullet on AAPL) remains.
2. Deploy to Streamlit Cloud (DEPLOY.md).
3. Make the card "Details" button real (currently aesthetic).
4. Optional: relevance filter is keyword-based; note its limits in the writeup.
5. The analysis report + architecture diagram (NLPTrader_Analysis_Report.md, NLPTrader_architecture.svg)
   live in the earlier outputs folder.
