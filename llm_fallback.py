"""
llm_fallback.py — shared LLM helper that tries Groq first, falls back to Gemini.

Usage:
    from llm_fallback import llm_complete
    text = llm_complete(system_prompt="...", user_prompt="...")
    if text is None:  # both providers failed
"""
from openai import OpenAI
from config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL, GEMINI_API_KEY, GEMINI_BASE_URL, GEMINI_MODEL

GROQ_LABEL = "Groq (" + LLM_MODEL + ")"
GEMINI_LABEL = "Gemini (" + GEMINI_MODEL + ")"


def llm_complete(system_prompt, user_prompt, max_tokens=500, temperature=0.3):
    """
    Call LLM: try Groq, then Gemini fallback.
    Returns (response_text, provider_name) or (None, "both failed").
    """
    providers = []
    errors = {}
    if LLM_API_KEY and LLM_API_KEY != "your_llm_key_here":
        providers.append((GROQ_LABEL, LLM_API_KEY, LLM_BASE_URL, LLM_MODEL))
    if GEMINI_API_KEY:
        providers.append((GEMINI_LABEL, GEMINI_API_KEY, GEMINI_BASE_URL, GEMINI_MODEL))

    for label, api_key, base_url, model in providers:
        try:
            client = OpenAI(api_key=api_key, base_url=base_url)
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            text = resp.choices[0].message.content.strip()
            if text:
                return text, label
            errors[label] = "Empty response"
        except Exception as e:
            msg = str(e)[:120]
            print(f"[llm_fallback] {label} failed: {msg}")
            errors[label] = msg
            continue

    return None, "both failed: " + "; ".join(f"{k}: {v}" for k, v in errors.items())
