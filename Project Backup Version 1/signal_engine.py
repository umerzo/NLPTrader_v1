"""
signal.py — Step 4: turn sentiment into a trading signal (BUY / HOLD / SELL).

This is the FREE, rule-based version. No API key, instant, deterministic. It maps each
scored article to a signal and a confidence number, and also prints a per-ticker overview.

The grounded LLM *explanation* layer plugs in later (provider-agnostic: DeepSeek / Groq /
OpenAI). This file is the dependable backbone underneath it.
Roman Urdu: Ye signal engine sirf rules se chalta hai — free, fauran, aur hamesha same
result. LLM wali tafseel (explanation) baad me isi ke upar lagti hai.

Run with:  python signal.py
"""
from db import fetch_unsignaled, save_signal, ticker_signal_overview

# --- Tuning knobs (change these to make the engine bolder or more cautious) ---
# A positive/negative label is only trusted if FinBERT was at least this confident.
# Below this, we play safe and say HOLD.
# Roman Urdu: Agar FinBERT itna (0.60) confident na ho to hum risk nahi lete -> HOLD.
MIN_CONFIDENCE = 0.60

BATCH_LIMIT = 1000  # how many articles to signal per run


def decide_signal(sentiment, score):
    """
    Core rule: sentiment + how sure FinBERT was -> a signal and a 0..100 confidence.

    Why gate on score? A weak 'positive' is basically a coin flip; turning it into a BUY
    would just add noise. Only act when the model is reasonably sure.
    """
    score = score or 0.0
    if sentiment == "positive" and score >= MIN_CONFIDENCE:
        return "BUY", round(score * 100)
    if sentiment == "negative" and score >= MIN_CONFIDENCE:
        return "SELL", round(score * 100)
    # neutral, OR a low-confidence positive/negative -> sit out
    return "HOLD", round(score * 100)


def main():
    rows = fetch_unsignaled(limit=BATCH_LIMIT)
    if not rows:
        print("No new articles to signal (all scored ones already have a signal).")
    else:
        print(f"Generating signals for {len(rows)} articles...")
        counts = {"BUY": 0, "HOLD": 0, "SELL": 0}
        for row in rows:
            sig, conf = decide_signal(row["sentiment"], row["sentiment_score"])
            save_signal(row["id"], sig, conf)
            counts[sig] += 1
        print(f"Done. Per-article signals: {counts}\n")

    # The part a human actually cares about: one verdict per ticker.
    print("=== Per-ticker overview ===")
    print(f"{'TICKER':<8}{'ARTICLES':<10}{'NET':<8}{'SIGNAL':<8}{'CONF'}")
    for t in ticker_signal_overview():
        print(f"{t['ticker']:<8}{t['articles']:<10}{t['net']:<8}{t['signal']:<8}{t['confidence']}")


if __name__ == "__main__":
    main()
