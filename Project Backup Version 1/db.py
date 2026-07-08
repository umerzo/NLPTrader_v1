"""
db.py — everything about the local SQLite database.

SQLite is just a single file on disk; no server to install. Perfect for an MVP.
Roman Urdu: SQLite ek single file database hai — koi server install nahi karna parta,
isliye beginner ke liye sab se aasaan choice hai.
"""
import sqlite3
from config import DB_PATH


def get_connection():
    """Open a connection. row_factory lets us read columns by name (row['headline'])."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """
    Create the articles table if it doesn't exist yet. Safe to call every run.

    The 'url' column is UNIQUE — this is our dedupe trick. If we try to insert the same
    article twice, SQLite rejects the duplicate instead of creating a copy.
    Roman Urdu: 'url' ko UNIQUE rakha hai — agar wohi khabar dobara aaye to database
    use reject kar deta hai, is liye duplicate news store nahi hoti.

    Columns the later steps will fill (sentiment, signal...) are created now but left NULL,
    so we don't have to change the table structure later.
    """
    conn = get_connection()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS articles (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker       TEXT,
            headline     TEXT NOT NULL,
            summary      TEXT,
            source       TEXT,
            url          TEXT UNIQUE,
            published_at TEXT,          -- real publish time (UTC). Critical for honest evaluation.
            fetched_at   TEXT,          -- when WE pulled it
            -- filled by later steps:
            sentiment        TEXT,      -- positive / negative / neutral  (Step 3)
            sentiment_score  REAL,      -- 0..1 confidence from FinBERT    (Step 3)
            signal           TEXT,      -- BUY / HOLD / SELL               (Step 4)
            signal_confidence INTEGER,  -- 0..100                          (Step 4)
            explanation      TEXT       -- LLM reasoning                   (Step 4)
        )
        """
    )
    conn.commit()
    conn.close()


def save_articles(articles):
    """
    Insert a list of article dicts. Returns how many were NEW (duplicates are skipped).

    'INSERT OR IGNORE' means: if the url already exists, silently skip it.
    Roman Urdu: 'INSERT OR IGNORE' ka matlab — agar url pehle se mojood hai to skip kar do,
    error mat do. Is se hum baar baar script chala sakte hain bina duplicate banaye.
    """
    conn = get_connection()
    new_count = 0
    for a in articles:
        cur = conn.execute(
            """
            INSERT OR IGNORE INTO articles
                (ticker, headline, summary, source, url, published_at, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                a.get("ticker"),
                a.get("headline"),
                a.get("summary"),
                a.get("source"),
                a.get("url"),
                a.get("published_at"),
                a.get("fetched_at"),
            ),
        )
        # rowcount is 1 when a row was actually inserted, 0 when it was ignored (duplicate).
        new_count += cur.rowcount
    conn.commit()
    conn.close()
    return new_count


def count_articles():
    conn = get_connection()
    n = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    conn.close()
    return n


def latest_articles(limit=10):
    conn = get_connection()
    rows = conn.execute(
        "SELECT ticker, headline, source, published_at FROM articles "
        "ORDER BY published_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return rows


# ---------------------------------------------------------------------------
# Step 3 helpers — sentiment
# ---------------------------------------------------------------------------

def fetch_unscored(limit=None):
    """
    Return rows that don't have a sentiment yet (sentiment IS NULL).

    Why filter on NULL? So we only score NEW articles each run instead of re-scoring
    the whole database every time. This makes the script cheap and re-runnable.
    Roman Urdu: Sirf wohi articles uthate hain jinka sentiment abhi tak khali (NULL) hai —
    is se har dafa poori database dobara process nahi karni parti, sirf nayi khabrein.
    """
    conn = get_connection()
    sql = "SELECT id, headline, summary FROM articles WHERE sentiment IS NULL ORDER BY id"
    if limit:
        sql += f" LIMIT {int(limit)}"
    rows = conn.execute(sql).fetchall()
    conn.close()
    return rows


def save_sentiment(article_id, label, score):
    """Write the FinBERT result back onto the article row."""
    conn = get_connection()
    conn.execute(
        "UPDATE articles SET sentiment = ?, sentiment_score = ? WHERE id = ?",
        (label, score, article_id),
    )
    conn.commit()
    conn.close()


def sentiment_summary():
    """Quick counts per sentiment label, for a sanity check after scoring."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT sentiment, COUNT(*) AS n FROM articles "
        "WHERE sentiment IS NOT NULL GROUP BY sentiment"
    ).fetchall()
    conn.close()
    return {r["sentiment"]: r["n"] for r in rows}


# ---------------------------------------------------------------------------
# Step 4 helpers — signals
# ---------------------------------------------------------------------------

def fetch_unsignaled(limit=None):
    """
    Rows that HAVE a sentiment but do NOT yet have a signal.

    We only act on already-scored articles, and we skip ones already signalled — same
    'only do new work' idea as Step 3, so the script stays cheap and re-runnable.
    Roman Urdu: Sirf wo articles uthate hain jinka sentiment ho chuka hai lekin signal
    abhi baaki hai — is se dobara kaam nahi hota.
    """
    conn = get_connection()
    sql = (
        "SELECT id, ticker, headline, sentiment, sentiment_score "
        "FROM articles WHERE sentiment IS NOT NULL AND signal IS NULL ORDER BY id"
    )
    if limit:
        sql += f" LIMIT {int(limit)}"
    rows = conn.execute(sql).fetchall()
    conn.close()
    return rows


