"""
Base middleware interface for the Chat SDK.

Equivalent to Vercel AI SDK's Language Model Middleware (transformParams, wrapGenerate, wrapStream).

Middleware can intercept and modify:
1. Parameters before they reach the provider (transform_params)
2. Non-streaming generation calls (before/after_generate)
3. Streaming generation (wrap_stream)
"""

from __future__ import annotations

from abc import ABC
from typing import Any, AsyncGenerator


class BaseMiddleware(ABC):
    """
    Abstract base class for Chat SDK middleware.

    Override any of the methods below to implement custom behavior.
    All methods have default no-op implementations so you only override what you need.

    Example:
        class MyMiddleware(BaseMiddleware):
            async def transform_params(self, params):
                params["temperature"] = 0.7  # Force temperature
                return params

            async def after_generate(self, params, result):
                log_usage(result.usage)  # Log token usage
    """

    name: str = "base"

    async def transform_params(self, params: dict[str, Any]) -> dict[str, Any]:
        """
        Transform parameters before they reach the provider.
        Called for both streaming and non-streaming requests.

        Equivalent to Vercel's transformParams middleware hook.

        Args:
            params: Dict with 'messages', 'model_id', 'tools', etc.

        Returns:
            Modified params dict
        """
        return params

    async def before_generate(self, params: dict[str, Any]) -> None:
        """
        Called before a generation request.
        Use for validation, rate checking, logging start time, etc.

        Args:
            params: The (possibly transformed) parameters
        """
        pass

    async def after_generate(self, params: dict[str, Any], result: Any) -> None:
        """
        Called after a generation request completes.
        Use for logging, metrics, caching results, etc.

        Args:
            params: The parameters used for generation
            result: The generation result
        """
        pass

    async def wrap_stream(
        self,
        stream: AsyncGenerator[dict, None],
        params: dict[str, Any],
    ) -> AsyncGenerator[dict, None]:
        """
        Wrap a streaming generation. Can intercept, transform, or replace stream chunks.

        Equivalent to Vercel's wrapStream middleware hook.

        Default implementation passes through all chunks unchanged.

        Args:
            stream: The original async generator of stream chunks
            params: The parameters used for generation

        Yields:
            Stream chunks (possibly modified)
        """
        async for chunk in stream:
            yield chunk
