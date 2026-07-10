"""
signal_engine.py — Step 4: turn sentiment into a trading signal (BUY / HOLD / SELL).

Now uses recency-weighted scoring + volume-aware confidence. Recent news counts more,
and signals based on more articles are displayed with higher confidence.

Roman Urdu: Naye signal engine me purani khabron se zyada, taaza khabron ka weight hai.
Aur jis ticker ke baare me zyada khabrein hain, uska signal utna hi bharosemand hai.

Run with:  python signal_engine.py
"""
from db import fetch_unsignaled, save_signal, ticker_signal_overview, init_history_table, log_signal_snapshot

BATCH_LIMIT = 1000


def decide_signal(sentiment, score):
    score = score or 0.0
    if sentiment == "positive":
        return "BUY", round(score * 100)
    if sentiment == "negative":
        return "SELL", round(score * 100)
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

    overview = ticker_signal_overview()
    print("=== Per-ticker overview (recency-weighted, volume-aware) ===")
    print(f"{'TICKER':<8}{'ARTICLES':<10}{'NET':<8}{'SIGNAL':<8}{'CONF':<6}NOTES")
    for t in overview:
        notes = []
        if t["articles"] < 6:
            notes.append("low volume")
        if t["articles"] >= 16:
            notes.append("high volume")
        note_str = ", ".join(notes) if notes else ""
        print(f"{t['ticker']:<8}{t['articles']:<10}{t['net']:<8}{t['signal']:<8}{t['confidence']:<6}{note_str}")

    # Log snapshot for change detection
    init_history_table()
    log_signal_snapshot(overview)
    print(f"\nLogged {len(overview)} ticker signals to history for change tracking.")


if __name__ == "__main__":
    main()
