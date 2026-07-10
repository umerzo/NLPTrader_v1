"""
api.py — FastAPI backend that serves your REAL data to the HTML frontend.

This is the "binding" layer. Your whole Python pipeline (ingest → FinBERT → signal → LLM)
stays untouched and keeps writing to nlptrader.db. This file just READS that db and exposes
it as JSON at /api/dashboard, and serves the standalone HTML at /.
Roman Urdu: Saara pipeline waise ka waisa. Ye file sirf database ko JSON banati hai aur HTML
ko serve karti hai — frontend us JSON ko fetch karke real data dikhata hai.

Run with:  uvicorn api:app --reload
Then open: http://localhost:8000
"""
from datetime import datetime, timezone, date, timedelta
from collections import defaultdict

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

import db

app = FastAPI(title="NLPTrader API")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

HTML_FILE = "NLPTrader-standalone.html"

# Optional brand colours for nicer ticker badges; anything not listed falls back to blue.
BRAND = {
    "AAPL": "#c8cdd8", "MSFT": "#5b8def", "NVDA": "#76b900", "AMZN": "#ff9900",
    "GOOGL": "#4285f4", "META": "#4f93ff", "TSLA": "#e82127", "AVGO": "#cc0000",
    "JPM": "#5b8def", "V": "#1a1f71", "SPY": "#c8102e",
    "BTC": "#f7931a", "ETH": "#627eea", "SOL": "#14f195", "XRP": "#23292f",
    "BNB": "#f3ba2f", "ADA": "#0033ad", "DOGE": "#c2a633", "AVAX": "#e84142",
    "LINK": "#2a5ada", "DOT": "#e6007a", "SHIB": "#ff6600", "PEPE": "#00a300",
    "BONK": "#f7931a",
    "XAUUSD": "#d4af37", "XAGUSD": "#a8a9ad", "EURCHF": "#5b8def", "USDCNH": "#e60012",
}


def _rel(iso):
    """Turn a stored ISO timestamp into 'Xm ago' / 'Xh ago'."""
    try:
        t = datetime.fromisoformat(iso)
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
        secs = (datetime.now(timezone.utc) - t).total_seconds()
    except Exception:
        return ""
    if secs < 60:
        return "just now"
    if secs < 3600:
        return f"{int(secs // 60)}m ago"
    if secs < 86400:
        return f"{int(secs // 3600)}h ago"
    return f"{int(secs // 86400)}d ago"


def _first_bullet(explanation):
    """The LLM explanation is +/-/= bullet lines; take the first as a one-line description."""
    for line in (explanation or "").splitlines():
        line = line.strip()
        if line:
            return line.lstrip("+-=").strip()
    return "Signal generated from recent news"


def _tone(sentiment):
    return {"positive": "green", "negative": "red"}.get(sentiment, "gray")


def _stale_status(pipeline_status):
    """Return 'fresh', 'stale', or 'old' based on last fetch time."""
    last = pipeline_status.get("last_fetched")
    if not last:
        return "never"
    try:
        t = datetime.fromisoformat(last)
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
        hours = (datetime.now(timezone.utc) - t).total_seconds() / 3600
    except Exception:
        return "unknown"
    if hours < 6:
        return "fresh"
    if hours < 24:
        return "stale"
    return "old"


def _fetch_price(ticker):
    """Get current price via yfinance. Handles stocks, crypto (BTC-USD), forex (EURUSD=X).
    Returns (current_price, change_pct) or (None, None)."""
    # Map ticker to Yahoo Finance symbol format
    yahoo_map = {
        "XAUUSD": "GC=F",
        "XAGUSD": "SI=F",
        "EURUSD": "EURUSD=X", "GBPUSD": "GBPUSD=X",
        "USDJPY": "USDJPY=X", "USDCHF": "USDCHF=X",
        "AUDUSD": "AUDUSD=X", "USDCAD": "USDCAD=X",
        "NZDUSD": "NZDUSD=X", "EURGBP": "EURGBP=X",
        "EURJPY": "EURJPY=X", "GBPJPY": "GBPJPY=X",
        "EURCHF": "EURCHF=X", "USDCNH": "USDCNH=X",
    }
    # Crypto: append -USD
    crypto_suffix = ["BTC", "ETH", "SOL", "XRP", "BNB", "ADA", "DOGE",
                     "AVAX", "LINK", "DOT", "SHIB", "PEPE", "BONK"]
    try:
        import yfinance as yf
        if ticker in yahoo_map:
            sym = yahoo_map[ticker]
        elif ticker in crypto_suffix:
            sym = f"{ticker}-USD"
        else:
            sym = ticker  # stocks/ETFs as-is
        tk = yf.Ticker(sym)
        hist = tk.history(period="5d")
        if hist.empty or "Close" not in hist.columns:
            return None, None
        latest = float(hist["Close"].iloc[-1])
        prev = float(hist["Close"].iloc[-2]) if len(hist) >= 2 else latest
        change_pct = round((latest - prev) / prev * 100, 2) if prev else 0
        return round(latest, 4), change_pct
    except Exception:
        return None, None


