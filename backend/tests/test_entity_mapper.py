from backend.app.ingestion.entity_mapper import map_article_tickers, _classify_event


def test_earnings_classification():
    result = map_article_tickers("AAPL beats Q3 earnings estimates with record revenue")
    assert len(result) >= 1
    assert any(r["ticker"] == "AAPL" for r in result)
    assert result[0]["event_type"] == "EARNINGS"


def test_regulatory_legal():
    result = map_article_tickers("SEC launches investigation into Tesla over self-driving claims")
    assert any(r["ticker"] == "TSLA" for r in result)
    assert result[0]["event_type"] == "REGULATORY_LEGAL"


def test_analyst_rating():
    result = map_article_tickers(
        "Goldman Sachs upgrades Microsoft to overweight, raises price target to $500"
    )
    assert any(r["ticker"] in ("MSFT",) for r in result)
    assert result[0]["event_type"] == "ANALYST_RATING"


def test_multi_ticker_article():
    result = map_article_tickers(
        "Apple and Google announce joint partnership on AI-powered health platform"
    )
    tickers = {r["ticker"] for r in result}
    assert "AAPL" in tickers, "Should detect AAPL"
    assert "GOOGL" in tickers or "GOOG" in tickers, "Should detect GOOGL/GOOG"
    assert all(r["event_type"] == "PRODUCT_LAUNCH" for r in result)


def test_false_positive_avoidance():
    result = map_article_tickers("The IT department will upgrade systems next quarter")
    tickers = {r["ticker"] for r in result}
    assert "IT" not in tickers, "IT is a common word, should not match as ticker"


def test_macro_event():
    result = map_article_tickers(
        "Fed signals potential interest rate cut amid slowing inflation data"
    )
    assert result[0]["event_type"] == "MACRO"


def test_management_change():
    result = map_article_tickers("Apple names new CEO as Tim Cook steps down after decade")
    assert any(r["ticker"] == "AAPL" for r in result)
    assert result[0]["event_type"] == "MANAGEMENT_CHANGE"
