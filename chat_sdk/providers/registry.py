"""
Provider Registry - Manage and discover AI providers.

Equivalent to Vercel AI SDK's createProviderRegistry().
Allows string-based model references like "openai/gpt-4o" or "anthropic/claude-sonnet".
"""

from __future__ import annotations

import importlib
import logging
from typing import Any

from django.conf import settings

from .base import BaseProvider

logger = logging.getLogger(__name__)


class ProviderRegistry:
    """
    Central registry for AI providers. Singleton pattern.

    Usage:
        registry = ProviderRegistry()
        registry.register("openai", OpenAIProvider(api_key="..."))

        # Get provider by name
        provider = registry.get_provider("openai", "gpt-4o")

        # Or use slash notation
        provider = registry.resolve("openai/gpt-4o")
    """

    def __init__(self):
        self._providers: dict[str, type[BaseProvider]] = {}
        self._instances: dict[str, BaseProvider] = {}
        self._configs: dict[str, dict] = {}

    def register(self, name: str, provider_class: type[BaseProvider], config: dict | None = None):
        """Register a provider class with optional config."""
        self._providers[name] = provider_class
        if config:
            self._configs[name] = config
        logger.debug(f"Registered provider: {name}")

    def register_instance(self, name: str, instance: BaseProvider):
        """Register a pre-configured provider instance."""
        self._instances[name] = instance
        logger.debug(f"Registered provider instance: {name}")

    def get_provider(self, name: str, model_id: str = "") -> BaseProvider:
        """
        Get a provider instance by name.

        Args:
            name: Provider name (e.g., "openai", "anthropic", "azure_openai")
            model_id: Model to use with the provider

        Returns:
            Configured BaseProvider instance
        """
        # Check for cached instance
        cache_key = f"{name}:{model_id}"
        if cache_key in self._instances:
            return self._instances[cache_key]

        # Check for pre-registered instance without model
        if name in self._instances:
            instance = self._instances[name]
            if model_id:
                instance.model_id = model_id
            return instance

        # Create new instance from class + config
        if name not in self._providers:
            raise KeyError(
                f"Provider '{name}' not registered. "
                f"Available: {list(self._providers.keys())}"
            )

        provider_class = self._providers[name]
        config = self._configs.get(name, {})
        instance = provider_class(model_id=model_id, **config)
        self._instances[cache_key] = instance
        return instance

    def resolve(self, model_string: str) -> BaseProvider:
        """
        Resolve a slash-notation model string to a provider.

        Args:
            model_string: "provider/model" (e.g., "openai/gpt-4o")

        Returns:
            Configured BaseProvider instance
        """
        if "/" in model_string:
            provider_name, model_id = model_string.split("/", 1)
        else:
            provider_name = self._get_default_provider_name()
            model_id = model_string

        return self.get_provider(provider_name, model_id)

    def get_default_provider(self) -> BaseProvider:
        """Get the default provider from settings."""
        config = getattr(settings, "CHAT_SDK", {})
        name = config.get("DEFAULT_PROVIDER", "azure_openai")
        model = config.get("DEFAULT_MODEL", "gpt-4o")
        return self.get_provider(name, model)

    def _get_default_provider_name(self) -> str:
        config = getattr(settings, "CHAT_SDK", {})
        return config.get("DEFAULT_PROVIDER", "azure_openai")

    def list_providers(self) -> list[str]:
        """List registered provider names."""
        return list(set(list(self._providers.keys()) + list(self._instances.keys())))

    def auto_discover(self):
        """
        Auto-discover and register providers from Django settings.

        Reads CHAT_SDK.PROVIDERS from settings and registers each provider class.
        """
        config = getattr(settings, "CHAT_SDK", {})
        providers_config = config.get("PROVIDERS", {})

        for name, prov_config in providers_config.items():
            class_path = prov_config.pop("class", None)
            if not class_path:
                logger.warning(f"Provider '{name}' missing 'class' in config, skipping")
                continue

            try:
                module_path, class_name = class_path.rsplit(".", 1)
                module = importlib.import_module(module_path)
                provider_class = getattr(module, class_name)
                self.register(name, provider_class, prov_config)
                logger.info(f"Auto-discovered provider: {name} ({class_path})")
            except (ImportError, AttributeError) as e:
                logger.error(f"Failed to load provider '{name}' ({class_path}): {e}")

        # Register built-in providers if not already configured
        self._register_builtins()

    def _register_builtins(self):
        """Register built-in providers that aren't already configured."""
        from .openai_provider import OpenAIProvider
        from .anthropic_provider import AnthropicProvider
        from .azure_openai_provider import AzureOpenAIProvider

        builtins = {
            "openai": OpenAIProvider,
            "anthropic": AnthropicProvider,
            "azure_openai": AzureOpenAIProvider,
        }

        for name, cls in builtins.items():
            if name not in self._providers:
                self._providers[name] = cls


# Global singleton
provider_registry = ProviderRegistry()