@app.get("/api/dashboard")
def dashboard():
    conn = db.get_connection()

    # ---- cleanup: delete articles older than 3 days ----
    deleted = db.delete_old_articles(max_days=3)

    # ---- pipeline freshness ----
    pstatus = db.get_pipeline_status()
    stale = _stale_status(pstatus)

    # ---- signals (computed fresh from overview, explanation from stored LLM data) ----
    overview_map = {o["ticker"]: o for o in db.ticker_signal_overview()}
    sig_rows = db.get_ticker_signals()
    seen = set()

    # Initialise outcome tracking table
    db.init_price_tracking()

    # Build ticker → outcome map
    ticker_outcomes = db.get_outcomes()

    signals = []
    price_fetch_tickers = []

    for r in sig_rows:
        tk = r["ticker"]
        ov = overview_map.get(tk, {})
        sig = ov.get("signal", r["signal"]) or "HOLD"
        conf = ov.get("confidence") if ov.get("confidence") is not None else (r["confidence"] or 0)

        outcome = ticker_outcomes.get(tk, {})
        signals.append({
            "ticker": tk,
            "mono": tk[0],
            "brand": BRAND.get(tk, "#5b8def"),
            "event": "News Signal",
            "desc": _first_bullet(r["explanation"]),
            "dir": sig,
            "conf": int(conf),
            "sampleSize": ov.get("articles", 0),
            "positive": ov.get("positive", 0),
            "negative": ov.get("negative", 0),
            "neutral": ov.get("neutral", 0),
            "outcome": outcome.get("outcome", "pending"),
            "entryPrice": outcome.get("entry_price"),
            "latestPrice": outcome.get("latest_price"),
            "time": _rel(r["updated_at"]),
        })
        seen.add(tk)

        # Queue for price tracking if no outcome yet
        if outcome.get("outcome") in (None, "pending"):
            price_fetch_tickers.append(tk)

    # Add tickers that have overview data but no stored explanation yet
    for tk, ov in overview_map.items():
        if tk not in seen:
            outcome = ticker_outcomes.get(tk, {})
            signals.append({
                "ticker": tk,
                "mono": tk[0],
                "brand": BRAND.get(tk, "#5b8def"),
                "event": "News Signal",
                "desc": "No LLM explanation yet — run llm_explain.py",
                "dir": ov.get("signal", "HOLD"),
                "conf": int(ov.get("confidence", 0)),
                "sampleSize": ov.get("articles", 0),
                "positive": ov.get("positive", 0),
                "negative": ov.get("negative", 0),
                "neutral": ov.get("neutral", 0),
                "outcome": outcome.get("outcome", "pending"),
                "entryPrice": outcome.get("entry_price"),
                "latestPrice": outcome.get("latest_price"),
                "time": "",
            })
            if outcome.get("outcome") in (None, "pending"):
                price_fetch_tickers.append(tk)

    signals.sort(key=lambda s: s["conf"], reverse=True)

    # ---- fetch prices for tickers with no outcome yet ----
    for tk in price_fetch_tickers:
        price, change = _fetch_price(tk)
        if price is not None:
            existing = ticker_outcomes.get(tk)
            if existing and existing.get("entry_price"):
                db.update_price_outcome(tk, price)
            else:
                db.save_price_entry(tk, tk, 0, price)
            ticker_outcomes[tk] = db.get_outcomes([tk]).get(tk, {})

    # ---- news feed (latest articles) ----
    news = []
    for r in db.get_articles(limit=80):
        news.append({
            "time": _rel(r["published_at"]),
            "source": r["source"] or "RSS",
            "headline": r["headline"],
            "ticker": r["ticker"],
            "tone": _tone(r["sentiment"]),
            "url": r["url"],
            "image": r["image"] or "",
        })

    # ---- stats ----
    total_articles = pstatus["total_articles"]
    sources = conn.execute(
        "SELECT COUNT(DISTINCT source) FROM articles WHERE source IS NOT NULL"
    ).fetchone()[0]
    high_conf = sum(1 for s in signals if s["conf"] >= 50)
    outcomes = [s["outcome"] for s in signals if s["outcome"] in ("correct", "incorrect")]
    correct = sum(1 for o in outcomes if o == "correct")
    accuracy_pct = round(correct / len(outcomes) * 100) if outcomes else 0
    stats = {
        "signalsToday": len(signals),
        "highConf": high_conf,
        "newsProcessed": total_articles,
        "scoredArticles": pstatus["scored_articles"],
        "sources": sources,
        "dataAge": stale,
        "lastUpdated": _rel(pstatus["last_fetched"]) if pstatus["last_fetched"] else "never",
        "accuracy": f"{accuracy_pct}%" if accuracy_pct else "N/A",
        "trackedOutcomes": len(outcomes),
    }

    # ---- confidence distribution (from signal confidences) ----
    hi = sum(1 for s in signals if s["conf"] >= 80)
    md = sum(1 for s in signals if 50 <= s["conf"] < 80)
    lo = sum(1 for s in signals if s["conf"] < 50)
    tot = max(1, hi + md + lo)
    conf_dist = [
        {"label": "High (80-100%)", "pct": round(hi / tot * 100), "count": hi, "color": "#34d399"},
        {"label": "Medium (50-79%)", "pct": round(md / tot * 100), "count": md, "color": "#f7a23b"},
        {"label": "Low (0-49%)", "pct": round(lo / tot * 100), "count": lo, "color": "#f5556d"},
    ]

    # ---- top tickers by article volume ----
    top_rows = conn.execute(
        "SELECT ticker, COUNT(*) n FROM articles GROUP BY ticker ORDER BY n DESC LIMIT 5"
    ).fetchall()
    top_tickers = [
        {"ticker": r["ticker"], "mono": r["ticker"][0],
         "brand": BRAND.get(r["ticker"], "#5b8def"), "value": r["n"]}
        for r in top_rows
    ]

    conn.close()
    return {
        "signals": signals,
        "news": news,
        "stats": stats,
        "confDist": conf_dist,
        "topTickers": top_tickers,
    }


