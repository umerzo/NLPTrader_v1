"""
db.py — everything about the local SQLite database.

SQLite is just a single file on disk; no server to install. Perfect for an MVP.
Roman Urdu: SQLite ek single file database hai — koi server install nahi karna parta,
isliye beginner ke liye sab se aasaan choice hai.
"""
from datetime import datetime, timezone, timedelta
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
            image        TEXT,          -- article thumbnail from Finnhub
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
    # Migration: add image column if it doesn't exist (for DBs created before image support)
    try:
        conn.execute("ALTER TABLE articles ADD COLUMN image TEXT")
    except Exception:
        pass  # column already exists — safe to ignore
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
                (ticker, headline, summary, source, url, image, published_at, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                a.get("ticker"),
                a.get("headline"),
                a.get("summary"),
                a.get("source"),
                a.get("url"),
                a.get("image"),
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
    Aggregate per-article signals into ONE view per ticker, with recency weighting.

    Key improvements over old version:
    1. RECENCY WEIGHT: articles published in last 24h get 2x weight, 24-48h get 1.5x,
       older gets 0.5x. Recent news matters more in markets.
    2. VOLUME CONFIDENCE: a signal based on 20 articles is more reliable than 2.
       Confidence gets scaled: 0-5 articles → 50% cap, 6-15 → 75% cap, 16+ → 100%.
    3. SAMPLE SIZE: we return article_count so the UI can show 'based on X articles'.

    Roman Urdu: Nayi khabron ko zyada weight diya ja raha hai taake signal zyada fresh
    ho. Volume bhi dekha ja raha hai — 2 articles se jo signal bana, wo 20 articles se
    bane signal jaisa confident nahi ho sakta.
    """
    from datetime import datetime, timezone, timedelta
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT ticker, headline, sentiment, sentiment_score, published_at
        FROM articles
        WHERE sentiment IS NOT NULL
        ORDER BY ticker, published_at DESC
        """
    ).fetchall()
    conn.close()

    now = datetime.now(timezone.utc)
    ticker_data = {}

    for r in rows:
        tk = r["ticker"]
        if tk not in ticker_data:
            ticker_data[tk] = {"articles": []}
        # Parse published_at, handling missing/invalid gracefully
        try:
            pub = datetime.fromisoformat(r["published_at"])
            if pub.tzinfo is None:
                pub = pub.replace(tzinfo=timezone.utc)
            hours_ago = (now - pub).total_seconds() / 3600
        except Exception:
            hours_ago = 72  # assume old if we can't parse

        # Recency weight: exponential decay, halving every 24 hours
        weight = 2.0 ** (-hours_ago / 48)

        score = r["sentiment_score"] or 0.0
        if r["sentiment"] == "positive":
            weighted = score * weight
        elif r["sentiment"] == "negative":
            weighted = -score * weight
        else:
            weighted = 0

        ticker_data[tk]["articles"].append({
            "weight": weight,
            "weighted_score": weighted,
            "is_positive": r["sentiment"] == "positive",
            "is_negative": r["sentiment"] == "negative",
        })

    overview = []
    for tk, data in ticker_data.items():
        arts = data["articles"]
        n = len(arts)
        total_weight = sum(a["weight"] for a in arts) or 1
        total_weighted = sum(a["weighted_score"] for a in arts)
        net = total_weighted / total_weight

        # Volume-based confidence modifier
        if n >= 16:
            volume_factor = 1.0
        elif n >= 6:
            volume_factor = 0.75
        else:
            volume_factor = 0.5

        if net > 0.05:
            sig = "BUY"
        elif net < -0.05:
            sig = "SELL"
        else:
            sig = "HOLD"

        # Base confidence from net score magnitude, modified by volume
        base_conf = min(100, round(abs(net) * 100))
        confidence = min(100, round(base_conf * volume_factor))

        pos_count = sum(1 for a in arts if a["is_positive"])
        neg_count = sum(1 for a in arts if a["is_negative"])
        neu_count = n - pos_count - neg_count

        overview.append(
            {
                "ticker": tk,
                "articles": n,
                "net": round(net, 3),
                "signal": sig,
                "confidence": confidence,
                "positive": pos_count,
                "negative": neg_count,
                "neutral": neu_count,
            }
        )

    overview.sort(key=lambda x: x["ticker"])
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
        "signal, signal_confidence, url, image "
        f"FROM articles {where} ORDER BY published_at DESC LIMIT ?"
    )
    params.append(limit)

    conn = get_connection()
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return rows


