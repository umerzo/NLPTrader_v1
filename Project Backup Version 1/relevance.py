"""
relevance.py — keep only news that is actually ABOUT the ticker.

The problem you saw: Finnhub tagged SpaceX/Anthropic stories under NVDA. Those pollute the
sentiment score. The fix is a cheap check: does the headline (or summary) actually mention
the company by name or symbol? If not, it's noise — drop it.
Roman Urdu: Masla ye tha ke ghair-mutaaliqa khabrein ticker se judi thीं. Hum check karte
hain ke headline me company ka naam ya symbol hai ya nahi — agar nahi to wo khabar noise hai.

This is a SIMPLE keyword check, not perfect. That's fine for an MVP — and being honest about
its limits is itself good capstone material.
"""
import re

# ticker -> words that count as "this is really about them".
# Keep symbols here too; single-letter tickers (V, MA) rely on the NAME, not the symbol.
TICKER_ALIASES = {
    "AAPL": ["apple"],
    "MSFT": ["microsoft", "msft"],
    "TSLA": ["tesla", "tsla"],
    "NVDA": ["nvidia", "nvda"],
    "AMZN": ["amazon", "amzn"],
    "GOOGL": ["google", "alphabet", "googl"],
    "META": ["meta platforms", "facebook", "instagram", "meta"],
    "NFLX": ["netflix", "nflx"],
    "AMD": ["amd", "advanced micro"],
    "INTC": ["intel", "intc"],
    "JPM": ["jpmorgan", "jp morgan", "jpm"],
    "BAC": ["bank of america", "bofa"],
    "V": ["visa inc", "visa"],
    "MA": ["mastercard"],
    "DIS": ["disney"],
    "KO": ["coca-cola", "coca cola", "coke"],
    "PEP": ["pepsico", "pepsi"],
    "WMT": ["walmart"],
    "NKE": ["nike"],
    "BA": ["boeing"],
    "XOM": ["exxon", "exxonmobil"],
    "CVX": ["chevron"],
    "PFE": ["pfizer"],
    "JNJ": ["johnson & johnson", "johnson and johnson", "j&j"],
    "UBER": ["uber"],
}


def is_relevant(ticker, headline, summary=""):
    """True if the text clearly mentions the company. Falls back to the symbol itself."""
    text = f"{headline or ''} {summary or ''}".lower()
    aliases = TICKER_ALIASES.get(ticker.upper(), [ticker.lower()])
    for alias in aliases:
        # \b = word boundary, so 'visa' won't match inside 'invasive'.
        if re.search(rf"\b{re.escape(alias)}\b", text):
            return True
    return False
