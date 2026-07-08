"""
app.py — NLPTrader dashboard (premium glassmorphism edition).

Sections: Stocks · Crypto · Forex. Control bar lives on the RIGHT. macOS-style frosted glass.
Streamlit re-runs this whole file whenever a control changes — that's the only mental model.
Roman Urdu: Streamlit har control badalne par poori script dobara chalata hai. Saara
visual kaam neeche diye CSS block me hai — Python sirf data laata hai.

Run with:  streamlit run app.py
"""
import sys
import hashlib
import subprocess
import importlib.util

import pandas as pd
import streamlit as st

# Is the heavy pipeline available here? Locally yes (torch installed). On the free cloud
# host we ship a slim install WITHOUT torch, so this is False there and we hide the
# Refresh button — the hosted app is a read-only snapshot of your data.
# Roman Urdu: Cloud par torch install nahi hota, is liye wahan Refresh button chhup jata
# hai aur app sirf mojooda data dikhata hai (display-only). Local par sab chalta hai.
PIPELINE_AVAILABLE = importlib.util.find_spec("torch") is not None

from db import get_ticker_signals, get_articles, sentiment_summary, count_articles
from config import STOCKS, CRYPTO, FOREX

st.set_page_config(page_title="NLPTrader", page_icon="📈", layout="wide")

