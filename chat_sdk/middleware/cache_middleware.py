"""Caching middleware - cache LLM responses for identical prompts."""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, AsyncGenerator

from django.core.cache import cache as django_cache

from .base import BaseMiddleware

logger = logging.getLogger(__name__)


class CacheMiddleware(BaseMiddleware):
    """
    Caches LLM responses for identical message sequences.

    Uses Django's cache framework (Redis recommended for production).
    Only caches non-streaming, non-tool-call responses.

    Config:
        Cache timeout: 3600 seconds (1 hour) by default
        Cache key prefix: "chat_sdk:llm:"
    """

    name = "cache"
    cache_timeout = 3600
    key_prefix = "chat_sdk:llm:"

    async def transform_params(self, params: dict[str, Any]) -> dict[str, Any]:
        """Check cache before generation."""
        if params.get("tools"):
            # Don't cache tool-calling requests
            return params

        cache_key = self._make_key(params)
        cached = django_cache.get(cache_key)

        if cached:
            logger.info(f"Cache hit: {cache_key[:20]}...")
            params["_cache_hit"] = cached
        else:
            params["_cache_key"] = cache_key

        return params

    async def after_generate(self, params: dict[str, Any], result: Any) -> None:
        """Store result in cache after generation."""
        cache_key = params.pop("_cache_key", None)
        params.pop("_cache_hit", None)

        if cache_key and result:
            content = getattr(result, "content", None)
            if content and not getattr(result, "tool_calls", None):
                django_cache.set(cache_key, content, self.cache_timeout)
                logger.debug(f"Cached response: {cache_key[:20]}...")

    def _make_key(self, params: dict) -> str:
        """Generate a deterministic cache key from params."""
        key_data = {
            "model": params.get("model_id", ""),
            "messages": params.get("messages", []),
        }
        raw = json.dumps(key_data, sort_keys=True)
        digest = hashlib.sha256(raw.encode()).hexdigest()[:16]
        return f"{self.key_prefix}{digest}"
