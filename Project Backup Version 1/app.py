"""
app.py — Step 5: the NLPTrader dashboard (Streamlit), polished edition.

Streamlit re-runs this whole file top-to-bottom every time a filter changes. That single
fact is the entire mental model.
Roman Urdu: Streamlit poori script dobara chalata hai jab bhi filter badle — isi liye code
seedha upar se neeche hai, koi alag event/button logic nahi.

Run with:   streamlit run app.py
"""
import sys
import subprocess

import pandas as pd
import streamlit as st

from db import get_ticker_signals, get_articles, sentiment_summary, count_articles
from config import TICKERS

# ---------------------------------------------------------------- page setup
st.set_page_config(page_title="NLPTrader", page_icon="📈", layout="wide")

# All the visual polish lives in this one CSS block: gradient title, fade-in cards,
# hover lift, and animated confidence bars. Streamlit lets us inject raw CSS once.
st.markdown(
    """
    <style>
      @keyframes rise {from {opacity:0; transform:translateY(14px);} to {opacity:1; transform:none;}}
      @keyframes grow {from {width:0;} }
      @keyframes shine {0%{background-position:-200px 0;} 100%{background-position:200px 0;}}

      .hero {font-size:40px;font-weight:900;letter-spacing:-1px;
             background:linear-gradient(90deg,#3b6fd6,#7c3aed,#16a34a);
             -webkit-background-clip:text;background-clip:text;color:transparent;
             background-size:200% auto;animation:shine 6s linear infinite;}
      .sub {color:#8b93a3;margin-top:-6px;font-size:14px;}

      .grid {display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:14px;}
      .card {background:rgba(130,130,150,0.07);border:1px solid rgba(130,130,150,0.18);
             border-radius:16px;padding:16px 18px;animation:rise .5s ease both;
             transition:transform .18s ease, box-shadow .18s ease, border-color .18s;}
      .card:hover {transform:translateY(-4px);box-shadow:0 10px 28px rgba(0,0,0,0.28);
                   border-color:rgba(130,130,150,0.4);}
      .cardtop {display:flex;justify-content:space-between;align-items:center;}
      .tk {font-size:21px;font-weight:800;letter-spacing:.5px;}
      .badge {padding:3px 13px;border-radius:20px;font-weight:700;font-size:13px;color:#fff;}
      .BUY {background:#16a34a;} .SELL {background:#dc2626;} .HOLD {background:#6b7280;}
      .muted {color:#8b93a3;font-size:12px;margin:6px 0 8px;}

      .bar {height:8px;border-radius:8px;background:rgba(130,130,150,0.18);overflow:hidden;}
      .fill {height:100%;border-radius:8px;animation:grow 1s ease both;}
      .fill.BUY {background:linear-gradient(90deg,#16a34a,#4ade80);}
      .fill.SELL {background:linear-gradient(90deg,#dc2626,#f87171);}
      .fill.HOLD {background:linear-gradient(90deg,#6b7280,#9ca3af);}

      .bullets {margin-top:12px;display:flex;flex-direction:column;gap:6px;}
      .b {font-size:13.5px;line-height:1.35;display:flex;gap:7px;align-items:flex-start;}
      .b .m {font-weight:800;width:14px;flex-shrink:0;}
      .pos .m {color:#16a34a;} .neg .m {color:#dc2626;} .neu .m {color:#9ca3af;}
    </style>
    """,
    unsafe_allow_html=True,
)

SENT_COLOR = {"positive": "#16a34a", "negative": "#dc2626", "neutral": "#9ca3af"}


# ---------------------------------------------------------------- helpers
def parse_bullets(text):
    """Turn the LLM's '+ / - / =' lines into (css_class, marker, words) tuples.
    Old long explanations (no markers) still render as plain neutral lines.
    Roman Urdu: LLM ki +/-/= lines ko parse karke rang aur icon de dete hain."""
    out = []
    for line in (text or "").splitlines():
        line = line.strip()
        if not line:
            continue
        if line[0] == "+":
            out.append(("pos", "▲", line[1:].strip()))
        elif line[0] == "-":
            out.append(("neg", "▼", line[1:].strip()))
        elif line[0] == "=":
            out.append(("neu", "●", line[1:].strip()))
        else:
            out.append(("neu", "●", line))
    return out[:3]


