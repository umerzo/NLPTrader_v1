"""
main.py — run Steps 1 + 2: fetch news and land it in SQLite.

Run with:  python main.py
Run it twice: the second run should add ~0 new rows, proving dedupe works.
Roman Urdu: Script do dafa chalao — doosri dafa naye rows ~0 hone chahiye. Ye sabit
karta hai ke duplicate news store nahi ho rahi (dedupe sahi kaam kar raha hai).
"""
from config import assert_configured, TICKERS
from db import init_db, save_articles, count_articles, latest_articles
from ingest import fetch_all


def main():
    assert_configured()          # stop early if the API key is missing
    init_db()                    # create the table if needed

    print(f"Fetching news for: {', '.join(TICKERS)}")
    articles = fetch_all()

    new_count = save_articles(articles)
    print(f"\nFetched {len(articles)} articles | {new_count} were new | "
          f"{count_articles()} total in database")

    print("\nLatest headlines stored:")
    for row in latest_articles(limit=5):
        print(f"  [{row['ticker']}] {row['headline']}  ({row['source']})")


if __name__ == "__main__":
    main()