# ---------------------------------------------------------------------------
# Events Calendar helpers — upcoming earnings dates
# ---------------------------------------------------------------------------

def init_earnings_table():
    """One row per (symbol, date). Stores scheduled earnings with the EPS estimate.
    Roman Urdu: Har stock ki aane wali earnings ki date yahan store hoti hai."""
    conn = get_connection()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS earnings (
            symbol       TEXT,
            date         TEXT,
            eps_estimate REAL,
            eps_actual   REAL,
            hour         TEXT,
            quarter      INTEGER,
            year         INTEGER,
            fetched_at   TEXT,
            PRIMARY KEY (symbol, date)
        )
        """
    )
    conn.commit()
    conn.close()


def save_earnings(rows):
    """Insert or overwrite earnings rows. Returns count written."""
    conn = get_connection()
    n = 0
    for r in rows:
        conn.execute(
            """
            INSERT OR REPLACE INTO earnings
                (symbol, date, eps_estimate, eps_actual, hour, quarter, year, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (r.get("symbol"), r.get("date"), r.get("eps_estimate"), r.get("eps_actual"),
             r.get("hour"), r.get("quarter"), r.get("year"), r.get("fetched_at")),
        )
        n += 1
    conn.commit()
    conn.close()
    return n


def get_earnings(date_from, date_to):
    """All earnings between two YYYY-MM-DD dates (inclusive)."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT symbol, date, eps_estimate FROM earnings "
        "WHERE date BETWEEN ? AND ? ORDER BY date",
        (date_from, date_to),
    ).fetchall()
    conn.close()
    return rows


# ---------------------------------------------------------------------------
# Phase 1a: Signal change tracker + sentiment trends
# ---------------------------------------------------------------------------

def init_history_table():
    """Stores snapshots of per-ticker signals so we can detect changes.
    Roman Urdu: Har pipeline run par ticker signals ka snapshot save hota hai,
    taake hum dekh saken ke kya badla hai."""
    conn = get_connection()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS signal_history (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker     TEXT,
            signal     TEXT,
            confidence INTEGER,
            articles   INTEGER,
            net        REAL,
            snapshot_at TEXT
        )
        """
    )
    conn.commit()
    conn.close()


def log_signal_snapshot(overview):
    """Save current ticker signals as a snapshot with timestamp.
    Call this after signal_engine.py runs."""
    now = datetime.now(timezone.utc).isoformat()
    conn = get_connection()
    for t in overview:
        conn.execute(
            "INSERT INTO signal_history (ticker, signal, confidence, articles, net, snapshot_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (t["ticker"], t["signal"], t["confidence"], t["articles"], t["net"], now),
        )
    conn.commit()
    conn.close()


