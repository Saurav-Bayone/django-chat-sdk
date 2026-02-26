# Provider Adapter Guide

## Overview

The Chat SDK uses a provider adapter pattern inspired by Vercel AI SDK's LanguageModelV3
interface. Each provider adapter wraps a specific AI service (OpenAI, Anthropic, Azure, etc.)
behind a common interface.

## Built-in Providers

| Provider | Class | Python Package | Models |
|----------|-------|---------------|--------|
| OpenAI | `OpenAIProvider` | `openai` | gpt-4o, gpt-4o-mini, o1, etc. |
| Anthropic | `AnthropicProvider` | `anthropic` | claude-opus-4-5, claude-sonnet-4, etc. |
| Azure OpenAI | `AzureOpenAIProvider` | `openai` | Any Azure-deployed model |
| OpenAI-Compatible | `OpenAICompatibleProvider` | `openai` | Any OpenAI-compatible API |
| Ollama | `OllamaProvider` | `openai` | llama3.1, mistral, etc. |
| Groq | `GroqProvider` | `openai` | llama-3.1-70b, mixtral, etc. |
| Together AI | `TogetherProvider` | `openai` | Various open-source models |

## Creating a Custom Provider

### Step 1: Subclass BaseProvider

```python
# my_app/providers/my_provider.py

from chat_sdk.providers.base import BaseProvider, GenerateResult
from typing import Any, AsyncGenerator


class MyCustomProvider(BaseProvider):
    """My custom AI provider."""

    provider_name = "my_provider"

    def __init__(self, model_id: str = "my-model", **config):
        super().__init__(model_id=model_id, **config)
        self._client = None

    def _get_client(self):
        """Lazy-initialize your API client."""
        if self._client is None:
            from my_sdk import AsyncClient
            self._client = AsyncClient(
                api_key=self.config.get("api_key"),
                base_url=self.config.get("base_url"),
            )
        return self._client

    async def generate(
        self,
        messages: list[dict[str, Any]],
        model: str | None = None,
        tools: list[dict] | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        **kwargs,
    ) -> GenerateResult:
        """Non-streaming generation."""
        client = self._get_client()

        response = await client.complete(
            model=self.get_model(model),
            messages=messages,
            max_tokens=max_tokens or 4096,
        )

        return GenerateResult(
            content=response.text,
            tool_calls=[],  # Parse if your API supports tools
            finish_reason="stop",
            usage={
                "prompt_tokens": response.usage.input,
                "completion_tokens": response.usage.output,
            },
        )

    async def stream(
        self,
        messages: list[dict[str, Any]],
        model: str | None = None,
        tools: list[dict] | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        **kwargs,
    ) -> AsyncGenerator[dict, None]:
        """Streaming generation."""
        client = self._get_client()

        async for chunk in client.stream(
            model=self.get_model(model),
            messages=messages,
        ):
            if chunk.text:
                yield {"type": "text_delta", "text": chunk.text}

        # Emit usage at the end
        yield {
            "type": "usage",
            "usage": {"prompt_tokens": 0, "completion_tokens": 0},
        }
```

### Step 2: Register the Provider

**Option A: Via settings (recommended)**

```python
# settings.py
CHAT_SDK = {
    'PROVIDERS': {
        'my_provider': {
            'class': 'my_app.providers.my_provider.MyCustomProvider',
            'api_key': env('MY_PROVIDER_API_KEY'),
            'base_url': 'https://api.myprovider.com/v1',
        },
    },
}
```

**Option B: Programmatically**

```python
from chat_sdk.providers import provider_registry
from my_app.providers import MyCustomProvider

provider_registry.register(
    "my_provider",
    MyCustomProvider,
    config={"api_key": "..."},
)
```

### Step 3: Use It

```python
# Direct
provider = provider_registry.get_provider("my_provider", "my-model")
result = await provider.generate(messages=[...])

# Via slash notation
provider = provider_registry.resolve("my_provider/my-model")

# Via ChatService (set as default)
CHAT_SDK = {'DEFAULT_PROVIDER': 'my_provider', ...}
```

## Using OpenAICompatibleProvider

For any API that follows the OpenAI chat completions format, use the base class:

```python
from chat_sdk.providers.openai_compatible import OpenAICompatibleProvider


class LMStudioProvider(OpenAICompatibleProvider):
    provider_name = "lm_studio"

    def __init__(self, model_id: str = "local-model", **config):
        config.setdefault("base_url", "http://localhost:1234/v1")
        config.setdefault("api_key", "not-needed")
        super().__init__(model_id=model_id, **config)
```

No need to implement `generate()` or `stream()` - they're inherited from OpenAIProvider.

## Stream Chunk Format

All providers must yield chunks in this format:

```python
# Text content
{"type": "text_delta", "text": "Hello world"}

# Tool calls (after all args are collected)
{
    "type": "tool_call",
    "tool_call_id": "call_abc123",
    "tool_name": "get_weather",
    "args": {"city": "San Francisco"},
}

# Usage (emit once at end)
{
    "type": "usage",
    "usage": {
        "prompt_tokens": 150,
        "completion_tokens": 42,
    },
}
```

## Message Format Reference

All providers receive messages in OpenAI-compatible format:

```python
messages = [
    {"role": "system", "content": "You are helpful."},
    {"role": "user", "content": "Hello"},
    {"role": "assistant", "content": "Hi there!", "tool_calls": [...]},
    {"role": "tool", "tool_call_id": "call_123", "content": "{...}"},
]
```

Providers that use a different format (like Anthropic) must convert internally.
See `AnthropicProvider._convert_messages()` for an example.

## Provider Comparison

| Feature | OpenAI | Anthropic | Azure OpenAI | OpenAI-Compatible |
|---------|--------|-----------|-------------|-------------------|
| Streaming | Yes | Yes | Yes | Depends on API |
| Tool Calling | Yes | Yes | Yes | Depends on API |
| Multimodal | Yes | Yes | Yes | Depends on API |
| System Prompt | In messages | Separate param | In messages | In messages |
| Max Tokens | Optional | Required | Optional | Optional |
| Python Package | `openai` | `anthropic` | `openai` | `openai` |
