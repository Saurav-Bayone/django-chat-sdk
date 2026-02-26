"""Guardrails middleware - content safety filtering."""

from __future__ import annotations

import logging
import re
from typing import Any, AsyncGenerator

from .base import BaseMiddleware

logger = logging.getLogger(__name__)


class GuardrailsMiddleware(BaseMiddleware):
    """
    Content safety guardrails for LLM inputs and outputs.

    Configurable blocked patterns and content policies.
    Override check_input() and check_output() for custom rules.
    """

    name = "guardrails"

    # Default blocked patterns (override in subclass or settings)
    BLOCKED_INPUT_PATTERNS = [
        r"ignore\s+(all\s+)?previous\s+instructions",
        r"you\s+are\s+now\s+(a|an)\s+",
        r"system\s*:\s*",
    ]

    BLOCKED_OUTPUT_PATTERNS: list[str] = []

    def __init__(self):
        self._input_patterns = [
            re.compile(p, re.IGNORECASE) for p in self.BLOCKED_INPUT_PATTERNS
        ]
        self._output_patterns = [
            re.compile(p, re.IGNORECASE) for p in self.BLOCKED_OUTPUT_PATTERNS
        ]

    async def transform_params(self, params: dict[str, Any]) -> dict[str, Any]:
        """Check input messages for blocked content."""
        messages = params.get("messages", [])

        for msg in messages:
            if msg.get("role") == "user":
                content = msg.get("content", "")
                if isinstance(content, str):
                    self._check_text(content, self._input_patterns, "input")

        return params

    async def wrap_stream(
        self,
        stream: AsyncGenerator[dict, None],
        params: dict[str, Any],
    ) -> AsyncGenerator[dict, None]:
        """Filter output stream for blocked content."""
        accumulated = ""

        async for chunk in stream:
            if chunk.get("type") == "text_delta":
                text = chunk.get("text", "")
                accumulated += text

                # Check accumulated text periodically
                if len(accumulated) > 100:
                    try:
                        self._check_text(accumulated, self._output_patterns, "output")
                    except ContentBlockedError:
                        yield {"type": "text_delta", "text": "\n\n[Content filtered by safety policy]"}
                        return
                    accumulated = accumulated[-50:]  # Keep last 50 chars for context

            yield chunk

    def _check_text(self, text: str, patterns: list, direction: str):
        """Check text against blocked patterns."""
        for pattern in patterns:
            if pattern.search(text):
                logger.warning(
                    f"Guardrail blocked {direction}: matched pattern '{pattern.pattern}'"
                )
                raise ContentBlockedError(
                    f"Content blocked by {direction} guardrail"
                )


class ContentBlockedError(Exception):
    """Raised when content is blocked by guardrails."""
    pass