def get_signal_changes():
    """
    Compare the latest two snapshots per ticker. Returns what changed.
    If a ticker has only 1 snapshot, returns its current state with no change info.
    Roman Urdu: Pichli do snapshots compare karta hai — konsa ticker BUY se HOLD
    hua, ya confidence up/down hua, etc.
    """
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT ticker, signal, confidence, articles, net, snapshot_at,
               ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY snapshot_at DESC) AS rn
        FROM signal_history
        """
    ).fetchall()
    conn.close()

    current = {}
    previous = {}
    for r in rows:
        if r["rn"] == 1:
            current[r["ticker"]] = r
        elif r["rn"] == 2:
            previous[r["ticker"]] = r

    changes = []
    for tk, cur in current.items():
        prev = previous.get(tk)
        entry = {
            "ticker": tk,
            "currentSignal": cur["signal"],
            "currentConf": cur["confidence"],
            "currentArticles": cur["articles"],
        }
        if prev:
            entry["previousSignal"] = prev["signal"]
            entry["previousConf"] = prev["confidence"]
            entry["previousArticles"] = prev["articles"]
            entry["changed"] = (
                cur["signal"] != prev["signal"] or
                abs(cur["confidence"] - prev["confidence"]) >= 10
            )
            entry["changeType"] = None
            if cur["signal"] != prev["signal"]:
                entry["changeType"] = f"{prev['signal']} → {cur['signal']}"
            elif cur["confidence"] - prev["confidence"] >= 10:
                entry["changeType"] = f"confidence +{cur['confidence'] - prev['confidence']}"
            elif prev["confidence"] - cur["confidence"] >= 10:
                entry["changeType"] = f"confidence {cur['confidence'] - prev['confidence']}"
        else:
            entry["changed"] = False
            entry["changeType"] = "new"
        changes.append(entry)

    changes.sort(key=lambda c: (
        0 if c.get("changeType") and "→" in c["changeType"] else
        1 if c.get("changeType") and "confidence" in c["changeType"] else 2,
        c["ticker"]
    ))
    return changes


def sentiment_trend(days=7):
    """
    Daily net sentiment per ticker for the last N days.
    Returns: {ticker: [{date: '2026-07-03', net: 0.45, articles: 5}, ...]}
    Roman Urdu: Har ticker ke liye roz ka sentiment trend — kya positive ho raha
    hai ya negative, kaise badal raha hai.
    """
    from datetime import datetime, timezone, timedelta
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT ticker, DATE(published_at) AS day,
               SUM(CASE WHEN sentiment='positive' THEN sentiment_score
                        WHEN sentiment='negative' THEN -sentiment_score ELSE 0 END) AS net_raw,
               COUNT(*) AS n
        FROM articles
        WHERE sentiment IS NOT NULL AND published_at >= ?
        GROUP BY ticker, DATE(published_at)
        ORDER BY ticker, day
        """,
        (cutoff,),
    ).fetchall()
    conn.close()

    trend = {}
    for r in rows:
        tk = r["ticker"]
        if tk not in trend:
            trend[tk] = []
        n = r["n"] or 1
        trend[tk].append({
            "date": r["day"],
            "net": round((r["net_raw"] or 0) / n, 3),
            "articles": r["n"],
        })
    return trend


def get_ticker_history(ticker):
    """Return all signal snapshots for one ticker, oldest first (for timeline chart)."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT signal, confidence, articles, net, snapshot_at "
        "FROM signal_history WHERE ticker = ? ORDER BY snapshot_at ASC",
        (ticker,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


_HIGH_TIER_SOURCES = ["reuters", "bloomberg", "wsj", "wall street", "financial times",
                      "cnbc", "marketwatch", "coindesk", "the block", "ft"]


def top_stories(limit=5):
    """Top stories by source credibility + recency. Perfect for 'Top Stories' section.
    Roman Urdu: Sab se bharosemand sources (Reuters, Bloomberg, etc.) ki taaza khabrein."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT ticker, headline, source, url, published_at, sentiment, sentiment_score "
        "FROM articles WHERE sentiment IS NOT NULL ORDER BY published_at DESC LIMIT 200"
    ).fetchall()
    conn.close()

    def score(row):
        s = (row["source"] or "").lower()
        credibility = 2 if any(k in s for k in _HIGH_TIER_SOURCES) else 1
        pub = row["published_at"] or ""
        return (credibility, pub)

    ranked = sorted(rows, key=score, reverse=True)
    return [
        {
            "ticker": r["ticker"],
            "headline": r["headline"],
            "source": r["source"] or "RSS",
            "url": r["url"],
            "sentiment": r["sentiment"],
            "score": r["sentiment_score"],
        }
        for r in ranked[:limit]
    ]


# ---------------------------------------------------------------------------
# Outcome Tracking — records price at signal time and checks if it was right
# ---------------------------------------------------------------------------

