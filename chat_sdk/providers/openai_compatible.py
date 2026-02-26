"""
OpenAI-Compatible provider base.

Equivalent to Vercel AI SDK's @ai-sdk/openai-compatible package.
Base class for any provider with an OpenAI-compatible API (Together AI, Groq, etc.).

Usage:
    class GroqProvider(OpenAICompatibleProvider):
        provider_name = "groq"

    provider = GroqProvider(
        model_id="llama-3.1-70b",
        api_key="gsk_...",
        base_url="https://api.groq.com/openai/v1",
    )
"""

from __future__ import annotations

import logging

from .openai_provider import OpenAIProvider

logger = logging.getLogger(__name__)


class OpenAICompatibleProvider(OpenAIProvider):
    """
    Base class for OpenAI-compatible API providers.

    Any provider that implements the OpenAI chat completions API format
    can extend this class. Just set the base_url in config.

    Examples:
        - Groq: base_url="https://api.groq.com/openai/v1"
        - Together AI: base_url="https://api.together.xyz/v1"
        - Fireworks: base_url="https://api.fireworks.ai/inference/v1"
        - Ollama: base_url="http://localhost:11434/v1"
        - LM Studio: base_url="http://localhost:1234/v1"
    """

    provider_name = "openai_compatible"

    def __init__(self, model_id: str = "", **config):
        if "base_url" not in config:
            raise ValueError(
                f"{self.__class__.__name__} requires 'base_url' in config"
            )
        super().__init__(model_id=model_id, **config)

    def _get_client(self):
        if self._async_client is None:
            try:
                from openai import AsyncOpenAI
            except ImportError:
                raise ImportError("openai package required: pip install openai")

            self._async_client = AsyncOpenAI(
                api_key=self.config.get("api_key", "not-needed"),
                base_url=self.config.get("base_url"),
            )
        return self._async_client


# --- Convenience subclasses for popular providers ---

class OllamaProvider(OpenAICompatibleProvider):
    """Local Ollama provider."""

    provider_name = "ollama"

    def __init__(self, model_id: str = "llama3.1", **config):
        config.setdefault("base_url", "http://localhost:11434/v1")
        config.setdefault("api_key", "ollama")
        super().__init__(model_id=model_id, **config)


class GroqProvider(OpenAICompatibleProvider):
    """Groq cloud provider."""

    provider_name = "groq"

    def __init__(self, model_id: str = "llama-3.1-70b-versatile", **config):
        config.setdefault("base_url", "https://api.groq.com/openai/v1")
        super().__init__(model_id=model_id, **config)


class TogetherProvider(OpenAICompatibleProvider):
    """Together AI provider."""

    provider_name = "together"

    def __init__(self, model_id: str = "meta-llama/Llama-3.1-70B-Instruct-Turbo", **config):
        config.setdefault("base_url", "https://api.together.xyz/v1")
        super().__init__(model_id=model_id, **config)
