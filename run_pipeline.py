"""
run_pipeline.py — saare pipeline steps ek saath chalaye (one-shot).

Roman Urdu: Ab alag-alag scripts chalane ki zaroorat nahi — bas ye ek file chalao
aur saara pipeline (fetch → sentiment → signal → LLM → earnings) chal jayega.

Run with:  python run_pipeline.py
"""
import subprocess
import sys

STEPS = [
    ("Fetching news (Finnhub)", "main.py"),
    ("Fetching RSS feeds", "rss_ingest.py"),
    ("Scoring sentiment (FinBERT)", "sentiment.py"),
    ("Generating signals", "signal_engine.py"),
    ("LLM explanations", "llm_explain.py"),
    ("Earnings calendar", "earnings_ingest.py"),
]


def main():
    for label, script in STEPS:
        print(f"\n{'='*60}")
        print(f"  {label}...")
        print(f"{'='*60}")
        res = subprocess.run([sys.executable, script], capture_output=False)
        if res.returncode != 0:
            print(f"\nFAILED at: {label}")
            print("Fix the issue above, then re-run.")
            sys.exit(1)

    print(f"\n{'='*60}")
    print("  Pipeline complete! Start dashboard:")
    print("  uvicorn api:app --reload")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
