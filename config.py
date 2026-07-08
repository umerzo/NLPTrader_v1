"""
config.py — central place for all settings.

Why a separate config file? So secrets (your API key) live in a .env file that is NEVER
committed to git, and the rest of the code just imports clean values from here.
Roman Urdu: Settings aur API key ek hi jagah rakhte hain taake code saaf rahe aur key
git par galti se upload na ho jaye.
"""
import os
from dotenv import load_dotenv

# Reads the .env file and loads its values into the environment.
load_dotenv()

FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY", "").strip()

# --- Three asset universes (10 each). Defined here in code now (not .env) so the
# dashboard can group them into Stocks / Crypto / Forex sections.
# Roman Urdu: Ab teen alag list hain — har ek dashboard par apne section me dikhegi.
# Note: the old TICKERS line in .env is no longer used.
STOCKS = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AVGO", "JPM", "V"]
CRYPTO = ["BTC", "ETH", "SOL", "XRP", "BNB", "ADA", "DOGE", "AVAX", "LINK", "DOT"]
FOREX = ["EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD",
         "USDCAD", "NZDUSD", "EURGBP", "EURJPY", "GBPJPY"]

TICKERS = STOCKS + CRYPTO + FOREX

_CLASS = {}
for _s in STOCKS:
    _CLASS[_s] = "stock"
for _s in CRYPTO:
    _CLASS[_s] = "crypto"
for _s in FOREX:
    _CLASS[_s] = "forex"


def asset_class_of(ticker):
    """Return 'stock' | 'crypto' | 'forex' for a symbol."""
    return _CLASS.get(ticker.upper(), "stock")

LOOKBACK_DAYS = int(os.getenv("LOOKBACK_DAYS", "3"))

# The SQLite database is just a single file created in this folder.
DB_PATH = "nlptrader.db"

# --- LLM settings (Step 4b: grounded explanations) ---------------------------
# DeepSeek, Groq and OpenAI all speak the same "OpenAI-compatible" API, so ONE set
# of settings works for any of them — you just change these 3 values in .env.
# Roman Urdu: Teeno providers ka API ek jaisa hai — sirf ye 3 cheezein .env me badlo
# aur koi bhi LLM lag jayega. Code badalne ki zaroorat nahi.
#
# Free starter: Groq -> https://console.groq.com  (free key, hosts Llama 3.3 70B)
#   LLM_BASE_URL=https://api.groq.com/openai/v1
#   LLM_MODEL=llama-3.3-70b-versatile
# Cheap alt: DeepSeek -> https://platform.deepseek.com
#   LLM_BASE_URL=https://api.deepseek.com
#   LLM_MODEL=deepseek-chat
LLM_API_KEY = os.getenv("LLM_API_KEY", "").strip()
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1").strip()
LLM_MODEL = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile").strip()


def assert_llm_configured():
    if not LLM_API_KEY or LLM_API_KEY == "your_llm_key_here":
        raise SystemExit(
            "No LLM API key found.\n"
            "Fix: get a FREE key at https://console.groq.com, then add to .env:\n"
            "  LLM_API_KEY=your_real_key\n"
            "  LLM_BASE_URL=https://api.groq.com/openai/v1\n"
            "  LLM_MODEL=llama-3.3-70b-versatile"
        )


def assert_configured():
    """Fail early with a friendly message if the API key is missing."""
    if not FINNHUB_API_KEY or FINNHUB_API_KEY == "your_key_here":
        raise SystemExit(
            "No Finnhub API key found.\n"
            "Fix: copy .env.example to .env and paste your key from https://finnhub.io"
        )
