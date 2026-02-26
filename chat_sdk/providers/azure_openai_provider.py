"""
Azure OpenAI provider adapter.

Equivalent to Vercel AI SDK's @ai-sdk/azure package.
Uses the official openai Python SDK with Azure configuration.
"""

from __future__ import annotations

import logging
from typing import Any, AsyncGenerator

from .openai_provider import OpenAIProvider
from .base import GenerateResult

logger = logging.getLogger(__name__)


class AzureOpenAIProvider(OpenAIProvider):
    """
    Azure OpenAI provider. Extends OpenAIProvider with Azure-specific config.

    Config:
        api_key: Azure OpenAI API key
        endpoint: Azure OpenAI endpoint URL
        api_version: API version (default: 2024-06-01)
        deployment_name: Optional deployment name override
    """

    provider_name = "azure_openai"

    def __init__(self, model_id: str = "gpt-4o", **config):
        super().__init__(model_id=model_id, **config)

    def _get_client(self):
        if self._async_client is None:
            try:
                from openai import AsyncAzureOpenAI
            except ImportError:
                raise ImportError("openai package required: pip install openai")

            self._async_client = AsyncAzureOpenAI(
                api_key=self.config.get("api_key"),
                azure_endpoint=self.config.get("endpoint", ""),
                api_version=self.config.get("api_version", "2024-06-01"),
            )
        return self._async_client

    def get_model(self, override: str | None = None) -> str:
        """Azure uses deployment names instead of model IDs."""
        return override or self.config.get("deployment_name", self.model_id)
