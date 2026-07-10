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
    "AVGO": ["broadcom", "avgo"],
    "SPY": ["spy", "s&p 500", "sp 500", "s&p500"],
    # --- Crypto (matched against Finnhub's general crypto news) ---
    "BTC": ["bitcoin", "btc"],
    "ETH": ["ethereum", "ether", "eth"],
    "SOL": ["solana"],
    "XRP": ["xrp", "ripple"],
    "BNB": ["binance coin", "bnb"],
    "ADA": ["cardano"],
    "DOGE": ["dogecoin", "doge"],
    "AVAX": ["avalanche"],
    "LINK": ["chainlink"],
    "DOT": ["polkadot"],
    "SHIB": ["shiba inu", "shib"],
    "PEPE": ["pepe"],
    "BONK": ["bonk"],
    # --- Forex (matched against Finnhub's general forex news). Distinctive currency
    # names cut down noise; 'dollar' alone is too common so we avoid it. ---
    "EURUSD": ["eur/usd", "eurusd", "euro"],
    "GBPUSD": ["gbp/usd", "british pound", "sterling", "pound"],
    "USDJPY": ["usd/jpy", "japanese yen", "yen"],
    "USDCHF": ["usd/chf", "swiss franc", "franc"],
    "AUDUSD": ["aud/usd", "australian dollar", "aussie"],
    "USDCAD": ["usd/cad", "canadian dollar", "loonie"],
    "NZDUSD": ["nzd/usd", "new zealand dollar", "kiwi"],
    "EURGBP": ["eur/gbp"],
    "EURJPY": ["eur/jpy"],
    "GBPJPY": ["gbp/jpy"],
    "XAUUSD": ["gold", "xau", "xau/usd"],
    "XAGUSD": ["silver", "xag", "xag/usd"],
    "EURCHF": ["eur/chf"],
    "USDCNH": ["usd/cnh", "chinese yuan", "yuan"],
}


def match_symbol(symbols, headline, summary=""):
    """Return the FIRST symbol from `symbols` that the text is about, else None.
    Used to tag general crypto/forex news to a specific coin/pair.
    Roman Urdu: General crypto/forex news me se pehla matching symbol dhoond kar
    us khabar ko usi ke saath tag kar dete hain."""
    for sym in symbols:
        if is_relevant(sym, headline, summary):
            return sym
    return None


def is_relevant(ticker, headline, summary=""):
    """True if the text clearly mentions the company. Falls back to the symbol itself."""
    text = f"{headline or ''} {summary or ''}".lower()
    aliases = TICKER_ALIASES.get(ticker.upper(), [ticker.lower()])
    for alias in aliases:
        # \b = word boundary, so 'visa' won't match inside 'invasive'.
        if re.search(rf"\b{re.escape(alias)}\b", text):
            return True
    return False
