import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)

EVENT_KEYWORDS: dict[str, list[str]] = {
    "EARNINGS": ["earnings", "quarterly result", "fiscal", "profit", "revenue", "eps", "earnings call",
                  "net income", "financial result", "quarter", "q1", "q2", "q3", "q4", "dividend",
                  "buyback", "share repurchase"],
    "PRODUCT_LAUNCH": ["launch", "unveil", "new product", "release", "announce", "introduc",
                       "debut", "rollout", "shipment", "pre-order", "beta"],
    "M_AND_A": ["acquisition", "merger", "acquire", "buyout", "takeover", "merge", "acquired",
                "purchase", "divestiture", "spin-off", "spinoff", "joint venture"],
    "REGULATORY_LEGAL": ["lawsuit", "regulator", "sec", "fine", "investigation", "antitrust",
                         "regulation", "compliance", "legal", "settlement", "approval", "ban",
                         "sanction", "class action", "doj", "fcc", "ftc"],
    "ANALYST_RATING": ["upgrade", "downgrade", "overweight", "underweight", "outperform",
                       "buy rating", "sell rating", "hold rating", "target price", "price target",
                       "analyst", "rating"],
    "MACRO": ["inflation", "interest rate", "gdp", "unemployment", "cpi", "ppi", "fed",
              "central bank", "treasury", "trade war", "recession", "stimulus", "economic",
              "jobs report", "nonfarm", "consumer price"],
    "MANAGEMENT_CHANGE": ["ceo", "cfo", "executive", "board", "appoint", "resign", "step down",
                          "named ceo", "new chief", "management change", "succession",
                          "departure", "hire"],
}

COMMON_WORDS = {
    "A", "I", "IT", "AT", "ON", "IN", "BY", "TO", "OF", "OR", "BE", "DO", "GO", "NO",
    "UP", "WE", "AS", "IS", "AM", "AN", "SO", "IF", "ME", "MY", "HE", "HI", "BIG",
    "TOP", "OUT", "NEW", "ALL", "ARE", "NOT", "CAN", "GET", "HAS", "HAD", "BUT",
    "FOR", "THE", "AND", "WHO", "HOW", "NOW", "ANY", "MAY", "JAN", "FEB", "MAR",
    "APR", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC",
}

COMPANY_TO_TICKER: dict[str, str] = {
    "APPLE": "AAPL", "MICROSOFT": "MSFT", "GOOGLE": "GOOGL",
    "ALPHABET": "GOOGL", "AMAZON": "AMZN", "META": "META",
    "FACEBOOK": "META", "TESLA": "TSLA", "NVIDIA": "NVDA",
    "JPMORGAN": "JPM", "BANK OF AMERICA": "BAC", "GOLDMAN": "GS",
    "GOLDMAN SACHS": "GS", "JOHNSON": "JNJ", "PFIZER": "PFE",
    "MODERNA": "MRNA", "WALMART": "WMT", "COSTCO": "COST",
    "HOME DEPOT": "HD", "DISNEY": "DIS", "NETFLIX": "NFLX",
    "COMCAST": "CMCSA", "NIKE": "NKE", "INTEL": "INTC",
    "ADVANCED MICRO": "AMD", "IBM": "IBM", "ORACLE": "ORCL",
    "SALESFORCE": "CRM", "ADOBE": "ADBE", "CISCO": "CSCO",
    "EXXON": "XOM", "CHEVRON": "CVX", "CONOCO": "COP",
    "BOEING": "BA", "CATERPILLAR": "CAT", "GENERAL ELECTRIC": "GE",
    "FORD": "F", "GENERAL MOTORS": "GM", "COCA": "KO",
    "COCA-COLA": "KO", "PEPSI": "PEP", "PEPSICO": "PEP",
    "MCDONALD": "MCD", "MCDONALD'S": "MCD", "STARBUCKS": "SBUX",
    "AT&T": "T", "VERIZON": "VZ", "BITCOIN": "BTC",
    "ETHEREUM": "ETH", "SOLANA": "SOL", "RIPPLE": "XRP",
    "BINANCE": "BNB", "CARDANO": "ADA", "DOGECOIN": "DOGE",
}

def map_article_tickers(
    headline: str,
    summary: Optional[str] = None,
    known_tickers: Optional[set[str]] = None,
) -> list[dict]:
    if known_tickers is None:
        known_tickers = _default_tickers()
    text = f"{headline} {summary or ''}"
    text_upper = text.upper()

    matched_tickers: set[str] = set()

    for ticker in known_tickers:
        if ticker in COMMON_WORDS:
            pattern = r'\b' + re.escape(ticker) + r'\b'
            if re.search(pattern, text_upper):
                matched_tickers.add(ticker)
        else:
            pattern = r'\b' + re.escape(ticker) + r'\b'
            if re.search(pattern, text_upper):
                matched_tickers.add(ticker)

    for company_name, ticker in COMPANY_TO_TICKER.items():
        if company_name in text_upper or company_name.replace("'", "") in text_upper:
            matched_tickers.add(ticker)

    if not matched_tickers:
        matched_tickers.add("OTHER")

    event_type = _classify_event(headline, summary)
    relevance = 1.0 if len(matched_tickers) <= 3 else 0.5

    return [
        {"ticker": t, "event_type": event_type, "relevance": relevance}
        for t in matched_tickers
    ]


def _classify_event(headline: str, summary: Optional[str] = None) -> str:
    text = (headline + " " + (summary or "")).lower()
    scores: dict[str, int] = {}
    for event_type, keywords in EVENT_KEYWORDS.items():
        score = 0
        for kw in keywords:
            pattern = r'\b' + re.escape(kw) + r'\b'
            score += len(re.findall(pattern, text))
        if score > 0:
            scores[event_type] = score
    if not scores:
        return "OTHER"
    return max(scores, key=scores.get)


def _default_tickers() -> set[str]:
    return {
        "AAPL", "MSFT", "GOOGL", "GOOG", "AMZN", "META", "FB", "NVDA", "TSLA",
        "JPM", "BAC", "GS", "V", "MA", "JNJ", "PFE", "MRNA", "UNH",
        "WMT", "COST", "HD", "DIS", "NFLX", "CMCSA", "NKE",
        "INTC", "AMD", "IBM", "ORCL", "CRM", "ADBE", "CSCO",
        "XOM", "CVX", "COP", "BA", "CAT", "GE", "F", "GM",
        "KO", "PEP", "MCD", "SBUX", "T", "VZ",
        "BTC", "ETH", "SOL", "XRP", "BNB", "ADA", "DOGE",
        "SPY", "QQQ", "IWM", "DIA", "GLD", "SLV",
        "XAUUSD", "BTC-USD", "ETH-USD",
    }
