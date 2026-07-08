# CLAUDE.md — NLPTrader project notes

## Working preferences (persist across sessions)
- **Roman Urdu explanations:** whenever something in this project is logical or genuinely worth
  understanding, add a SHORT explanation in Roman Urdu alongside the English. Keep it brief.
- Owner is new to AI & programming — explain the *why*, not just the *what*.
- Scope discipline: decision-support MVP only. No price prediction, no broker execution, no Kafka.

## Project shape
- Pipeline: news → FinBERT sentiment → LLM reasoning → signal (BUY/HOLD/SELL + confidence + explanation) → dashboard.
- DB: SQLite (file-based, zero setup). Frontend: Streamlit. Backend: plain Python (FastAPI optional later).

## Honesty rules (important for the capstone)
- Trading-direction accuracy is ~50–55% out-of-sample. Do NOT claim market-beating returns.
- Always store the real article publish timestamp → needed to avoid look-ahead bias in evaluation.

## Status
- Steps 1–2 done (ingestion → SQLite). Next: Step 3 (FinBERT).
