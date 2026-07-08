# NLPTrader

An interpretable financial-news analysis tool: ingest news → score sentiment → generate an
evidence-grounded BUY/HOLD/SELL signal with an explanation. **Decision-support, not auto-trading.**

This repo currently covers **Steps 1–2**: getting real news to land reliably in a local database.

## Files (drop them all into one folder named `nlptrader/`)

```
nlptrader/
├── CLAUDE.md           # project notes + working preferences (read me)
├── README.md
├── requirements.txt
├── .env.example        # copy to .env and add your Finnhub key
├── .gitignore
├── config.py           # loads settings + API key from .env
├── db.py               # SQLite schema + save/read helpers
├── ingest.py           # fetch news from Finnhub, dedupe, store
└── main.py             # run the pipeline (steps 1 + 2)
```

## Setup (do this once)

1. Install Python 3.10+.
2. In the folder, create a virtual environment and activate it:
   - Windows: `python -m venv venv` then `venv\Scripts\activate`
   - Mac/Linux: `python3 -m venv venv` then `source venv/bin/activate`
3. `pip install -r requirements.txt`
4. Get a free key at https://finnhub.io → copy `.env.example` to `.env` → paste your key.

## Run

```
python main.py
```

You should see articles fetched and a count of new rows saved. Run it again — the count of *new*
rows should drop to ~0 (that proves dedupe works).

## Roadmap
- [x] Step 1 — environment + one real headline
- [x] Step 2 — ingestion → SQLite (this repo)
- [ ] Step 3 — FinBERT sentiment scoring
- [ ] Step 4 — LLM reasoning + signal
- [ ] Step 5 — Streamlit dashboard
