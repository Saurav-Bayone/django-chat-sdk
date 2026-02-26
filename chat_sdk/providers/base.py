"""
Base provider interface - equivalent to Vercel AI SDK's LanguageModelV3.

All provider adapters must implement this abstract base class.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator


@dataclass
class GenerateResult:
    """Result from a non-streaming generation call."""

    content: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    finish_reason: str = "stop"
    usage: dict[str, int] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseProvider(ABC):
    """
    Abstract base class for AI provider adapters.

    Equivalent to Vercel AI SDK's LanguageModelV3 interface.
    Each provider implements generate() for non-streaming and stream() for streaming.

    To create a custom provider:
        class MyProvider(BaseProvider):
            provider_name = "my_provider"

            async def generate(self, messages, **kwargs) -> GenerateResult:
                # Call your LLM API
                ...

            async def stream(self, messages, **kwargs) -> AsyncGenerator[dict, None]:
                # Stream from your LLM API
                yield {"type": "text_delta", "text": "Hello"}
    """

    provider_name: str = "base"

    def __init__(self, model_id: str = "", **config):
        self.model_id = model_id
        self.config = config

    @abstractmethod
    async def generate(
        self,
        messages: list[dict[str, Any]],
        model: str | None = None,
        tools: list[dict] | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        **kwargs,
    ) -> GenerateResult:
        """
        Non-streaming generation. Equivalent to Vercel's doGenerate().

        Args:
            messages: Conversation history in OpenAI format
            model: Model override (uses instance default if None)
            tools: Tool definitions in OpenAI format
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature

        Returns:
            GenerateResult with content, tool_calls, usage, etc.
        """
        ...

    @abstractmethod
    async def stream(
        self,
        messages: list[dict[str, Any]],
        model: str | None = None,
        tools: list[dict] | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        **kwargs,
    ) -> AsyncGenerator[dict, None]:
        """
        Streaming generation. Equivalent to Vercel's doStream().

        Args:
            messages: Conversation history in OpenAI format
            model: Model override
            tools: Tool definitions
            max_tokens: Maximum tokens
            temperature: Sampling temperature

        Yields:
            Stream chunks as dicts:
            - {"type": "text_delta", "text": "..."}
            - {"type": "tool_call", "tool_call_id": "...", "tool_name": "...", "args": {...}}
            - {"type": "usage", "usage": {"prompt_tokens": N, "completion_tokens": N}}
        """
        ...
        # Make this an async generator
        yield  # pragma: no cover

    def get_model(self, override: str | None = None) -> str:
        """Get the model ID, with optional override."""
        return override or self.model_id

    def __repr__(self):
        return f"{self.__class__.__name__}(model={self.model_id!r})"
