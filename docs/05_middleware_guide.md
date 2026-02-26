# Middleware Guide

## Overview

The Chat SDK middleware system is inspired by Vercel AI SDK's Language Model Middleware.
It provides hooks to intercept, modify, and enhance LLM interactions at three stages:

1. **Before**: Transform parameters, validate input, check rate limits
2. **During**: Wrap the streaming response, filter content
3. **After**: Log results, cache responses, track costs

## Built-in Middleware

| Middleware | Purpose | Default Config |
|-----------|---------|---------------|
| `LoggingMiddleware` | Log all LLM requests, responses, latency, tokens | Logger: `chat_sdk.llm` |
| `RateLimitMiddleware` | Token bucket rate limiting | 30 RPM, 100K TPM |
| `CacheMiddleware` | Cache identical prompts via Django cache | 1 hour TTL, Redis recommended |
| `GuardrailsMiddleware` | Block prompt injection and unsafe content | Basic patterns |

## Configuration

```python
# settings.py
CHAT_SDK = {
    'MIDDLEWARE': [
        'chat_sdk.middleware.LoggingMiddleware',
        'chat_sdk.middleware.RateLimitMiddleware',
        'chat_sdk.middleware.CacheMiddleware',
        'chat_sdk.middleware.GuardrailsMiddleware',
    ],
    'RATE_LIMIT': {
        'requests_per_minute': 30,
        'tokens_per_minute': 100000,
    },
}
```

Middleware executes in the order listed. For `after_generate`, order is reversed.

## Creating Custom Middleware

### Step 1: Subclass BaseMiddleware

```python
# my_app/middleware/cost_tracker.py

from chat_sdk.middleware.base import BaseMiddleware
from typing import Any, AsyncGenerator


class CostTrackingMiddleware(BaseMiddleware):
    """Track LLM costs per user."""

    name = "cost_tracking"

    # Approximate cost per 1K tokens (USD)
    COSTS = {
        "gpt-4o": {"input": 0.005, "output": 0.015},
        "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
        "claude-sonnet-4-20250514": {"input": 0.003, "output": 0.015},
    }

    async def after_generate(self, params: dict[str, Any], result: Any) -> None:
        """Record cost after generation."""
        model = params.get("model_id", "unknown")
        usage = getattr(result, "usage", {}) if result else {}

        costs = self.COSTS.get(model, {"input": 0.01, "output": 0.03})
        input_cost = (usage.get("prompt_tokens", 0) / 1000) * costs["input"]
        output_cost = (usage.get("completion_tokens", 0) / 1000) * costs["output"]
        total_cost = input_cost + output_cost

        # Store cost (use your own model/service)
        # await save_cost_record(user_id, model, total_cost, usage)
        print(f"Cost: ${total_cost:.6f} ({model})")

    async def wrap_stream(
        self,
        stream: AsyncGenerator[dict, None],
        params: dict[str, Any],
    ) -> AsyncGenerator[dict, None]:
        """Track streaming costs from usage events."""
        async for chunk in stream:
            if chunk.get("type") == "usage":
                usage = chunk.get("usage", {})
                model = params.get("model_id", "unknown")
                costs = self.COSTS.get(model, {"input": 0.01, "output": 0.03})
                total = (
                    (usage.get("prompt_tokens", 0) / 1000) * costs["input"]
                    + (usage.get("completion_tokens", 0) / 1000) * costs["output"]
                )
                print(f"Stream cost: ${total:.6f}")
            yield chunk
```

### Step 2: Register It

```python
# settings.py
CHAT_SDK = {
    'MIDDLEWARE': [
        'chat_sdk.middleware.LoggingMiddleware',
        'my_app.middleware.cost_tracker.CostTrackingMiddleware',
    ],
}
```

## Middleware Hooks Reference

### transform_params(params) → params

Called before any LLM request. Receives and returns the params dict.

**Common uses:**
- Inject RAG context into messages
- Force temperature or max_tokens
- Add system prompts dynamically
- Validate input

```python
async def transform_params(self, params):
    # Inject context from vector search
    query = params["messages"][-1].get("content", "")
    context = await search_vector_db(query)

    if context:
        params["messages"].insert(0, {
            "role": "system",
            "content": f"Relevant context:\n{context}",
        })

    return params
```

### before_generate(params) → None

Called after transform_params, before the provider call. Cannot modify params.

**Common uses:**
- Rate limit checks
- Log start time
- Validate user permissions

### after_generate(params, result) → None

Called after the provider returns. `result` is a `GenerateResult` for non-streaming.

**Common uses:**
- Log token usage and latency
- Cache successful responses
- Track costs
- Update rate limiter state

### wrap_stream(stream, params) → AsyncGenerator

Wraps the streaming generator. Must yield all chunks (or filter/transform them).

**Common uses:**
- Content filtering (guardrails)
- Token counting
- Progress tracking
- Stream transformation

```python
async def wrap_stream(self, stream, params):
    chunk_count = 0
    async for chunk in stream:
        chunk_count += 1

        # Filter out certain content
        if chunk.get("type") == "text_delta":
            text = chunk.get("text", "")
            if "confidential" in text.lower():
                chunk["text"] = "[REDACTED]"

        yield chunk

    print(f"Stream complete: {chunk_count} chunks")
```

## Execution Order

```
Request arrives
    │
    ▼
middleware[0].transform_params() → middleware[1].transform_params() → ...
    │
    ▼
middleware[0].before_generate() → middleware[1].before_generate() → ...
    │
    ▼
Provider.stream() or Provider.generate()
    │
    ▼ (streaming)
middleware[0].wrap_stream(middleware[1].wrap_stream(...original_stream...))
    │
    ▼ (non-streaming)
middleware[N].after_generate() → ... → middleware[0].after_generate()
```

Note: `after_generate` runs in **reverse order** (last middleware runs first).
This matches the "onion" pattern - the first middleware to start is the last to finish.

## Error Handling

Middleware errors are logged but don't break the pipeline. If one middleware fails,
the next one still executes. This ensures that a logging failure doesn't prevent
the chat from working.

To create middleware that **must** succeed (like guardrails), raise an exception:

```python
async def transform_params(self, params):
    if is_blocked_user(params.get("user_id")):
        raise PermissionError("User is blocked from chat")
    return params
```

The ChatService will catch this and send an error event to the client.
