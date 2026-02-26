# Custom Provider Example

## Creating a Groq Provider

Groq uses an OpenAI-compatible API, so this is trivial:

```python
# my_app/providers/groq.py
from chat_sdk.providers.openai_compatible import OpenAICompatibleProvider


class GroqProvider(OpenAICompatibleProvider):
    provider_name = "groq"

    def __init__(self, model_id="llama-3.1-70b-versatile", **config):
        config.setdefault("base_url", "https://api.groq.com/openai/v1")
        super().__init__(model_id=model_id, **config)
```

Register in settings:

```python
CHAT_SDK = {
    'PROVIDERS': {
        'groq': {
            'class': 'my_app.providers.groq.GroqProvider',
            'api_key': env('GROQ_API_KEY'),
        },
    },
}
```

## Creating a Fully Custom Provider

For APIs that don't follow the OpenAI format:

```python
# my_app/providers/custom_llm.py
from chat_sdk.providers.base import BaseProvider, GenerateResult
from typing import Any, AsyncGenerator
import httpx


class CustomLLMProvider(BaseProvider):
    provider_name = "custom_llm"

    def __init__(self, model_id="default", **config):
        super().__init__(model_id=model_id, **config)
        self._client = None

    def _get_client(self):
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.config.get("base_url"),
                headers={"Authorization": f"Bearer {self.config.get('api_key')}"},
            )
        return self._client

    async def generate(self, messages, model=None, tools=None,
                       max_tokens=None, temperature=None, **kwargs):
        client = self._get_client()

        # Convert messages to your API's format
        payload = {
            "model": self.get_model(model),
            "prompt": self._messages_to_prompt(messages),
            "max_tokens": max_tokens or 4096,
        }

        response = await client.post("/generate", json=payload)
        data = response.json()

        return GenerateResult(
            content=data["text"],
            usage={
                "prompt_tokens": data.get("input_tokens", 0),
                "completion_tokens": data.get("output_tokens", 0),
            },
        )

    async def stream(self, messages, model=None, tools=None,
                     max_tokens=None, temperature=None, **kwargs):
        client = self._get_client()

        payload = {
            "model": self.get_model(model),
            "prompt": self._messages_to_prompt(messages),
            "stream": True,
        }

        async with client.stream("POST", "/generate", json=payload) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    import json
                    data = json.loads(line[6:])
                    if "text" in data:
                        yield {"type": "text_delta", "text": data["text"]}

        yield {"type": "usage", "usage": {"prompt_tokens": 0, "completion_tokens": 0}}

    def _messages_to_prompt(self, messages):
        """Convert OpenAI messages to plain text prompt."""
        parts = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if isinstance(content, str):
                parts.append(f"<{role}>\n{content}\n</{role}>")
        return "\n".join(parts)
```

## Using the TalentAI UnifiedProcessor as a Provider

Bridge to TalentAI's existing AI infrastructure:

```python
# intelligence/chat_sdk_bridge.py
from chat_sdk.providers.base import BaseProvider, GenerateResult
from intelligence.ai_models.services.unified_processor import UnifiedProcessor


class TalentAIProvider(BaseProvider):
    provider_name = "talent_ai"

    async def generate(self, messages, model=None, **kwargs):
        processor = UnifiedProcessor()
        result = await processor.process(
            messages=messages,
            model=self.get_model(model),
        )
        return GenerateResult(
            content=result.get("content", ""),
            usage=result.get("usage", {}),
        )

    async def stream(self, messages, model=None, **kwargs):
        processor = UnifiedProcessor()
        async for chunk in processor.stream(
            messages=messages,
            model=self.get_model(model),
        ):
            yield {"type": "text_delta", "text": chunk}
```