def init_price_tracking():
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS price_tracking (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker       TEXT NOT NULL UNIQUE,
            signal       TEXT NOT NULL,
            confidence   INTEGER,
            signal_time  TEXT NOT NULL,
            entry_price  REAL,
            latest_price REAL,
            outcome      TEXT DEFAULT 'pending',
            checked_at   TEXT,
            verified_at  TEXT
        )
    """)
    conn.commit()
    conn.close()


def save_price_entry(ticker, signal, confidence, entry_price):
    """Insert or update price tracking row for a ticker."""
    now = datetime.now(timezone.utc).isoformat()
    conn = get_connection()
    conn.execute("""
        INSERT INTO price_tracking (ticker, signal, confidence, signal_time, entry_price, checked_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(ticker) DO UPDATE SET
            signal=excluded.signal,
            confidence=excluded.confidence,
            entry_price=excluded.entry_price,
            checked_at=excluded.checked_at
    """, (ticker, signal, confidence, now, entry_price, now))
    conn.commit()
    conn.close()


def update_price_outcome(ticker, latest_price):
    """Check whether the signal was correct and update the row.
    Roman Urdu: Check karta hai ke price direction signal ke mutabiq tha ya nahi."""
    try:
        now = datetime.now(timezone.utc).isoformat()
        conn = get_connection()
        row = conn.execute(
            "SELECT signal, entry_price FROM price_tracking WHERE ticker = ?",
            (ticker,),
        ).fetchone()
        if not row:
            conn.close()
            return

        sig = row["signal"]
        entry = row["entry_price"]
        if not entry or not latest_price:
            conn.close()
            return

        change_pct = (latest_price - entry) / entry * 100
        # 0.5% threshold to filter noise
        if sig == "BUY":
            outcome = "correct" if change_pct >= 0.5 else ("incorrect" if change_pct <= -0.5 else "pending")
        elif sig == "SELL":
            outcome = "correct" if change_pct <= -0.5 else ("incorrect" if change_pct >= 0.5 else "pending")
        else:
            outcome = "neutral"

        # Only finalize if 24h+ have passed since signal_time
        signal_time = row.get("signal_time")
        if signal_time and outcome != "pending":
            try:
                st = datetime.fromisoformat(signal_time)
                if st.tzinfo is None:
                    st = st.replace(tzinfo=timezone.utc)
                hours_elapsed = (datetime.now(timezone.utc) - st).total_seconds() / 3600
                if hours_elapsed < 24:
                    outcome = "pending"
            except Exception:
                pass

        verified = now if outcome in ("correct", "incorrect", "neutral") else None
        conn.execute("""
            UPDATE price_tracking SET
                latest_price = ?, outcome = ?, checked_at = ?, verified_at = ?
            WHERE ticker = ?
        """, (latest_price, outcome, now, verified, ticker))
        conn.commit()
        conn.close()
    except Exception:
        pass  # outcome tracking should never crash the dashboard


def get_outcomes(tickers=None):
    """Return outcome dict for given tickers (or all)."""
    conn = get_connection()
    if tickers:
        placeholders = ",".join("?" for _ in tickers)
        rows = conn.execute(
            f"SELECT ticker, signal, confidence, entry_price, latest_price, outcome, checked_at, verified_at FROM price_tracking WHERE ticker IN ({placeholders})",
            tickers,
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT ticker, signal, confidence, entry_price, latest_price, outcome, checked_at, verified_at FROM price_tracking"
        ).fetchall()
    conn.close()
    return {r["ticker"]: dict(r) for r in rows}


# ---------------------------------------------------------------------------
# Auto-delete articles older than N days
# ---------------------------------------------------------------------------

def delete_old_articles(max_days=3):
    """Remove articles where published_at is older than max_days.
    Roman Urdu: Purane articles delete karta hai — sirf aakhri max_days din ke rakhta hai."""
    conn = get_connection()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=max_days)).isoformat()
    cur = conn.execute("DELETE FROM articles WHERE published_at < ?", (cutoff,))
    deleted = cur.rowcount
    conn.commit()
    conn.close()
    return deleted


def get_pipeline_status():
    """
    Return the most recently fetched article timestamp and total article count.
    Used to show 'last updated X ago' and warn if data is stale.
    Roman Urdu: Batata hai ke pipeline kab chali thi aur kitna data hai.
    """
    conn = get_connection()
    last = conn.execute(
        "SELECT fetched_at FROM articles ORDER BY fetched_at DESC LIMIT 1"
    ).fetchone()
    count = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    scored = conn.execute(
        "SELECT COUNT(*) FROM articles WHERE sentiment IS NOT NULL"
    ).fetchone()[0]
    conn.close()
    return {
        "last_fetched": last["fetched_at"] if last else None,
        "total_articles": count,
        "scored_articles": scored,
    }
