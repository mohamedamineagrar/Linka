"""
NutriTrack — Groq LLM Client
=============================
OpenAI-compatible client for Groq chat completions (https://groq.com).

Environment variables:
- GROQ_API_KEY: Groq API key from https://console.groq.com/keys (required to enable LLM mode)
- GROQ_MODEL: optional (default: mixtral-8x7b-32768)
- GROQ_BASE_URL: optional (default: https://api.groq.com/openai/v1)

Backward-compatible aliases also supported:
- GROK_API_KEY, GROK_MODEL, GROK_BASE_URL
"""

from __future__ import annotations

import json
import os
from typing import Any

from dotenv import load_dotenv
from groq import Groq


class GrokClient:
    def __init__(self):
        load_dotenv()
        self.api_key = (os.getenv("GROQ_API_KEY") or os.getenv("GROK_API_KEY") or "").strip()
        self.model = (
            os.getenv("GROQ_MODEL")
            or os.getenv("GROK_MODEL")
            or "mixtral-8x7b-32768"
        ).strip() or "mixtral-8x7b-32768"
        self.base_url = (
            os.getenv("GROQ_BASE_URL")
            or os.getenv("GROK_BASE_URL")
            or "https://api.groq.com/openai/v1"
        ).rstrip("/")

        # Groq SDK targets /openai/v1 internally; avoid duplicating that segment.
        sdk_base_url = self.base_url
        if sdk_base_url.endswith("/openai/v1"):
            sdk_base_url = sdk_base_url[: -len("/openai/v1")]

        self._client = Groq(api_key=self.api_key, base_url=sdk_base_url) if self.api_key else None

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def complete_json(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float = 0.1,
        max_tokens: int = 800,
    ) -> dict[str, Any] | None:
        """
        Request a JSON object from Grok and parse it safely.
        Returns None on API or parse failure.
        """
        if not self.enabled or self._client is None:
            return None

        try:
            response = self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
            )

            content = response.choices[0].message.content
            if content is None:
                return None
            if isinstance(content, dict):
                return content
            return json.loads(content)
        except Exception as e:
            import sys
            print(f"[GROK ERROR] SDK request/parse error: {e}", file=sys.stderr)
            return None


_CLIENT: GrokClient | None = None


def get_grok_client() -> GrokClient:
    global _CLIENT
    if _CLIENT is None:
        _CLIENT = GrokClient()
    return _CLIENT