@app.get("/api/ticker/{ticker}/articles")
def ticker_articles(ticker: str):
    """Top 5 most-recent articles for a ticker (within last 3 days).
    Used by the frontend modal when a signal card is clicked."""
    ticker = ticker.upper()
    rows = db.get_articles(ticker=ticker, limit=5)
    cutoff = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
    return [
        {
            "headline": r["headline"],
            "source": r["source"] or "RSS",
            "url": r["url"] or "#",
            "sentiment": r["sentiment"] or "neutral",
            "score": r["sentiment_score"] or 0,
            "signal": r["signal"] or "HOLD",
            "time": _rel(r["published_at"]),
        }
        for r in rows
        if r["published_at"] and r["published_at"] >= cutoff
    ] or [
        {
            "headline": "No recent articles found for " + ticker,
            "source": "", "url": "#", "sentiment": "neutral",
            "score": 0, "signal": "HOLD", "time": "",
        }
    ]


# Rough source-credibility tiers (higher = more authoritative). Honest and simple —
# not a real credibility model, just a sensible ranking for "top supporting article".
_HIGH_TIER = ["reuters", "bloomberg", "wsj", "wall street", "financial times", " ft",
              "cnbc", "marketwatch", "coindesk", "the block"]


def _tier(source):
    s = (source or "").lower()
    return 2 if any(k in s for k in _HIGH_TIER) else 1


def _bullets(explanation):
    out = []
    for line in (explanation or "").splitlines():
        line = line.strip()
        if not line:
            continue
        m = line[0]
        if m == "+":
            mark, color = "▲", "#34d399"
        elif m == "-":
            mark, color = "▼", "#f5556d"
        else:
            mark, color = "●", "#aab0c2"
        out.append({"mark": mark, "color": color, "text": line.lstrip("+-=").strip()})
    return out


@app.get("/api/ticker/{ticker}")
def ticker_detail(ticker: str):
    """Why-behind-the-signal: bullets + top articles + sample size."""
    ticker = ticker.upper()
    conn = db.get_connection()

    overview_map = {o["ticker"]: o for o in db.ticker_signal_overview()}
    ov = overview_map.get(ticker, {})

    row = conn.execute(
        "SELECT signal, confidence, explanation FROM ticker_signals WHERE ticker = ?",
        (ticker,),
    ).fetchone()

    arts = conn.execute(
        "SELECT headline, source, url, published_at FROM articles WHERE ticker = ? "
        "ORDER BY published_at DESC LIMIT 30",
        (ticker,),
    ).fetchall()
    conn.close()

    ranked = sorted(arts, key=lambda a: (_tier(a["source"]), a["published_at"] or ""),
                    reverse=True)[:3]
    articles = [
        {"headline": a["headline"], "source": a["source"] or "RSS",
         "url": a["url"], "time": _rel(a["published_at"])}
        for a in ranked
    ]
    sig = ov.get("signal", (row["signal"] if row else "HOLD")) or "HOLD"
    conf = ov.get("confidence") if ov.get("confidence") is not None else (
        int(row["confidence"]) if row and row["confidence"] is not None else 0
    )
    return {
        "ticker": ticker,
        "dir": sig,
        "conf": conf,
        "sampleSize": ov.get("articles", 0),
        "bullets": _bullets(row["explanation"] if row else ""),
        "articles": articles,
    }


@app.post("/api/ticker/{ticker}/regenerate")
def regenerate_ticker(ticker: str):
    """On-demand: ask the LLM for a FRESH explanation for one ticker, save it, return it.
    Lazy-imports the LLM libs so the display-only server still runs without them."""
    ticker = ticker.upper()
    try:
        from llm_fallback import llm_complete
        import llm_explain
    except Exception:
        return {"error": "LLM libraries not installed on this server."}

    overview = {o["ticker"]: o for o in db.ticker_signal_overview()}
    info = overview.get(ticker)
    if not info:
        return {"error": "No signal exists for this ticker yet."}

    headlines = db.top_headlines_for_ticker(ticker, limit=8)
    prompt = llm_explain.build_user_prompt(ticker, info["signal"], info["confidence"], headlines)
    expl, provider = llm_complete(
        system_prompt=llm_explain.SYSTEM_PROMPT,
        user_prompt=prompt,
        max_tokens=180,
        temperature=0.4,
    )
    if expl is None:
        return {"error": "Both LLM providers (Groq, Gemini) failed."}

    db.init_ticker_table()
    db.save_ticker_explanation(ticker, info["signal"], info["confidence"], expl,
                               datetime.now(timezone.utc).isoformat())
    return ticker_detail(ticker)  # reuse: returns fresh bullets + articles


@app.get("/api/calendar")
def calendar_view(offset: int = 0):
    """A 6x7 month grid (offset months from now). Each earnings date carries the ticker's
    CURRENT signal so the calendar ties future catalysts to your live sentiment."""
    today = datetime.now(timezone.utc).date()
    # month = current month shifted by `offset`
    m0 = today.month - 1 + offset
    year = today.year + m0 // 12
    month = m0 % 12 + 1
    first = date(year, month, 1)

    # grid starts on the Sunday on/of the first of the month; 42 cells (6 weeks)
    start = first - timedelta(days=(first.weekday() + 1) % 7)
    cells = [start + timedelta(days=i) for i in range(42)]

    db.init_earnings_table()
    ern = db.get_earnings(cells[0].isoformat(), cells[-1].isoformat())
    overview_map = {o["ticker"]: o for o in db.ticker_signal_overview()}

    by_date = defaultdict(list)
    for e in ern:
        ov = overview_map.get(e["symbol"], {})
        by_date[e["date"]].append({
            "ticker": e["symbol"],
            "epsEst": e["eps_estimate"],
            "dir": ov.get("signal", "HOLD"),
            "conf": int(ov.get("confidence", 0)),
        })

    days = []
    for d in cells:
        iso = d.isoformat()
        days.append({
            "day": d.day,
            "iso": iso,
            "inMonth": d.month == month,
            "isToday": d == today,
            "events": by_date.get(iso, []),
        })

    return {
        "monthLabel": first.strftime("%B %Y"),
        "offset": offset,
        "weekdays": ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"],
        "days": days,
    }


