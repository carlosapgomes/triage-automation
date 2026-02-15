"""Generic LLM client protocol and simple adapter wrappers."""

from __future__ import annotations

from typing import Protocol


class LlmClientPort(Protocol):
    """Protocol for text completion against chat-style LLM APIs."""

    async def complete(self, *, system_prompt: str, user_prompt: str) -> str:
        """Return completion text for the supplied prompts."""


class StaticLlmClient:
    """Test-friendly static client returning fixed response text."""

    def __init__(self, response_text: str) -> None:
        self._response_text = response_text

    async def complete(self, *, system_prompt: str, user_prompt: str) -> str:
        return self._response_text