# ============================================================ STYLES (all the polish)
st.markdown(
    """
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800;900&display=swap');
      html, body, [class*="css"] { font-family:'Inter',system-ui,sans-serif; }

      @keyframes rise {from{opacity:0;transform:translateY(16px);} to{opacity:1;transform:none;}}
      @keyframes grow {from{stroke-dasharray:0 999;}}
      @keyframes shine {0%{background-position:-220px 0;} 100%{background-position:220px 0;}}
      @keyframes spin {to{transform:rotate(360deg);}}
      @keyframes float1 {0%,100%{transform:translate(0,0);}50%{transform:translate(30px,-20px);}}

      /* colourful soft blobs behind the glass so the frosting reads */
      [data-testid="stAppViewContainer"]::before{
        content:"";position:fixed;inset:0;z-index:0;pointer-events:none;
        background:
          radial-gradient(420px 420px at 12% 18%, rgba(59,111,214,0.30), transparent 60%),
          radial-gradient(460px 460px at 88% 12%, rgba(124,58,237,0.26), transparent 60%),
          radial-gradient(520px 520px at 70% 88%, rgba(22,163,74,0.20), transparent 60%);
        animation:float1 18s ease-in-out infinite;
      }
      .block-container{position:relative;z-index:1;padding-top:2rem;}

      /* ---- hero ---- */
      .hero{font-size:44px;font-weight:900;letter-spacing:-1.5px;line-height:1;
            background:linear-gradient(90deg,#5b8def,#a855f7,#34d399);
            -webkit-background-clip:text;background-clip:text;color:transparent;
            background-size:220% auto;animation:shine 6s linear infinite;}
      .sub{color:#aab2c5;font-size:14px;margin-top:6px;}

      /* ---- right-hand glass control bar ---- */
      section[data-testid="stSidebar"]{
        left:auto !important; right:0 !important; width:250px !important; min-width:250px !important;
        background:rgba(255,255,255,0.06) !important; backdrop-filter:blur(20px) saturate(160%);
        -webkit-backdrop-filter:blur(20px) saturate(160%);
        border-left:1px solid rgba(255,255,255,0.14);}
      section[data-testid="stSidebar"] .stButton{display:flex;justify-content:center;}
      /* circular refresh button with a spinning gradient ring */
      section[data-testid="stSidebar"] .stButton > button{
        width:86px;height:86px;border-radius:50%;font-size:26px;
        background:rgba(255,255,255,0.10);border:1px solid rgba(255,255,255,0.20);
        position:relative;transition:transform .2s ease;color:#fff;}
      section[data-testid="stSidebar"] .stButton > button:hover{transform:scale(1.06);}
      section[data-testid="stSidebar"] .stButton > button::before{
        content:"";position:absolute;inset:-4px;border-radius:50%;
        background:conic-gradient(from 0deg,#5b8def,#a855f7,#34d399,#5b8def);
        -webkit-mask:radial-gradient(farthest-side,transparent calc(100% - 5px),#000 0);
                mask:radial-gradient(farthest-side,transparent calc(100% - 5px),#000 0);
        animation:spin 3.2s linear infinite;}

      /* ---- glass stat strip ---- */
      .stats{display:flex;gap:12px;flex-wrap:wrap;margin:6px 0 8px;}
      .stat{flex:1;min-width:120px;background:rgba(255,255,255,0.06);
            border:1px solid rgba(255,255,255,0.14);border-radius:16px;padding:14px 16px;
            backdrop-filter:blur(14px) saturate(150%);-webkit-backdrop-filter:blur(14px) saturate(150%);}
      .stat .n{font-size:26px;font-weight:800;}
      .stat .l{font-size:12px;color:#aab2c5;text-transform:uppercase;letter-spacing:.6px;}

      /* ---- section header ---- */
      .sec{display:flex;align-items:center;gap:10px;margin:26px 0 12px;}
      .sec .ti{font-size:21px;font-weight:800;}
      .sec .cnt{font-size:12px;color:#aab2c5;background:rgba(255,255,255,0.07);
                border:1px solid rgba(255,255,255,0.12);padding:2px 10px;border-radius:20px;}
      .sec .line{flex:1;height:1px;background:linear-gradient(90deg,rgba(255,255,255,0.2),transparent);}

      /* ---- card grid + glass cards ---- */
      .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(265px,1fr));gap:16px;}
      .gcard{background:rgba(255,255,255,0.07);border:1px solid rgba(255,255,255,0.15);
             border-radius:20px;padding:16px 18px;animation:rise .5s ease both;
             backdrop-filter:blur(16px) saturate(150%);-webkit-backdrop-filter:blur(16px) saturate(150%);
             transition:transform .2s ease,box-shadow .2s ease,border-color .2s;}
      .gcard:hover{transform:translateY(-5px);box-shadow:0 16px 40px rgba(0,0,0,0.35);
                   border-color:rgba(255,255,255,0.3);}
      .gcard.empty{opacity:.55;}
      .ch{display:flex;justify-content:space-between;align-items:center;}
      .sym{display:flex;align-items:center;gap:8px;}
      .sym .ic{font-size:18px;}
      .sym .t{font-size:19px;font-weight:800;letter-spacing:.4px;}
      .chip{font-size:10px;text-transform:uppercase;letter-spacing:.6px;padding:2px 8px;
            border-radius:20px;border:1px solid rgba(255,255,255,0.2);color:#cfd6e4;}
      .badge{padding:3px 13px;border-radius:20px;font-weight:800;font-size:12px;color:#fff;}
      .BUY{background:#16a34a;} .SELL{background:#dc2626;} .HOLD{background:#6b7280;}
      .mid{display:flex;align-items:center;gap:12px;margin:12px 0 4px;}
      .ring{flex-shrink:0;}
      .ring circle.p{animation:grow 1.1s ease both;}
      .spk{flex:1;}
      .bullets{display:flex;flex-direction:column;gap:5px;margin-top:8px;}
      .b{font-size:13px;line-height:1.32;display:flex;gap:7px;align-items:flex-start;color:#dfe4ee;}
      .b .m{font-weight:900;width:12px;flex-shrink:0;}
      .pos .m{color:#34d399;} .neg .m{color:#f87171;} .neu .m{color:#9aa3b2;}
      .cf{display:flex;justify-content:space-between;align-items:center;margin-top:12px;}
      .ghost{background:rgba(255,255,255,0.08);border:1px solid rgba(255,255,255,0.18);
             color:#dfe4ee;font-size:12px;font-weight:600;padding:5px 12px;border-radius:10px;
             cursor:pointer;transition:.15s;}
      .ghost:hover{background:rgba(255,255,255,0.16);}
      .src{font-size:11px;color:#8b93a3;}
    </style>
    """,
    unsafe_allow_html=True,
)

SIG_COLOR = {"BUY": "#34d399", "SELL": "#f87171", "HOLD": "#9aa3b2"}
SENT_COLOR = {"positive": "#16a34a", "negative": "#dc2626", "neutral": "#9ca3af"}
ASSET_ICON = {"stock": "📈", "crypto": "🪙", "forex": "💱"}


# ============================================================ small render helpers
def parse_bullets(text):
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
    return out[:5]