@app.get("/api/history/{ticker}")
def ticker_history(ticker: str):
    """Signal history timeline for one ticker."""
    ticker = ticker.upper()
    h = db.get_ticker_history(ticker)
    return {"ticker": ticker, "history": h, "count": len(h)}


@app.get("/api/topstories")
def top_stories(limit: int = 5):
    """Top credibility-ranked headlines right now."""
    stories = db.top_stories(limit=limit)
    return {"stories": stories, "count": len(stories)}


@app.get("/api/changes")
def signal_changes():
    """What changed since the last pipeline run."""
    db.init_history_table()
    changes = db.get_signal_changes()
    changed = [c for c in changes if c.get("changed") or c.get("changeType") == "new"]
    return {"changes": changed, "total": len(changes), "changedCount": len(changed)}


@app.get("/api/trends")
def trends(days: int = 7):
    """Daily sentiment trends per ticker for the last N days."""
    return {"trends": db.sentiment_trend(days=days)}


@app.get("/api/status")
def pipeline_status():
    """Health check: data freshness, counts, staleness warning."""
    p = db.get_pipeline_status()
    stale = _stale_status(p)
    return {
        "status": "ok",
        "dataAge": stale,
        "lastFetched": p["last_fetched"],
        "lastFetchedRel": _rel(p["last_fetched"]) if p["last_fetched"] else "never",
        "totalArticles": p["total_articles"],
        "scoredArticles": p["scored_articles"],
        "message": (
            f"Data last fetched {_rel(p['last_fetched'])}. "
            f"{p['total_articles']} articles ({p['scored_articles']} scored)."
        ) if p["last_fetched"] else "No data yet — run the pipeline.",
    }


# Cached FinBERT model (loaded once on first scan)
_finbert = None


def _get_finbert():
    global _finbert
    if _finbert is None:
        from transformers import pipeline
        _finbert = pipeline(
            "sentiment-analysis", model="ProsusAI/finbert", truncation=True
        )
    return _finbert


@app.post("/api/scan/{ticker}")
def scan_ticker(ticker: str):
    """Run the full pipeline for ONE ticker: fetch fresh news → FinBERT → signal → LLM → report."""
    import time as _time
    import traceback

    ticker = ticker.upper()
    started = _time.time()
    try:
        # 1. Fetch fresh news from Finnhub (works for stocks; crypto/forex may return empty)
        try:
            from ingest import fetch_for_ticker
            articles = fetch_for_ticker(ticker)
        except Exception as e:
            return {"error": f"Fetch failed: {str(e)[:120]}"}
        new_count = 0
        if articles:
            new_count = db.save_articles(articles)
        else:
            # Fallback: use articles already in DB (crypto/forex ingested via category news)
            existing = db.get_articles(ticker=ticker, limit=20)
            if not existing:
                return {"error": f"No recent news found for {ticker} on Finnhub or in database."}
            articles = [dict(r) for r in existing]

        # 2. FinBERT — score any unscored articles for this ticker
        conn = db.get_connection()
        unscored = conn.execute(
            "SELECT id, headline, summary FROM articles WHERE ticker = ? AND sentiment IS NULL",
            (ticker,),
        ).fetchall()
        conn.close()
        if unscored:
            classifier = _get_finbert()
            for row in unscored:
                text = (row["headline"] or "") + ". " + (row["summary"] or "")
                text = text[:1000]
                result = classifier(text)[0]
                db.save_sentiment(
                    row["id"], result["label"].lower(), round(float(result["score"]), 4)
                )

        # 3. Generate per-article signals for this ticker
        conn = db.get_connection()
        unsignaled = conn.execute(
            "SELECT id, sentiment, sentiment_score FROM articles "
            "WHERE ticker = ? AND signal IS NULL AND sentiment IS NOT NULL",
            (ticker,),
        ).fetchall()
        conn.close()
        for row in unsignaled:
            s = (row["sentiment_score"] or 0.0) * 100
            sig = "BUY" if row["sentiment"] == "positive" else (
                "SELL" if row["sentiment"] == "negative" else "HOLD"
            )
            db.save_signal(row["id"], sig, round(s))

        # 4. Get weighted ticker overview
        overview = {o["ticker"]: o for o in db.ticker_signal_overview()}
        info = overview.get(ticker, {})

        # 5. Get articles for display + LLM
        conn = db.get_connection()
        art_rows = conn.execute(
            "SELECT headline, source, url, published_at FROM articles "
            "WHERE ticker = ? ORDER BY published_at DESC LIMIT 8",
            (ticker,),
        ).fetchall()
        conn.close()
        headlines = [{"headline": r["headline"], "sentiment": ""} for r in art_rows]
        expl = ""
        try:
            from llm_fallback import llm_complete
            from llm_explain import build_user_prompt, SYSTEM_PROMPT
            prompt = build_user_prompt(
                ticker, info.get("signal", "HOLD"), int(info.get("confidence", 0)), headlines,
            )
            expl, _ = llm_complete(
                system_prompt=SYSTEM_PROMPT,
                user_prompt=prompt,
                max_tokens=180,
                temperature=0.4,
            )
        except Exception:
            pass

        db.init_ticker_table()
        if expl:
            db.save_ticker_explanation(
                ticker, info.get("signal", "HOLD"), int(info.get("confidence", 0)),
                expl, datetime.now(timezone.utc).isoformat(),
            )

        db.init_history_table()
        if info:
            db.log_signal_snapshot([info])

        elapsed = round(_time.time() - started, 1)
        return {
            "ticker": ticker,
            "dir": info.get("signal", "HOLD"),
            "conf": int(info.get("confidence", 0)),
            "sampleSize": info.get("articles", 0),
            "newArticles": new_count,
            "totalArticles": len(articles),
            "elapsed": elapsed,
            "bullets": _bullets(expl) if expl else [],
            "articles": [
                {"headline": r["headline"], "source": r["source"] or "RSS",
                 "url": r["url"] or "#", "time": _rel(r["published_at"])}
                for r in art_rows[:3]
            ],
            "confidence": int(info.get("confidence", 0)),
            "articlesCount": info.get("articles", 0),
        }
    except Exception as e:
        return {"error": f"Scan failed: {traceback.format_exc()[:500]}"}


