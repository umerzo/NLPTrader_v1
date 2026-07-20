from dataclasses import dataclass
from typing import Optional
from datetime import datetime, timezone
import json
import logging

from backend.app.core.config import get_settings
from backend.app.llm.client import LLMClient
from backend.app.signals.embedder import retrieve_relevant_articles

logger = logging.getLogger(__name__)


@dataclass
class FundamentalSignal:
    signal: str
    confidence: int
    narrative: str
    key_themes: list[str]
    risks: list[str]
    catalyst: Optional[str]
    articles_used: int


class FundamentalEngine:
    def __init__(self, session=None):
        self.settings = get_settings()
        self.llm = LLMClient()
        self._session = session

    async def generate_signal(
        self,
        ticker: str,
        current_price: float,
        lookback_days: Optional[int] = None,
    ) -> FundamentalSignal:
        if lookback_days is None:
            lookback_days = self.settings.RAG_LOOKBACK_DAYS

        if self._session is None:
            return FundamentalSignal(
                signal='hold', confidence=5,
                narrative="Database session not available for fundamental analysis.",
                key_themes=[], risks=[], catalyst=None, articles_used=0
            )

        query_text = f"{ticker} price action news fundamentals earnings guidance outlook"
        articles = await retrieve_relevant_articles(
            session=self._session,
            ticker=ticker,
            query_text=query_text,
            top_k=self.settings.RAG_TOP_K,
            lookback_days=lookback_days,
        )

        if not articles:
            return FundamentalSignal(
                signal='hold', confidence=10,
                narrative="Insufficient recent news for fundamental assessment.",
                key_themes=[], risks=[], catalyst=None, articles_used=0
            )

        context_parts = []
        for a in articles:
            text = a.get("headline", "")
            if a.get("summary"):
                text += ". " + a["summary"]
            context_parts.append(f"[{a['published_at']}] {text}")
        context = "\n\n".join(context_parts)

        prompt = f"""You are a senior fundamental analyst. Analyze {ticker} at ${current_price:.2f}.

Recent relevant news (retrieved via RAG):
{context}

Provide a JSON response with:
{{
  "bias": "bullish|bearish|neutral",
  "confidence": 0-100,
  "narrative": "2-3 sentence summary of fundamental picture",
  "key_themes": ["theme1", "theme2"],
  "risks": ["risk1", "risk2"],
  "catalyst": "specific near-term event or null"
}}

Be honest. If unclear, return neutral with low confidence."""

        try:
            response = await self.llm.complete(prompt, temperature=0.3, max_tokens=400, response_format="json")
            parsed = json.loads(response)
        except Exception as e:
            logger.error("Fundamental LLM call failed for %s: %s", ticker, e)
            return FundamentalSignal(
                signal='hold', confidence=10,
                narrative="LLM unavailable for fundamental analysis.",
                key_themes=[], risks=[], catalyst=None, articles_used=len(articles)
            )

        bias = parsed.get('bias', 'neutral').lower()
        signal_map = {'bullish': 'buy', 'bearish': 'sell', 'neutral': 'hold'}

        return FundamentalSignal(
            signal=signal_map.get(bias, 'hold'),
            confidence=min(100, max(0, int(parsed.get('confidence', 10)))),
            narrative=parsed.get('narrative', ''),
            key_themes=parsed.get('key_themes', []),
            risks=parsed.get('risks', []),
            catalyst=parsed.get('catalyst'),
            articles_used=len(articles)
        )