def confidence_ring(conf, sig):
    """A circular progress ring (SVG) — looks more premium than a flat bar."""
    C = 125.6
    dash = C * min(conf, 100) / 100
    color = SIG_COLOR.get(sig, "#9aa3b2")
    return (
        f"<svg width='58' height='58' viewBox='0 0 48 48' class='ring'>"
        f"<circle cx='24' cy='24' r='20' fill='none' stroke='rgba(160,160,170,0.20)' stroke-width='4'/>"
        f"<circle class='p' cx='24' cy='24' r='20' fill='none' stroke='{color}' stroke-width='4' "
        f"stroke-linecap='round' stroke-dasharray='{dash:.1f} {C:.1f}' transform='rotate(-90 24 24)'/>"
        f"<text x='24' y='27' text-anchor='middle' font-size='12' font-weight='800' "
        f"fill='{color}'>{conf}</text></svg>"
    )


def spark_svg(symbol, sig):
    """A small DECORATIVE sparkline. Deterministic from the symbol name (not real prices).
    Roman Urdu: Ye chhoti line sirf khoobsurti ke liye hai — asli price nahi."""
    h = int(hashlib.md5(symbol.encode()).hexdigest(), 16)
    n, w, top, bot = 9, 92, 4, 26
    pts = []
    for i in range(n):
        h, r = divmod(h, 101)
        y = top + (r / 101) * (bot - top)
        pts.append((round(i * (w / (n - 1)), 1), round(y, 1)))
    color = SIG_COLOR.get(sig, "#9aa3b2")
    poly = " ".join(f"{x},{y}" for x, y in pts)
    area = "M0,30 " + " ".join(f"L{x},{y}" for x, y in pts) + " L92,30 Z"
    return (
        f"<svg width='100%' height='34' viewBox='0 0 92 30' preserveAspectRatio='none' class='spk'>"
        f"<path d='{area}' fill='{color}' opacity='0.12'/>"
        f"<polyline points='{poly}' fill='none' stroke='{color}' stroke-width='1.6'/></svg>"
    )


def build_card(symbol, asset, row, delay):
    icon = ASSET_ICON.get(asset, "📈")
    if not row:
        return (
            f"<div class='gcard empty' style='animation-delay:{delay:.2f}s'>"
            f"<div class='ch'><div class='sym'><span class='ic'>{icon}</span>"
            f"<span class='t'>{symbol}</span><span class='chip'>{asset}</span></div></div>"
            f"<div class='bullets'><div class='b neu'><span class='m'>●</span>"
            f"<span>Awaiting data — run the pipeline.</span></div></div></div>"
        )
    sig = row["signal"] or "HOLD"
    conf = min(int(row["confidence"] or 0), 100)
    bullets = "".join(
        f"<div class='b {c}'><span class='m'>{m}</span><span>{t}</span></div>"
        for c, m, t in parse_bullets(row["explanation"])
    ) or "<div class='b neu'><span class='m'>●</span><span>No explanation yet.</span></div>"
    return (
        f"<div class='gcard' style='animation-delay:{delay:.2f}s'>"
        f"<div class='ch'><div class='sym'><span class='ic'>{icon}</span>"
        f"<span class='t'>{symbol}</span><span class='chip'>{asset}</span></div>"
        f"<span class='badge {sig}'>{sig}</span></div>"
        f"<div class='mid'>{confidence_ring(conf, sig)}{spark_svg(symbol, sig)}</div>"
        f"<div class='bullets'>{bullets}</div>"
        f"<div class='cf'><button class='ghost'>Details</button>"
        f"<span class='src'>evidence-grounded</span></div></div>"
    )


def run_pipeline():
    steps = [("Fetching fresh news", "main.py"),
             ("Reading RSS feeds", "rss_ingest.py"),
             ("Scoring sentiment (FinBERT)", "sentiment.py"),
             ("Generating signals", "signal_engine.py"),
             ("Writing LLM explanations", "llm_explain.py"),
             ("Fetching earnings calendar", "earnings_ingest.py")]
    with st.status("Refreshing data…", expanded=True) as status:
        for label, script in steps:
            st.write(f"▶ {label}…")
            res = subprocess.run([sys.executable, script], capture_output=True, text=True)
            if res.returncode != 0:
                status.update(label=f"Failed at: {label}", state="error")
                st.code((res.stderr or res.stdout)[-1500:])
                return False
        status.update(label="Done — data refreshed!", state="complete")
    return True