# ---------------------------------------------------------------------------
# Technical Analysis — fetch OHLCV, calculate indicators, LLM verdict
# ---------------------------------------------------------------------------

def _calc_sma(data, window):
    if len(data) < window:
        return None
    return round(sum(data[-window:]) / window, 2)

def _calc_ema(data, window):
    if len(data) < window:
        return None
    multiplier = 2 / (window + 1)
    ema = sum(data[:window]) / window
    for price in data[window:]:
        ema = (price - ema) * multiplier + ema
    return round(ema, 2)

def _calc_rsi(data, window=14):
    if len(data) < window + 1:
        return None
    gains, losses = [], []
    for i in range(len(data) - window, len(data)):
        change = data[i] - data[i-1]
        gains.append(max(change, 0))
        losses.append(max(-change, 0))
    avg_gain = sum(gains) / window
    avg_loss = sum(losses) / window
    if avg_loss == 0:
        return 100
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 1)

def _calc_macd(data, fast=12, slow=26, signal=9):
    if len(data) < slow:
        return None, None, None
    ema_fast = _calc_ema(data, fast)
    ema_slow = _calc_ema(data, slow)
    if ema_fast is None or ema_slow is None:
        return None, None, None
    macd_line = round(ema_fast - ema_slow, 2)
    return macd_line, 0, 0  # simplified for LLM

def _calc_support_resistance(highs, lows, window=30):
    if len(highs) < window * 2:
        return [], []
    recent_highs = highs[-window:]
    recent_lows = lows[-window:]
    resistance = sorted([round(max(recent_highs[i:i+5]), 2) for i in range(0, len(recent_highs)-4)], reverse=True)[:5]
    support = sorted([round(min(recent_lows[i:i+5]), 2) for i in range(0, len(recent_lows)-4)])[:5]
    return support, resistance


def _calculate_trade_setup(current_price, support_levels, resistance_levels, rsi):
    """Determine a trade setup (entry, SL, TPs, R:R) from indicators. Returns None if no clear setup."""
    if not support_levels or not resistance_levels:
        return None
    nearest_support = max([s for s in support_levels if s < current_price], default=None)
    nearest_resistance = min([r for r in resistance_levels if r > current_price], default=None)
    if nearest_support is None or nearest_resistance is None:
        return None
    rng = nearest_resistance - nearest_support
    if rng <= 0:
        return None
    pos = (current_price - nearest_support) / rng

    if rsi is not None and rsi < 45 and pos < 0.4:
        direction = "BUY"
        entry = round(current_price, 2)
        sl = round(nearest_support - rng * 0.15, 2)
        tp1 = round(nearest_resistance, 2)
        tp2 = round(nearest_resistance + rng * 0.3, 2)
        tp3 = round(nearest_resistance + rng * 0.6, 2)
    elif rsi is not None and rsi > 55 and pos > 0.6:
        direction = "SELL"
        entry = round(current_price, 2)
        sl = round(nearest_resistance + rng * 0.15, 2)
        tp1 = round(nearest_support, 2)
        tp2 = round(nearest_support - rng * 0.3, 2)
        tp3 = round(nearest_support - rng * 0.6, 2)
    else:
        return None
    risk = round(abs(entry - sl), 2)
    reward = round(abs(tp1 - entry), 2)
    return {
        "direction": direction,
        "entry": entry,
        "stop_loss": sl,
        "take_profit_1": tp1,
        "take_profit_2": tp2,
        "take_profit_3": tp3,
        "rr_ratio": round(reward / risk, 2) if risk > 0 else 0,
    }


