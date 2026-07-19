"""
fundamental_engine.py — RAG + LLM Fundamental Analysis.

1. Ingest articles into ChromaDB (vector store) at ingestion time
2. At signal time: retrieve relevant articles → LLM synthesis → FundamentalSignal
"""
import asyncio
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, timedelta
import json

import chromadb
from chromadb.config import Settings as ChromaSettings
from sentence_transformers import SentenceTransformer

from backend.app.core.config import get_settings
from backend.app.llm.client import LLMClient


@dataclass
class FundamentalSignal:
    signal: str                 # 'buy' | 'sell' | 'hold'
    confidence: int             # 0-100
    narrative: str              # 2-3 sentence summary
    key_themes: List[str]       # Positive drivers
    risks: List[str]            # Negative risks
    catalyst: Optional[str]     # Near-term event
    articles_used: int


class FundamentalEngine:
    def __init__(self):
        self.settings = get_settings()
        self.client = chromadb.PersistentClient(
            path=self.settings.CHROMA_PERSIST_DIR,
            settings=ChromaSettings(anonymized_telemetry=False)
        )
        self.collection = self.client.get_or_create_collection(
            name="news_articles",
            metadata={"hnsw:space": "cosine"}
        )
        self.embedder = SentenceTransformer(self.settings.EMBEDDING_MODEL)
        self.llm = LLMClient()

    async def ingest_article(self, article: Dict[str, Any]) -> None:
        """Call during ingestion pipeline. Adds article to ChromaDB."""
        text = f"{article['headline']}. {article.get('summary', '')}"

        def _sync():
            embedding = self.embedder.encode(text).tolist()
            self.collection.add(
                ids=[article['url']],
                embeddings=[embedding],
                metadatas=[{
                    "ticker": article['ticker'],
                    "source": article['source'],
                    "published_at": article['published_at'].timestamp(),
                    "headline": article['headline'][:200],
                }],
                documents=[text]
            )

        await asyncio.to_thread(_sync)

    async def generate_signal(
        self,
        ticker: str,
        current_price: float,
        lookback_days: Optional[int] = None,
    ) -> FundamentalSignal:
        if lookback_days is None:
            lookback_days = self.settings.RAG_LOOKBACK_DAYS

        cutoff_ts = (datetime.now(timezone.utc) - timedelta(days=lookback_days)).timestamp()

        # Build query
        query_text = f"{ticker} price action news fundamentals earnings guidance outlook"
        query_emb = self.embedder.encode(query_text).tolist()

        # RAG RETRIEVAL
        results = self.collection.query(
            query_embeddings=[query_emb],
            n_results=self.settings.RAG_TOP_K,
            where={"$and": [
                {"ticker": ticker},
                {"published_at": {"$gte": cutoff_ts}}
            ]},
        )

        if not results['documents'][0]:
            return FundamentalSignal(
                signal='hold', confidence=10,
                narrative="Insufficient recent news for fundamental assessment.",
                key_themes=[], risks=[], catalyst=None, articles_used=0
            )

        # Prepare context for LLM
        articles_context = []
        for meta, doc in zip(results['metadatas'][0], results['documents'][0]):
            articles_context.append(
                f"[{meta['published_at']}] {meta['headline']}: {doc}"
            )
        context = "\n\n".join(articles_context)

        # LLM SYNTHESIS (RAG-AUGMENTED GENERATION)
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
        except Exception:
            return FundamentalSignal(
                signal='hold', confidence=10,
                narrative="LLM unavailable for fundamental analysis.",
                key_themes=[], risks=[], catalyst=None, articles_used=len(results['documents'][0])
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
            articles_used=len(results['documents'][0])
        )