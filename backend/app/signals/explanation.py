import logging
from dataclasses import dataclass
from typing import Optional
from backend.app.llm.client import LLMClient

logger = logging.getLogger(__name__)


@dataclass
class ExplanationResult:
    explanation: Optional[str]
    raw_prompt: str
    raw_response: Optional[str]
    model_used: Optional[str]


async def generate_explanation(
    signal: str,
    confidence: int,
    ticker: str,
    current_price: Optional[float],
    ta_signal: str,
    ta_confidence: int,
    sentiment_signal: str,
    sentiment_confidence: int,
    fundamental_signal: str,
    fundamental_confidence: int,
    regime: Optional[str] = None,
    conflict_penalty_applied: bool = False,
    combiner_reasoning: Optional[str] = None,
) -> ExplanationResult:
    price_str = f"${current_price:.2f}" if current_price is not None else "N/A"
    regime_str = regime or "unknown"
    conflict_str = "Yes" if conflict_penalty_applied else "No"
    reason_str = combiner_reasoning or "N/A"

    prompt_lines = [
        "You are an explainer for a financial signal generation system. Your job is to explain the final signal, not to decide it.",
        "",
        f"Ticker: {ticker}",
        f"Current Price: {price_str}",
        "",
        f"FINAL SIGNAL (already decided - do not change): {signal.upper()}",
        f"CONFIDENCE (already decided - do not change): {confidence}/100",
        "",
        "SUB-SIGNALS:",
        f"- Technical Analysis: {ta_signal} (confidence: {ta_confidence}/100)",
        f"- Sentiment Analysis: {sentiment_signal} (confidence: {sentiment_confidence}/100)",
        f"- Fundamental Analysis: {fundamental_signal} (confidence: {fundamental_confidence}/100)",
        "",
        f"Regime: {regime_str}",
        f"Conflict penalty applied: {conflict_str}",
        f"Combiner reasoning: {reason_str}",
        "",
        "Given the FINAL SIGNAL above as a fact, provide a brief narrative explanation (3-5 sentences) covering:",
        "1. Why this signal makes sense given the sub-signals",
        "2. Which sub-signals agreed and which disagreed",
        "3. Any contradictions worth flagging",
        "4. A summary of the risk",
        "",
        "Keep it factual. Do NOT suggest a different signal or confidence value.",
    ]
    prompt = "\n".join(prompt_lines)

    from backend.app.core.config import settings

    llm = LLMClient()
    raw_response = None
    model_used = settings.LLM_MODEL

    try:
        response = await llm.complete(prompt, temperature=0.5, max_tokens=400)
        raw_response = response
    except Exception as e:
        logger.warning("LLM explanation failed for %s: %s", ticker, e)
        return ExplanationResult(
            explanation=None,
            raw_prompt=prompt,
            raw_response=None,
            model_used=model_used,
        )

    return ExplanationResult(
        explanation=raw_response,
        raw_prompt=prompt,
        raw_response=raw_response,
        model_used=model_used,
    )