def _generate_ta_chart(full_hist, display_hist, ticker, timeframe, support_levels, resistance_levels, trade_setup=None):
    """Professional chart: zoomed candles, Bollinger Bands, Fibonacci, multiple S/R, RSI, Volume."""
    import os
    try:
        import mplfinance as mpf
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        import pandas as pd
        import numpy as np

        n_display = len(display_hist)
        df = display_hist.copy()
        df.columns = [c.capitalize() for c in df.columns]

        # Full data for accurate indicator calculations
        full_closes = full_hist['Close'].values

        # --- Bollinger Bands (20,2) ---
        bb_sma = pd.Series(full_closes).rolling(20).mean()
        bb_std = pd.Series(full_closes).rolling(20).std()
        bb_upper = bb_sma + 2 * bb_std
        bb_lower = bb_sma - 2 * bb_std

        # --- SMA / EMA ---
        sma20 = pd.Series(full_closes).rolling(20).mean()
        ema12 = pd.Series(full_closes).ewm(span=12, adjust=False).mean()
        ema26 = pd.Series(full_closes).ewm(span=26, adjust=False).mean()

        # --- RSI ---
        rsi_full = pd.Series(full_closes).rolling(50).apply(
            lambda x: _calc_rsi(x.tolist()) if len(x) == 50 else None, raw=False
        )

        # Slice all indicators to display range
        sma20_d = sma20.iloc[-n_display:]
        ema12_d = ema12.iloc[-n_display:]
        ema26_d = ema26.iloc[-n_display:]
        bbu_d = bb_upper.iloc[-n_display:]
        bbl_d = bb_lower.iloc[-n_display:]
        rsi_d = rsi_full.iloc[-n_display:]

        # --- Build addplots ---
        apds = []
        # Bollinger Bands (upper/lower)
        apds.append(mpf.make_addplot(bbu_d, color='#ff6b6b', width=0.5, alpha=0.4))
        apds.append(mpf.make_addplot(bbl_d, color='#ff6b6b', width=0.5, alpha=0.4))
        # SMA 20
        apds.append(mpf.make_addplot(sma20_d, color='#f7a23b', width=0.8))
        # EMA 12 (faster)
        apds.append(mpf.make_addplot(ema12_d, color='#5b8def', width=0.7))
        # EMA 26 (slower)
        apds.append(mpf.make_addplot(ema26_d, color='#c084fc', width=0.7, alpha=0.7))
        # RSI on panel 2
        apds.append(mpf.make_addplot(rsi_d, panel=2, color='#a78bfa', width=0.8, ylabel='RSI'))

        fig, axes = mpf.plot(
            df,
            type='candle',
            volume=True,
            addplot=apds,
            style='charles',
            figsize=(18, 11),
            returnfig=True,
            panel_ratios=(4, 1, 1),
            tight_layout=True,
            warn_too_much_data=2000,
        )

        # --- Fibonacci Retracement ---
        swing_high = df['High'].max()
        swing_low = df['Low'].min()
        fib_pcts = [0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0]
        fib_labels = ['0%', '23.6%', '38.2%', '50%', '61.8%', '78.6%', '100%']
        for pct, lbl in zip(fib_pcts, fib_labels):
            price = swing_low + (swing_high - swing_low) * pct
            axes[0].axhline(y=price, color='#f7931a', linestyle='--', linewidth=0.5, alpha=0.35)
            axes[0].text(df.index[-1], price, f'  {lbl}', color='#f7931a', fontsize=7, va='center', alpha=0.8)

        # --- Support & Resistance (up to 5 each) ---
        for level in support_levels[:5]:
            axes[0].axhline(y=level, color='#34d399', linestyle='--', linewidth=0.7, alpha=0.7)
            axes[0].text(df.index[-1], level, f'  S:{level}', color='#34d399', fontsize=7, va='center')
        for level in resistance_levels[:5]:
            axes[0].axhline(y=level, color='#f5556d', linestyle='--', linewidth=0.7, alpha=0.7)
            axes[0].text(df.index[-1], level, f'  R:{level}', color='#f5556d', fontsize=7, va='center')

        # --- Trade Setup (Entry, SL, TPs) ---
        if trade_setup:
            ts = trade_setup
            is_long = ts["direction"] == "BUY"
            clr_entry = '#34d399' if is_long else '#f5556d'
            clr_sl = '#f5556d' if is_long else '#34d399'
            clr_tp = '#34d399' if is_long else '#f5556d'
            last_idx = df.index[-1]

            # Entry line (thick solid)
            axes[0].axhline(y=ts["entry"], color=clr_entry, linewidth=2.0, alpha=0.9)
            axes[0].text(last_idx, ts["entry"], f'  ENTRY {ts["entry"]}',
                         color=clr_entry, fontsize=9, fontweight='bold', va='center',
                         bbox=dict(boxstyle='round,pad=0.15', facecolor='#0f1123', edgecolor=clr_entry, alpha=0.8))

            # SL line (thick solid, different color)
            axes[0].axhline(y=ts["stop_loss"], color=clr_sl, linewidth=1.5, alpha=0.8, linestyle='--')
            axes[0].text(last_idx, ts["stop_loss"], f'  SL {ts["stop_loss"]}',
                         color=clr_sl, fontsize=8, fontweight='bold', va='center',
                         bbox=dict(boxstyle='round,pad=0.15', facecolor='#0f1123', edgecolor=clr_sl, alpha=0.8))

            # TP lines (dashed)
            for label, val in [("TP1", ts["take_profit_1"]), ("TP2", ts["take_profit_2"]), ("TP3", ts["take_profit_3"])]:
                if val:
                    axes[0].axhline(y=val, color=clr_tp, linewidth=1.0, alpha=0.6, linestyle=':')
                    axes[0].text(last_idx, val, f'  {label} {val}',
                                 color=clr_tp, fontsize=7, va='center',
                                 bbox=dict(boxstyle='round,pad=0.1', facecolor='#0f1123', edgecolor=clr_tp, alpha=0.6))

            # Risk/Reward label
            rr_display = f'R:R 1:{ts["rr_ratio"]}'
            axes[0].text(0.02, 0.96, rr_display, transform=axes[0].transAxes,
                         fontsize=11, fontweight='bold', color='white',
                         bbox=dict(boxstyle='round,pad=0.3', facecolor='#1a1d3a', edgecolor='#a78bfa', alpha=0.9))

            # Direction label
            dir_label = '▲ LONG' if is_long else '▼ SHORT'
            axes[0].text(0.02, 0.90, dir_label, transform=axes[0].transAxes,
                         fontsize=12, fontweight='bold', color=clr_entry,
                         bbox=dict(boxstyle='round,pad=0.3', facecolor='#1a1d3a', edgecolor=clr_entry, alpha=0.9))

            # Shade risk zone (Entry → SL)
            y1 = min(ts["entry"], ts["stop_loss"])
            y2 = max(ts["entry"], ts["stop_loss"])
            axes[0].axhspan(y1, y2, xmin=0.85, xmax=1.0, color=clr_sl, alpha=0.08)

            # Shade reward zone (Entry → TP1)
            y1_r = min(ts["entry"], ts["take_profit_1"])
            y2_r = max(ts["entry"], ts["take_profit_1"])
            axes[0].axhspan(y1_r, y2_r, xmin=0.85, xmax=1.0, color=clr_tp, alpha=0.08)

        # --- RSI reference lines ---
        if len(axes) > 2:
            axes[2].axhline(y=70, color='#f5556d', linestyle=':', linewidth=0.5, alpha=0.5)
            axes[2].axhline(y=30, color='#34d399', linestyle=':', linewidth=0.5, alpha=0.5)
            axes[2].axhline(y=50, color='#aab0c2', linestyle=':', linewidth=0.3, alpha=0.3)
            axes[2].set_ylabel('RSI')

        # --- Title ---
        ts_tag = f'  |  {trade_setup["direction"]} 1:{trade_setup["rr_ratio"]}' if trade_setup else ''
        axes[0].set_title(
            f'{ticker} · {timeframe.upper()} · {n_display}c'
            f'  |  BB(20,2)  |  Fib  |  RSI{ts_tag}',
            color='white', fontsize=13, fontweight='bold'
        )

        # --- Dark theme ---
        for ax in axes:
            ax.set_facecolor('#0f1123')
            ax.tick_params(colors='#aab0c2')
            for spine in ax.spines.values():
                spine.set_color('#1a1d3a')

        fig.patch.set_facecolor('#0f1123')

        # Save to file
        out = os.path.join(os.path.dirname(__file__), "ta_chart_temp.png")
        fig.savefig(out, format='png', dpi=120, facecolor=fig.get_facecolor())
        plt.close(fig)
        return out
    except Exception as e:
        print(f"[chart_gen] Failed: {e}")
        return None


