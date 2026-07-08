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
    "JPM": "#5b8def", "V": "#1a1f71", "BTC": "#f7931a", "ETH": "#627eea",
    "SOL": "#14f195", "XRP": "#23292f", "BNB": "#f3ba2f", "DOGE": "#c2a633",
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


@app.get("/api/dashboard")
def dashboard():
    conn = db.get_connection()

    # ---- signals (one per ticker that has an explanation) ----
    sig_rows = db.get_ticker_signals()
    signals = []
    for r in sig_rows:
        tk = r["ticker"]
        signals.append({
            "ticker": tk,
            "mono": tk[0],
            "brand": BRAND.get(tk, "#5b8def"),
            "event": "News Signal",
            "desc": _first_bullet(r["explanation"]),
            "dir": r["signal"] or "HOLD",
            "conf": int(r["confidence"] or 0),
            "time": _rel(r["updated_at"]),
        })
    signals.sort(key=lambda s: s["conf"], reverse=True)

    # ---- news feed (latest articles) ----
    news = []
    for r in db.get_articles(limit=40):
        news.append({
            "time": _rel(r["published_at"]),
            "source": r["source"] or "RSS",
            "headline": r["headline"],
            "ticker": r["ticker"],
            "tone": _tone(r["sentiment"]),
            "url": r["url"],
        })

    # ---- stats (only what we can compute honestly) ----
    total_articles = db.count_articles()
    sources = conn.execute(
        "SELECT COUNT(DISTINCT source) FROM articles WHERE source IS NOT NULL"
    ).fetchone()[0]
    high_conf = sum(1 for s in signals if s["conf"] >= 50)
    stats = {
        "signalsToday": len(signals),
        "highConf": high_conf,
        "newsProcessed": total_articles,
        "sources": sources,
        "accuracy": "N/A",  # honest: we have no ground-truth labels to measure this
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
        # NOTE: eventTypes (Earnings/M&A/etc.) is NOT returned — we don't classify events yet,
        # so the frontend keeps its placeholder donut for that one widget.
    }


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
    """Why-behind-the-signal: reuse the STORED bullets (no new LLM call) + top articles."""
    ticker = ticker.upper()
    conn = db.get_connection()
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

    # rank by credibility tier first, then recency; keep top 3
    ranked = sorted(arts, key=lambda a: (_tier(a["source"]), a["published_at"] or ""),
                    reverse=True)[:3]
    articles = [
        {"headline": a["headline"], "source": a["source"] or "RSS",
         "url": a["url"], "time": _rel(a["published_at"])}
        for a in ranked
    ]
    return {
        "ticker": ticker,
        "dir": (row["signal"] if row else "HOLD") or "HOLD",
        "conf": int(row["confidence"]) if row and row["confidence"] is not None else 0,
        "bullets": _bullets(row["explanation"] if row else ""),
        "articles": articles,
    }


@app.post("/api/ticker/{ticker}/regenerate")
def regenerate_ticker(ticker: str):
    """On-demand: ask the LLM for a FRESH explanation for one ticker, save it, return it.
    Lazy-imports the LLM libs so the display-only server still runs without them."""
    ticker = ticker.upper()
    try:
        from openai import OpenAI
        import llm_explain
        from config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL
    except Exception:
        return {"error": "LLM libraries not installed on this server."}
    if not LLM_API_KEY or LLM_API_KEY == "your_llm_key_here":
        return {"error": "No LLM API key configured in .env."}

    overview = {o["ticker"]: o for o in db.ticker_signal_overview()}
    info = overview.get(ticker)
    if not info:
        return {"error": "No signal exists for this ticker yet."}

    headlines = db.top_headlines_for_ticker(ticker, limit=8)
    try:
        client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)
        prompt = llm_explain.build_user_prompt(ticker, info["signal"], info["confidence"], headlines)
        resp = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[{"role": "system", "content": llm_explain.SYSTEM_PROMPT},
                      {"role": "user", "content": prompt}],
            temperature=0.4,  # a bit higher -> a genuinely fresh take
            max_tokens=180,
        )
        expl = resp.choices[0].message.content.strip()
    except Exception as e:
        return {"error": "LLM call failed: " + str(e)[:140]}

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
    sigmap = {r["ticker"]: r for r in db.get_ticker_signals()}

    by_date = defaultdict(list)
    for e in ern:
        sig = sigmap.get(e["symbol"])
        by_date[e["date"]].append({
            "ticker": e["symbol"],
            "epsEst": e["eps_estimate"],
            "dir": (sig["signal"] if sig else "HOLD") or "HOLD",
            "conf": int(sig["confidence"]) if sig and sig["confidence"] is not None else 0,
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


@app.get("/")
def index():
    return FileResponse(HTML_FILE)
