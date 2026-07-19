"""
llm/client.py — Unified LLM client with Groq + Gemini fallback.
"""
import json
from typing import Optional, Dict, Any
from openai import AsyncOpenAI
from backend.app.core.config import get_settings


class LLMClient:
    def __init__(self):
        self.settings = get_settings()
        self._groq = None
        self._gemini = None

    @property
    def groq(self):
        if self._groq is None and self.settings.LLM_API_KEY:
            self._groq = AsyncOpenAI(
                api_key=self.settings.LLM_API_KEY,
                base_url=self.settings.LLM_BASE_URL,
            )
        return self._groq

    @property
    def gemini(self):
        if self._gemini is None and self.settings.GEMINI_API_KEY:
            self._gemini = AsyncOpenAI(
                api_key=self.settings.GEMINI_API_KEY,
                base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            )
        return self._gemini

    async def complete(
        self,
        prompt: str,
        system_prompt: str = "You are a professional financial analyst.",
        temperature: float = 0.3,
        max_tokens: int = 500,
        response_format: Optional[str] = None,
    ) -> str:
        """
        Try Groq first, fallback to Gemini. Returns text content.
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ]

        kwargs = {
            "model": self.settings.LLM_MODEL,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format == "json":
            kwargs["response_format"] = {"type": "json_object"}

        # Try Groq
        if self.groq:
            try:
                resp = await self.groq.chat.completions.create(**kwargs)
                return resp.choices[0].message.content
            except Exception as e:
                print(f"[LLM] Groq failed: {e}")

        # Fallback to Gemini
        if self.gemini:
            try:
                kwargs["model"] = "gemini-2.0-flash"
                resp = await self.gemini.chat.completions.create(**kwargs)
                return resp.choices[0].message.content
            except Exception as e:
                print(f"[LLM] Gemini failed: {e}")

        raise RuntimeError("Both Groq and Gemini unavailable")