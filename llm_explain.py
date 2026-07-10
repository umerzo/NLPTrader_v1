"""
llm_explain.py — Step 4b: a grounded, plain-English "why" for each ticker's signal.

This is the project's real differentiator. The rule engine (signal.py) decides BUY/HOLD/SELL;
the LLM here explains it using ONLY the actual headlines — no outside knowledge, no advice.
Roman Urdu: Signal to rules ne banaya — yahan LLM sirf asli headlines ke base par 2-3 line
me wajah likhta hai. Bahar ka knowledge ya mashwara nahi, sirf di hui khabron se.

Cost is tiny: we call the LLM ONCE PER TICKER (≈5 calls), not once per article (≈1000).
That single design choice is the difference between free and expensive.

Run with:  python llm_explain.py
Needs a free Groq key in .env (see config.py).
"""
from datetime import datetime, timezone

from config import assert_llm_configured
from db import (
    init_ticker_table,
    ticker_signal_overview,
    top_headlines_for_ticker,
    save_ticker_explanation,
)
from llm_fallback import llm_complete

SYSTEM_PROMPT = (
    "You are a sharp financial news analyst. You get a ticker, its computed signal, and "
    "recent headlines. Write 3 to 5 bullet points, one per line. Each bullet = what the "
    "headline says + the concrete impact it has on the ticker's outlook (up/down/risk). "
    "Example: 'New FDA approval opens $2B market, boosting revenue outlook' not just "
    "'FDA approves new drug'. Keep each bullet under 22 words. Ground every bullet in "
    "actual headlines. Start every line with exactly one marker:\n"
    "  +  for a bullish / positive point\n"
    "  -  for a bearish / negative point\n"
    "  =  for a neutral / mixed / 'evidence is weak' point\n"
    "No intro, no heading, no markdown. Just the marked lines."
)


def build_user_prompt(ticker, signal, confidence, headlines):
    lines = "\n".join(f"- ({h['sentiment']}) {h['headline']}" for h in headlines)
    return (
        f"Ticker: {ticker}\n"
        f"Computed signal: {signal} (confidence {confidence}/100)\n"
        f"Recent headlines:\n{lines}\n\n"
        f"Explain, grounded only in these headlines:"
    )


def main():
    assert_llm_configured()
    init_ticker_table()

    overview = ticker_signal_overview()
    if not overview:
        print("No signals yet — run signal.py first.")
        return

    print(f"Explaining {len(overview)} ticker signals via Groq → Gemini fallback...\n")
    now = datetime.now(timezone.utc).isoformat()

    for t in overview:
        ticker = t["ticker"]
        headlines = top_headlines_for_ticker(ticker, limit=8)
        prompt = build_user_prompt(ticker, t["signal"], t["confidence"], headlines)

        explanation, provider = llm_complete(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=prompt,
            max_tokens=180,
            temperature=0.2,
        )
        if explanation is None:
            print(f"[{ticker}] Both LLM providers failed, skipping")
            continue
        save_ticker_explanation(ticker, t["signal"], t["confidence"], explanation, now)

        print(f"[{ticker}] {t['signal']} ({t['confidence']}/100) — via {provider}")
        print(f"  {explanation}\n")

    print("Saved all explanations to the ticker_signals table.")


if __name__ == "__main__":
    main()
