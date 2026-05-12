from __future__ import annotations

import json
from typing import Any

import httpx

from app.core.config import get_settings
from app.services.llm.base import LLMError, Message


class OpenRouterProvider:
    """Async OpenRouter client — ported from ChampMail's `OpenRouterClient`.

    Web search is implemented by appending `:online` to the model slug, which
    routes the call through OpenRouter's web-search shim (cheapest path that
    works for every model). Perplexity Sonar models support search natively
    via the same shim.
    """

    name = "openrouter"

    def __init__(self) -> None:
        s = get_settings()
        if not s.openrouter_api_key:
            raise LLMError("OPENROUTER_API_KEY is not set")
        self.api_key = s.openrouter_api_key
        self.base_url = s.openrouter_base_url.rstrip("/")
        self.timeout = float(s.openrouter_timeout)

    async def _post(self, payload: dict[str, Any]) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://personalize.champions.group",
            "X-Title": "Five-Level Email Personalizer",
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                )
        except httpx.HTTPError as e:
            raise LLMError(f"OpenRouter transport error: {e}") from e

        if resp.status_code >= 400:
            try:
                detail = resp.json()
            except Exception:
                detail = resp.text
            raise LLMError(f"OpenRouter {resp.status_code}: {detail}")

        data = resp.json()
        choices = data.get("choices") or []
        if not choices:
            raise LLMError(f"OpenRouter returned no choices: {data}")
        message = choices[0].get("message") or {}
        content = message.get("content")
        if not isinstance(content, str):
            raise LLMError(f"Unexpected response shape: {data}")
        return content

    async def chat(
        self,
        messages: list[Message],
        *,
        model: str,
        max_tokens: int = 1500,
        temperature: float = 0.7,
        system: str | None = None,
        response_format: dict[str, Any] | None = None,
    ) -> str:
        msgs: list[dict[str, str]] = []
        if system:
            msgs.append({"role": "system", "content": system})
        msgs.extend(dict(m) for m in messages)
        payload: dict[str, Any] = {
            "model": model,
            "messages": msgs,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if response_format:
            payload["response_format"] = response_format
        return await self._post(payload)

    async def chat_with_search(
        self,
        messages: list[Message],
        *,
        model: str,
        max_tokens: int = 1500,
        temperature: float = 0.4,
        system: str | None = None,
    ) -> str:
        search_model = model if ":online" in model or model.startswith("perplexity/") else f"{model}:online"
        return await self.chat(
            messages,
            model=search_model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system,
        )


def extract_json(text: str) -> Any:
    """Pull the first/last brace-delimited JSON object out of an LLM response.

    Defensive: handles surrounding prose, markdown fences, and trailing text.
    """
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise LLMError(f"No JSON object found in: {text[:200]}")
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError as e:
        raise LLMError(f"Invalid JSON: {e}") from e
