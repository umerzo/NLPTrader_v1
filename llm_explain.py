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

from openai import OpenAI

from config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL, assert_llm_configured
from db import (
    init_ticker_table,
    ticker_signal_overview,
    top_headlines_for_ticker,
    save_ticker_explanation,
)

SYSTEM_PROMPT = (
    "You are a sharp financial news analyst. You get a ticker, its computed signal, and "
    "recent headlines. Output 3 to 5 bullet points, each on its own line, each MAX 11 "
    "words, grounded ONLY in the headlines. Start every line with exactly one marker:\n"
    "  +  for a bullish point\n"
    "  -  for a bearish point\n"
    "  =  for a neutral / mixed / 'evidence is weak' point\n"
    "No intro, no heading, no full sentences, no advice, no markdown. Just the marked lines."
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

    client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)

    overview = ticker_signal_overview()
    if not overview:
        print("No signals yet — run signal.py first.")
        return

    print(f"Explaining {len(overview)} ticker signals via {LLM_MODEL}...\n")
    now = datetime.now(timezone.utc).isoformat()

    for t in overview:
        ticker = t["ticker"]
        headlines = top_headlines_for_ticker(ticker, limit=8)
        prompt = build_user_prompt(ticker, t["signal"], t["confidence"], headlines)

        # temperature low -> steady, factual tone (not creative).
        # Roman Urdu: temperature kam rakhi hai taake jawab solid aur factual rahe.
        resp = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=180,
        )
        explanation = resp.choices[0].message.content.strip()
        save_ticker_explanation(ticker, t["signal"], t["confidence"], explanation, now)

        print(f"[{ticker}] {t['signal']} ({t['confidence']}/100)")
        print(f"  {explanation}\n")

    print("Saved all explanations to the ticker_signals table.")


if __name__ == "__main__":
    main()
