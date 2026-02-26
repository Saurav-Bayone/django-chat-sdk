"""Rate limiting middleware - token bucket algorithm."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from django.conf import settings

from .base import BaseMiddleware

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseMiddleware):
    """
    Rate limiting using a token bucket algorithm.

    Configurable via CHAT_SDK.RATE_LIMIT settings:
        requests_per_minute: Max requests per minute (default: 30)
        tokens_per_minute: Max tokens per minute (default: 100000)
    """

    name = "rate_limit"

    def __init__(self):
        config = getattr(settings, "CHAT_SDK", {}).get("RATE_LIMIT", {})
        self._rpm = config.get("requests_per_minute", 30)
        self._tpm = config.get("tokens_per_minute", 100000)
        self._request_tokens = float(self._rpm)
        self._token_tokens = float(self._tpm)
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def before_generate(self, params: dict[str, Any]) -> None:
        async with self._lock:
            self._refill()

            if self._request_tokens < 1:
                wait_time = (1 - self._request_tokens) / (self._rpm / 60)
                logger.warning(f"Rate limit: waiting {wait_time:.1f}s for request token")
                await asyncio.sleep(wait_time)
                self._refill()

            self._request_tokens -= 1

    async def after_generate(self, params: dict[str, Any], result: Any) -> None:
        usage = getattr(result, "usage", {}) if result else {}
        total_tokens = usage.get("prompt_tokens", 0) + usage.get("completion_tokens", 0)

        async with self._lock:
            self._token_tokens -= total_tokens
            if self._token_tokens < 0:
                logger.warning(
                    f"Rate limit: token budget exhausted "
                    f"({self._token_tokens:.0f} remaining)"
                )

    def _refill(self):
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._last_refill = now

        # Refill request tokens
        self._request_tokens = min(
            float(self._rpm),
            self._request_tokens + elapsed * (self._rpm / 60),
        )

        # Refill token budget
        self._token_tokens = min(
            float(self._tpm),
            self._token_tokens + elapsed * (self._tpm / 60),
        )