def save_signal(article_id, signal, confidence):
    conn = get_connection()
    conn.execute(
        "UPDATE articles SET signal = ?, signal_confidence = ? WHERE id = ?",
        (signal, confidence, article_id),
    )
    conn.commit()
    conn.close()


def ticker_signal_overview():
    """
    Aggregate per-article signals into ONE view per ticker.

    A single ticker has many articles; a human wants one answer, not 200. We compute a
    'net score': each positive article pushes up, each negative pushes down, neutral = 0.
    The average tells us the overall lean. This is far more useful than per-article noise.
    Roman Urdu: Ek ticker ki bohot saari khabrein hoti hain — hum unka net score nikaal kar
    ek hi overall faisla (BUY/HOLD/SELL) banate hain, jo dashboard par dikhega.
    """
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT ticker,
               COUNT(*) AS n,
               SUM(CASE WHEN sentiment='positive' THEN sentiment_score
                        WHEN sentiment='negative' THEN -sentiment_score
                        ELSE 0 END) AS net_raw
        FROM articles
        WHERE sentiment IS NOT NULL
        GROUP BY ticker
        ORDER BY ticker
        """
    ).fetchall()
    conn.close()

    overview = []
    for r in rows:
        n = r["n"] or 1
        net = (r["net_raw"] or 0) / n          # average lean, roughly -1..+1
        if net > 0.15:
            sig = "BUY"
        elif net < -0.15:
            sig = "SELL"
        else:
            sig = "HOLD"
        overview.append(
            {
                "ticker": r["ticker"],
                "articles": r["n"],
                "net": round(net, 3),
                "signal": sig,
                "confidence": min(100, round(abs(net) * 100)),
            }
        )
    return overview


# ---------------------------------------------------------------------------
# Step 4b helpers — LLM explanations (stored per ticker, not per article)
# ---------------------------------------------------------------------------

def init_ticker_table():
    """One row per ticker holding its overall signal + the LLM's grounded explanation.
    Roman Urdu: Har ticker ki ek hi row — uska overall signal aur LLM ki di hui wajah."""
    conn = get_connection()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS ticker_signals (
            ticker      TEXT PRIMARY KEY,
            signal      TEXT,
            confidence  INTEGER,
            explanation TEXT,
            updated_at  TEXT
        )
        """
    )
    conn.commit()
    conn.close()


def top_headlines_for_ticker(ticker, limit=8):
    """Most recent headlines for one ticker — the evidence we feed the LLM.
    We send only headlines (short + cheap), newest first."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT headline, sentiment FROM articles "
        "WHERE ticker = ? AND sentiment IS NOT NULL "
        "ORDER BY published_at DESC LIMIT ?",
        (ticker, limit),
    ).fetchall()
    conn.close()
    return rows


def save_ticker_explanation(ticker, signal, confidence, explanation, updated_at):
    """Insert or overwrite this ticker's row (UPSERT)."""
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO ticker_signals (ticker, signal, confidence, explanation, updated_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(ticker) DO UPDATE SET
            signal=excluded.signal,
            confidence=excluded.confidence,
            explanation=excluded.explanation,
            updated_at=excluded.updated_at
        """,
        (ticker, signal, confidence, explanation, updated_at),
    )
    conn.commit()
    conn.close()


def get_ticker_signals():
    """Read the finished ticker verdicts (for the dashboard in Step 5)."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT ticker, signal, confidence, explanation, updated_at "
        "FROM ticker_signals ORDER BY ticker"
    ).fetchall()
    conn.close()
    return rows


# ---------------------------------------------------------------------------
# Step 5 helper — flexible article query for the dashboard
# ---------------------------------------------------------------------------

def get_articles(ticker=None, sentiment=None, search=None, limit=300):
    """
    Fetch articles with optional filters. We build the WHERE clause piece by piece and
    use '?' placeholders — never f-strings with user text — so we're safe from SQL
    injection and from quote/typing bugs.
    Roman Urdu: Filters ke hisab se query banate hain aur values '?' ke zariye dete hain —
    is se SQL injection aur quotes ke masle dono se bach jate hain.
    """
    clauses, params = [], []
    if ticker and ticker != "All":
        clauses.append("ticker = ?")
        params.append(ticker)
    if sentiment and sentiment != "All":
        clauses.append("sentiment = ?")
        params.append(sentiment)
    if search:
        clauses.append("headline LIKE ?")
        params.append(f"%{search}%")

    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (
        "SELECT ticker, headline, source, published_at, sentiment, sentiment_score, "
        "signal, signal_confidence, url "
        f"FROM articles {where} ORDER BY published_at DESC LIMIT ?"
    )
    params.append(limit)

    conn = get_connection()
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return rows
