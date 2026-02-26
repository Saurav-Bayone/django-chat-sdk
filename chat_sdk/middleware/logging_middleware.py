"""Logging middleware - records all LLM interactions."""

from __future__ import annotations

import logging
import time
from typing import Any, AsyncGenerator

from .base import BaseMiddleware

logger = logging.getLogger("chat_sdk.llm")


class LoggingMiddleware(BaseMiddleware):
    """
    Logs LLM requests and responses with timing and token usage.

    Logs at INFO level: model, message count, latency, token usage.
    Logs at DEBUG level: full message content.
    """

    name = "logging"

    async def before_generate(self, params: dict[str, Any]) -> None:
        params["_log_start_time"] = time.monotonic()
        messages = params.get("messages", [])
        model = params.get("model_id", "unknown")
        logger.info(f"LLM request: model={model}, messages={len(messages)}")
        logger.debug(f"LLM messages: {messages}")

    async def after_generate(self, params: dict[str, Any], result: Any) -> None:
        start = params.pop("_log_start_time", None)
        elapsed = (time.monotonic() - start) * 1000 if start else 0

        usage = getattr(result, "usage", {}) if result else {}
        model = params.get("model_id", "unknown")

        logger.info(
            f"LLM response: model={model}, "
            f"latency={elapsed:.0f}ms, "
            f"tokens={usage}"
        )

    async def wrap_stream(
        self,
        stream: AsyncGenerator[dict, None],
        params: dict[str, Any],
    ) -> AsyncGenerator[dict, None]:
        start = time.monotonic()
        chunk_count = 0
        total_text_length = 0

        async for chunk in stream:
            chunk_count += 1
            if chunk.get("type") == "text_delta":
                total_text_length += len(chunk.get("text", ""))
            yield chunk

        elapsed = (time.monotonic() - start) * 1000
        logger.info(
            f"LLM stream complete: "
            f"chunks={chunk_count}, "
            f"text_length={total_text_length}, "
            f"latency={elapsed:.0f}ms"
        )
