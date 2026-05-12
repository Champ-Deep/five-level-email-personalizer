from __future__ import annotations

from typing import Any, Protocol, TypedDict


class Message(TypedDict, total=False):
    role: str
    content: str


class LLMError(RuntimeError):
    """Raised for any failure surfaced from a provider call."""


class LLMProvider(Protocol):
    name: str

    async def chat(
        self,
        messages: list[Message],
        *,
        model: str,
        max_tokens: int = 1500,
        temperature: float = 0.7,
        system: str | None = None,
        response_format: dict[str, Any] | None = None,
    ) -> str: ...

    async def chat_with_search(
        self,
        messages: list[Message],
        *,
        model: str,
        max_tokens: int = 1500,
        temperature: float = 0.4,
        system: str | None = None,
    ) -> str: ...