def run_pipeline():
    """Run the four pipeline scripts in order, showing live progress.
    Roman Urdu: Chaaron scripts tarteeb se chalti hain aur progress live nazar aati hai."""
    steps = [
        ("Fetching fresh news", "main.py"),
        ("Scoring sentiment (FinBERT)", "sentiment.py"),
        ("Generating signals", "signal_engine.py"),
        ("Writing LLM explanations", "llm_explain.py"),
    ]
    with st.status("Refreshing data…", expanded=True) as status:
        for label, script in steps:
            st.write(f"▶ {label}…")
            result = subprocess.run(
                [sys.executable, script], capture_output=True, text=True
            )
            if result.returncode != 0:
                status.update(label=f"Failed at: {label}", state="error")
                st.code((result.stderr or result.stdout)[-1500:])
                return False
        status.update(label="Done — data refreshed!", state="complete")
    return True


# ---------------------------------------------------------------- header + sidebar
st.markdown("<div class='hero'>📈 NLPTrader</div>", unsafe_allow_html=True)
st.markdown(
    "<div class='sub'>News → sentiment → evidence-grounded signals · "
    "decision-support only, not financial advice</div>",
    unsafe_allow_html=True,
)
st.write("")

st.sidebar.header("⚙️ Controls")
if st.sidebar.button("🔄 Refresh data", width="stretch",
                     help="Re-runs the whole pipeline: news → sentiment → signal → explanation"):
    if run_pipeline():
        st.rerun()

st.sidebar.divider()
st.sidebar.header("🔎 Filters")
ticker_choice = st.sidebar.selectbox("Ticker", ["All"] + TICKERS)
sentiment_choice = st.sidebar.selectbox("Sentiment", ["All", "positive", "neutral", "negative"])
search = st.sidebar.text_input("Search headlines", "")

# ---------------------------------------------------------------- KPI row
counts = sentiment_summary()
c1, c2, c3, c4 = st.columns(4)
c1.metric("📰 Articles", count_articles())
c2.metric("🟢 Positive", counts.get("positive", 0))
c3.metric("⚪ Neutral", counts.get("neutral", 0))
c4.metric("🔴 Negative", counts.get("negative", 0))
st.divider()

# ---------------------------------------------------------------- signal cards
st.subheader("Signal overview")
with st.spinner("Loading signals…"):
    signals = get_ticker_signals()

if ticker_choice != "All":
    signals = [s for s in signals if s["ticker"] == ticker_choice]

if not signals:
    st.info("No ticker signals yet. Run `python signal_engine.py` then `python llm_explain.py`, "
            "or hit 🔄 Refresh data.")
else:
    cards = []
    for i, row in enumerate(signals):
        sig = row["signal"] or "HOLD"
        conf = min(int(row["confidence"] or 0), 100)
        bullets_html = "".join(
            f"<div class='b {cls}'><span class='m'>{mark}</span><span>{txt}</span></div>"
            for cls, mark, txt in parse_bullets(row["explanation"])
        ) or "<div class='b neu'><span class='m'>●</span><span>No explanation yet.</span></div>"
        cards.append(
            f"<div class='card' style='animation-delay:{i*0.04:.2f}s'>"
            f"<div class='cardtop'><span class='tk'>{row['ticker']}</span>"
            f"<span class='badge {sig}'>{sig}</span></div>"
            f"<div class='muted'>confidence {conf}/100</div>"
            f"<div class='bar'><div class='fill {sig}' style='width:{conf}%'></div></div>"
            f"<div class='bullets'>{bullets_html}</div></div>"
        )
    st.markdown(f"<div class='grid'>{''.join(cards)}</div>", unsafe_allow_html=True)

st.divider()

# ---------------------------------------------------------------- sentiment chart
st.subheader("Sentiment mix")
if counts:
    chart_df = pd.DataFrame(
        {"sentiment": list(counts.keys()), "count": list(counts.values())}
    ).set_index("sentiment")
    st.bar_chart(chart_df, color="#3b6fd6", height=240)
else:
    st.info("No sentiment scored yet. Run `python sentiment.py` first.")

st.divider()

# ---------------------------------------------------------------- news feed
st.subheader("News feed")
rows = get_articles(ticker=ticker_choice, sentiment=sentiment_choice, search=search.strip())
if not rows:
    st.info("No articles match these filters.")
else:
    df = pd.DataFrame([dict(r) for r in rows])
    df = df[["published_at", "ticker", "headline", "sentiment",
             "sentiment_score", "signal", "signal_confidence", "source"]]

    def colour_sentiment(val):
        return f"color:{SENT_COLOR.get(val, '#999')};font-weight:600"

    # NOTE: newer pandas uses .map (not the old .applymap) for element-wise styling.
    styled = df.style.map(colour_sentiment, subset=["sentiment"])
    st.dataframe(styled, width="stretch", height=460)
    st.caption(f"Showing {len(df)} articles (newest first).")
