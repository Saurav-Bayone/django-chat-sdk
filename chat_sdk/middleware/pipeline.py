"""
Middleware pipeline - chains multiple middleware together.

Executes middleware in order for transform_params and before_generate,
in reverse order for after_generate, and nested for wrap_stream.
"""

from __future__ import annotations

import importlib
import logging
from typing import Any, AsyncGenerator

from django.conf import settings

from .base import BaseMiddleware

logger = logging.getLogger(__name__)


class MiddlewarePipeline:
    """
    Manages and executes a chain of middleware.

    Middleware execution order:
    - transform_params: first → last
    - before_generate: first → last
    - wrap_stream: first wraps last (outermost → innermost)
    - after_generate: last → first (reverse)
    """

    def __init__(self, middleware: list[BaseMiddleware] | None = None):
        self._middleware = middleware or []

    def add(self, mw: BaseMiddleware):
        """Add middleware to the pipeline."""
        self._middleware.append(mw)
        return self

    async def transform_params(self, params: dict[str, Any]) -> dict[str, Any]:
        """Run transform_params through all middleware (first → last)."""
        for mw in self._middleware:
            try:
                params = await mw.transform_params(params)
            except Exception as e:
                logger.error(f"Middleware {mw.name} transform_params failed: {e}")
        return params

    async def before_generate(self, params: dict[str, Any]) -> None:
        """Run before_generate through all middleware (first → last)."""
        for mw in self._middleware:
            try:
                await mw.before_generate(params)
            except Exception as e:
                logger.error(f"Middleware {mw.name} before_generate failed: {e}")

    async def after_generate(self, params: dict[str, Any], result: Any) -> None:
        """Run after_generate through all middleware (last → first)."""
        for mw in reversed(self._middleware):
            try:
                await mw.after_generate(params, result)
            except Exception as e:
                logger.error(f"Middleware {mw.name} after_generate failed: {e}")

    async def wrap_stream(
        self,
        stream: AsyncGenerator[dict, None],
        params: dict[str, Any],
    ) -> AsyncGenerator[dict, None]:
        """
        Wrap stream through all middleware (outermost → innermost).

        Each middleware wraps the previous one, creating a nested pipeline.
        """
        wrapped = stream
        for mw in reversed(self._middleware):
            try:
                wrapped = mw.wrap_stream(wrapped, params)
            except Exception as e:
                logger.error(f"Middleware {mw.name} wrap_stream failed: {e}")

        async for chunk in wrapped:
            yield chunk

    @classmethod
    def from_settings(cls) -> "MiddlewarePipeline":
        """Create a pipeline from Django CHAT_SDK settings."""
        config = getattr(settings, "CHAT_SDK", {})
        middleware_paths = config.get("MIDDLEWARE", [])

        middleware_list = []
        for path in middleware_paths:
            try:
                module_path, class_name = path.rsplit(".", 1)
                module = importlib.import_module(module_path)
                mw_class = getattr(module, class_name)
                middleware_list.append(mw_class())
                logger.debug(f"Loaded middleware: {path}")
            except (ImportError, AttributeError) as e:
                logger.error(f"Failed to load middleware '{path}': {e}")

        return cls(middleware_list)