@app.post("/api/technical-analysis")
def technical_analysis(body: dict = None):
    """
    Run technical analysis for a ticker on a given timeframe.
    Returns OHLCV data for charting + calculated indicators + LLM analysis.

    Request:  {"ticker": "AAPL", "timeframe": "1h"}
    Timeframes: 15m, 1h, 4h, 1D
    """
    import json, traceback, time as _time
    from datetime import datetime, timezone, timedelta

    if body is None:
        return {"error": "Request body required with 'ticker' and 'timeframe'"}
    ticker = body.get("ticker", "").upper().strip()
    timeframe = body.get("timeframe", "1h")

    if not ticker:
        return {"error": "Ticker is required"}

    started = _time.time()

    # Map timeframe to yfinance interval + period
    interval_map = {"15m": "15m", "1h": "1h", "4h": "1h", "1D": "1d"}
    period_map = {"15m": "5d", "1h": "1mo", "4h": "1mo", "1D": "6mo"}
    agg_map = {"4h": 4}  # aggregate every N hours

    interval = interval_map.get(timeframe, "1h")
    period = period_map.get(timeframe, "1mo")
    agg_hours = agg_map.get(timeframe, 1)

    try:
        import yfinance as yf

        # Map ticker for yfinance (same as _fetch_price)
        yahoo_map = {
            "XAUUSD": "GC=F", "XAGUSD": "SI=F",
            "EURUSD": "EURUSD=X", "GBPUSD": "GBPUSD=X",
            "USDJPY": "USDJPY=X", "USDCHF": "USDCHF=X",
            "AUDUSD": "AUDUSD=X", "USDCAD": "USDCAD=X",
            "NZDUSD": "NZDUSD=X", "EURGBP": "EURGBP=X",
            "EURJPY": "EURJPY=X", "GBPJPY": "GBPJPY=X",
            "EURCHF": "EURCHF=X", "USDCNH": "USDCNH=X",
        }
        crypto_list = ["BTC", "ETH", "SOL", "XRP", "BNB", "ADA", "DOGE",
                       "AVAX", "LINK", "DOT", "SHIB", "PEPE", "BONK"]
        if ticker in yahoo_map:
            sym = yahoo_map[ticker]
        elif ticker in crypto_list:
            sym = f"{ticker}-USD"
        else:
            sym = ticker

        tk = yf.Ticker(sym)
        hist = tk.history(period=period, interval=interval)

        if hist.empty or "Close" not in hist.columns:
            return {"error": f"No price data found for {ticker}"}

        # Aggregate 1h → 4h if needed
        if agg_hours > 1 and interval == "1h":
            hist = hist.resample(f"{agg_hours}h").agg({
                "Open": "first", "High": "max", "Low": "min",
                "Close": "last", "Volume": "sum"
            }).dropna()

        # Build OHLCV for chart
        ohlcv = []
        times = []
        for idx, row in hist.iterrows():
            ts = int(idx.timestamp())
            ohlcv.append({
                "time": ts,
                "open": round(float(row["Open"]), 2),
                "high": round(float(row["High"]), 2),
                "low": round(float(row["Low"]), 2),
                "close": round(float(row["Close"]), 2),
                "volume": int(row["Volume"]) if "Volume" in row else 0,
            })
            times.append(ts)

        closes = [float(c["close"]) for c in ohlcv]
        highs = [float(c["high"]) for c in ohlcv]
        lows = [float(c["low"]) for c in ohlcv]
        current_price = closes[-1] if closes else 0
        prev_close = closes[-2] if len(closes) >= 2 else current_price
        change_pct = round((current_price - prev_close) / prev_close * 100, 2) if prev_close else 0

        # Calculate indicators
        sma_20 = _calc_sma(closes, min(20, len(closes)))
        ema_12 = _calc_ema(closes, min(12, len(closes)))
        ema_26 = _calc_ema(closes, min(26, len(closes)))
        rsi = _calc_rsi(closes)
        macd_line, macd_signal, macd_hist = _calc_macd(closes)
        support, resistance = _calc_support_resistance(highs, lows)

        indicators = {
            "sma_20": sma_20,
            "ema_12": ema_12,
            "ema_26": ema_26,
            "rsi": rsi,
            "macd": macd_line,
            "support_levels": support,
            "resistance_levels": resistance,
            "current_price": round(current_price, 2),
            "change_pct": change_pct,
            "high_52w": round(max(highs), 2),
            "low_52w": round(min(lows), 2),
        }

        # Calculate trade setup (entry, SL, TP levels)
        trade_setup = _calculate_trade_setup(current_price, support, resistance, rsi)

        # Zoom in: pass only last ~90 bars to chart for visible candle sizes
        chart_bars = 90
        if len(hist) > chart_bars:
            chart_hist = hist.iloc[-chart_bars:].copy()
        else:
            chart_hist = hist.copy()
        chart_file = _generate_ta_chart(hist, chart_hist, ticker, timeframe, support, resistance, trade_setup)

        # LLM Analysis
        analysis_text = ""
        verdict = "NEUTRAL"
        confidence = 0
        entry_zone = ""
        stop_loss = ""
        take_profit = ""

        try:
            from llm_fallback import llm_complete
            recent = ohlcv[-20:] if len(ohlcv) >= 20 else ohlcv
            price_summary = "\n".join(
                f"  [{i+1}] O:{c['open']} H:{c['high']} L:{c['low']} C:{c['close']} V:{c['volume']}"
                for i, c in enumerate(recent)
            )

            prompt = (
                f"You are a senior institutional-grade technical analyst. Analyze {ticker} on the {timeframe} timeframe.\n\n"
                f"Current Price: ${current_price}\n"
                f"Change: {change_pct}%\n\n"
                f"Technical Indicators:\n"
                f"- SMA(20): {sma_20}\n"
                f"- EMA(12): {ema_12}\n"
                f"- EMA(26): {ema_26}\n"
                f"- RSI(14): {rsi}\n"
                f"- MACD: {macd_line}\n"
                f"- Support Levels: {support}\n"
                f"- Resistance Levels: {resistance}\n\n"
                f"Recent Price Action (last {len(recent)} candles):\n{price_summary}\n\n"
                f"Provide a sharp, professional technical analysis in plain text. Cover:\n"
                f"1. Market Structure & Trend\n"
                f"2. Key Indicator Signals\n"
                f"3. Clear Verdict: BUY / SELL / NEUTRAL (and why)\n"
                f"4. Confidence Level (0-100)\n"
                f"5. Entry Zone, Stop Loss, Take Profit levels\n"
                f"6. Risk Factors\n\n"
                f"If the setup is unclear or risky, say 'NOT WORTH IT' and explain why.\n"
                f"Be honest — don't force a signal if there isn't one."
            )

            analysis_text, llm_provider = llm_complete(
                system_prompt="You are a professional technical analyst. Output only the analysis, no markdown formatting.",
                user_prompt=prompt,
                max_tokens=500,
                temperature=0.3,
            )
            if analysis_text:
                text_upper = analysis_text.upper()
                if "BUY" in text_upper and "SELL" not in text_upper.split("BUY")[0]:
                    verdict = "BUY"
                elif "SELL" in text_upper:
                    verdict = "SELL"
                elif "NOT WORTH IT" in text_upper:
                    verdict = "NEUTRAL"
            else:
                analysis_text = f"LLM unavailable — {llm_provider}"

        except Exception as e:
            analysis_text = f"LLM analysis unavailable: {str(e)[:100]}"

        elapsed = round(_time.time() - started, 1)

        cache_buster = int(_time.time() * 1000)
        return {
            "ticker": ticker,
            "timeframe": timeframe,
            "current_price": round(current_price, 2),
            "change_pct": change_pct,
            "indicators": indicators,
            "trade_setup": trade_setup,
            "analysis": analysis_text,
            "verdict": verdict,
            "confidence": confidence,
            "entry_zone": entry_zone,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "chart_url": f"/ta_chart_temp.png?t={cache_buster}" if chart_file else None,
            "elapsed": elapsed,
        }

    except Exception as e:
        return {"error": f"Technical analysis failed: {traceback.format_exc()[:500]}"}


@app.get("/ta_chart_temp.png")
def serve_ta_chart():
    import os
    path = os.path.join(os.path.dirname(__file__), "ta_chart_temp.png")
    if os.path.exists(path):
        return FileResponse(path, media_type="image/png")
    return {"error": "No chart available"}


@app.get("/")
def index():
    return FileResponse(HTML_FILE)
