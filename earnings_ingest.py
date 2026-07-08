"""
earnings_ingest.py — pull UPCOMING earnings dates for our stocks (Finnhub, free tier).

This powers the Events Calendar. Unlike the news pipeline (which reacts to the past), this is
forward-looking: known future dates. It's a SEPARATE data source, run occasionally (weekly is
plenty — earnings dates rarely change).
Roman Urdu: Ye aane wali earnings ki dates laata hai (mustaqbil), news pipeline se alag. Hafte
me ek dafa chalana kaafi hai.

Finnhub endpoint (free):
  https://finnhub.io/api/v1/calendar/earnings?from=YYYY-MM-DD&to=YYYY-MM-DD&token=KEY

Run with:  python earnings_ingest.py
"""
from datetime import datetime, timezone, timedelta

import requests

from config import FINNHUB_API_KEY, STOCKS
from db import init_earnings_table, save_earnings

URL = "https://finnhub.io/api/v1/calendar/earnings"
DAYS_AHEAD = 75  # look ~2.5 months ahead so the month grid has data to show


def main():
    if not FINNHUB_API_KEY or FINNHUB_API_KEY == "your_key_here":
        raise SystemExit("No Finnhub key in .env")

    init_earnings_table()
    today = datetime.now(timezone.utc).date()
    params = {
        "from": today.isoformat(),
        "to": (today + timedelta(days=DAYS_AHEAD)).isoformat(),
        "token": FINNHUB_API_KEY,
    }
    resp = requests.get(URL, params=params, timeout=25)
    resp.raise_for_status()
    raw = resp.json().get("earningsCalendar", []) or []

    # The endpoint returns ALL US symbols in the range — keep only OUR stocks.
    # Roman Urdu: Endpoint saare US stocks deta hai — hum sirf apne 10 stocks rakhte hain.
    wanted = set(STOCKS)
    now_iso = datetime.now(timezone.utc).isoformat()
    rows = []
    for e in raw:
        if e.get("symbol") not in wanted:
            continue
        rows.append({
            "symbol": e.get("symbol"),
            "date": e.get("date"),
            "eps_estimate": e.get("epsEstimate"),
            "eps_actual": e.get("epsActual"),
            "hour": e.get("hour"),
            "quarter": e.get("quarter"),
            "year": e.get("year"),
            "fetched_at": now_iso,
        })

    n = save_earnings(rows)
    print(f"Fetched {len(raw)} total earnings rows | saved {n} for our stocks.")
    if rows:
        print("Upcoming for our stocks:")
        for r in sorted(rows, key=lambda x: x["date"])[:15]:
            print(f"  {r['date']}  {r['symbol']:<6} est EPS {r['eps_estimate']}")
    print("Now open the Events Calendar tab (uvicorn api:app --reload).")


if __name__ == "__main__":
    main()