# ============================================================ header
st.markdown("<div class='hero'>📈 NLPTrader</div>", unsafe_allow_html=True)
st.markdown("<div class='sub'>News → sentiment → evidence-grounded signals · "
            "Stocks · Crypto · Forex · decision-support only, not financial advice</div>",
            unsafe_allow_html=True)

# ============================================================ right control bar
st.sidebar.markdown("### ⚙️ Controls")
if PIPELINE_AVAILABLE:
    if st.sidebar.button("🔄", help="Refresh: re-runs news → sentiment → signal → explanation"):
        if run_pipeline():
            st.rerun()
    st.sidebar.caption("Refresh data")
else:
    st.sidebar.caption("🌐 Live demo · data is a snapshot")
st.sidebar.divider()
search = st.sidebar.text_input("🔎 Search symbol", "", placeholder="e.g. AAPL, BTC, EUR")
asset_choice = st.sidebar.radio("Asset class", ["All", "Stocks", "Crypto", "Forex"], horizontal=False)
sentiment_choice = st.sidebar.selectbox("News sentiment", ["All", "positive", "neutral", "negative"])

# ============================================================ data
signals = {r["ticker"]: r for r in get_ticker_signals()}
counts = sentiment_summary()
q = search.strip().upper()

# ============================================================ glass stat strip
st.markdown(
    f"""
    <div class='stats'>
      <div class='stat'><div class='n'>{count_articles()}</div><div class='l'>📰 Articles</div></div>
      <div class='stat'><div class='n' style='color:#34d399'>{counts.get('positive',0)}</div><div class='l'>Positive</div></div>
      <div class='stat'><div class='n' style='color:#9aa3b2'>{counts.get('neutral',0)}</div><div class='l'>Neutral</div></div>
      <div class='stat'><div class='n' style='color:#f87171'>{counts.get('negative',0)}</div><div class='l'>Negative</div></div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ============================================================ the 3 sections
SECTIONS = [("Stocks", "stock", STOCKS), ("Crypto", "crypto", CRYPTO), ("Forex", "forex", FOREX)]


def render_section(title, asset, symbols):
    if asset_choice != "All" and asset_choice.lower() != asset:
        return
    shown = [s for s in symbols if (not q or q in s.upper())]
    have = sum(1 for s in shown if s in signals)
    st.markdown(
        f"<div class='sec'><span class='ti'>{ASSET_ICON[asset]} {title}</span>"
        f"<span class='cnt'>{have}/{len(symbols)} with signals</span>"
        f"<span class='line'></span></div>",
        unsafe_allow_html=True,
    )
    if not shown:
        st.caption("No symbols match your search in this section.")
        return
    cards = "".join(build_card(s, asset, signals.get(s), i * 0.04) for i, s in enumerate(shown))
    st.markdown(f"<div class='grid'>{cards}</div>", unsafe_allow_html=True)


for title, asset, symbols in SECTIONS:
    render_section(title, asset, symbols)

# ============================================================ sentiment chart
st.markdown("<div class='sec'><span class='ti'>📊 Sentiment mix</span><span class='line'></span></div>",
            unsafe_allow_html=True)
if counts:
    cdf = pd.DataFrame({"sentiment": list(counts.keys()),
                        "count": list(counts.values())}).set_index("sentiment")
    st.bar_chart(cdf, color="#5b8def", height=220)
else:
    st.info("No sentiment scored yet. Run `python sentiment.py`.")

# ============================================================ news feed
st.markdown("<div class='sec'><span class='ti'>🗞️ News feed</span><span class='line'></span></div>",
            unsafe_allow_html=True)
ticker_filter = q if (q in signals or q in [s.upper() for s in STOCKS + CRYPTO + FOREX]) else None
rows = get_articles(ticker=ticker_filter, sentiment=sentiment_choice, search=search.strip())
if not rows:
    st.info("No articles match these filters.")
else:
    df = pd.DataFrame([dict(r) for r in rows])
    df = df[["published_at", "ticker", "headline", "sentiment",
             "sentiment_score", "signal", "signal_confidence", "source"]]
    styled = df.style.map(lambda v: f"color:{SENT_COLOR.get(v,'#999')};font-weight:600",
                          subset=["sentiment"])
    st.dataframe(styled, width="stretch", height=440)
    st.caption(f"Showing {len(df)} articles (newest first).")
