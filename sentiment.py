"""
sentiment.py — Step 3: score each stored article with FinBERT.

FinBERT (ProsusAI/finbert) is a BERT model already fine-tuned on financial text. We do NOT
train it — we just download it once and use it. It reads a piece of text and returns one of:
positive / negative / neutral, plus a confidence score (0..1).
Roman Urdu: FinBERT pehle se financial news par train hai — hum ise train nahi karte, sirf
download kar ke use karte hain. Ye har khabar ko positive/negative/neutral label deta hai.

Run with:  python sentiment.py
First run downloads the model (~400 MB) once, then caches it. CPU is fine; it's just slower.
"""
from transformers import pipeline

from db import fetch_unscored, save_sentiment, sentiment_summary

# How many articles to score in one run. Start small to test, then raise it.
# Roman Urdu: Pehle thori si (e.g. 25) score kar ke test karo, phir number barha do.
BATCH_LIMIT = 1000


def build_text(headline, summary):
    """
    Combine headline + summary for richer context, but keep it short.

    FinBERT can only read ~512 tokens, and a headline alone is often enough signal.
    We cap the length so we never overflow the model.
    Roman Urdu: Headline aur summary ko mila kar dete hain taake context ziyada ho,
    lekin lambai limit me rakhte hain warna model ki capacity cross ho jati hai.
    """
    text = headline or ""
    if summary:
        text += ". " + summary
    return text[:1000]  # characters, comfortably under the token limit


def main():
    rows = fetch_unscored(limit=BATCH_LIMIT)
    if not rows:
        print("Nothing to score — every article already has a sentiment. ")
        print("Current totals:", sentiment_summary())
        return

    print(f"Loading FinBERT model (first time downloads ~400 MB)...")
    # truncation=True protects us if any text is still too long for the model.
    classifier = pipeline(
        "sentiment-analysis",
        model="ProsusAI/finbert",
        truncation=True,
    )

    print(f"Scoring {len(rows)} articles...\n")
    for i, row in enumerate(rows, start=1):
        text = build_text(row["headline"], row["summary"])
        result = classifier(text)[0]           # e.g. {'label': 'positive', 'score': 0.97}
        label = result["label"].lower()        # normalise to lower-case
        score = round(float(result["score"]), 4)
        save_sentiment(row["id"], label, score)

        if i % 25 == 0 or i == len(rows):
            print(f"  scored {i}/{len(rows)}")

    print("\nDone. Sentiment counts so far:", sentiment_summary())
    print("Tip: run again to score the next batch if more articles remain.")


if __name__ == "__main__":
    main()
