"""
clean_relevance.py — one-off cleanup for data you ALREADY stored before the filter existed.

New articles get filtered at ingestion now. But your database still holds the old off-topic
rows (the SpaceX-as-NVDA noise). This script finds and deletes them so your signals get clean.
Roman Urdu: Naya data to ab filter ho raha hai, lekin purana noise database me mojood hai —
ye script use dhoond kar delete kar deti hai.

Safe by default: it first SHOWS you what it would delete and asks for confirmation.

Run with:  python clean_relevance.py
"""
from db import get_connection
from relevance import is_relevant


def main():
    conn = get_connection()
    rows = conn.execute("SELECT id, ticker, headline, summary FROM articles").fetchall()

    to_delete = [r["id"] for r in rows
                 if not is_relevant(r["ticker"], r["headline"], r["summary"])]

    total = len(rows)
    print(f"Scanned {total} articles. {len(to_delete)} look off-topic for their ticker.")
    if not to_delete:
        print("Nothing to clean. Your data is already on-topic.")
        conn.close()
        return

    # Show a few examples so you can sanity-check before deleting.
    print("\nExamples that would be removed:")
    sample = [r for r in rows if r["id"] in set(to_delete)][:5]
    for r in sample:
        print(f"  [{r['ticker']}] {r['headline']}")

    answer = input(f"\nDelete these {len(to_delete)} rows? (yes/no): ").strip().lower()
    if answer != "yes":
        print("Cancelled. Nothing deleted.")
        conn.close()
        return

    conn.executemany("DELETE FROM articles WHERE id = ?", [(i,) for i in to_delete])
    conn.commit()
    remaining = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    conn.close()
    print(f"Deleted {len(to_delete)} rows. {remaining} clean articles remain.")
    print("Now re-run: python signal_engine.py  &&  python llm_explain.py")


if __name__ == "__main__":
    main()
