# Django Chat SDK

A **Vercel AI Chat SDK equivalent** built for Django — with Phoenix Bootstrap theme, HTMX, and Django Channels.

Drop-in reusable Django app that gives you a full-featured AI chat interface with multi-provider support, streaming, tool calling, and middleware pipeline.

## Features

- **Multi-Provider** — OpenAI, Anthropic, Azure OpenAI, + any OpenAI-compatible API (Groq, Ollama, Together AI, etc.)
- **Real-Time Streaming** — WebSocket via Django Channels with typed stream events
- **Tool Calling** — Pydantic-validated function calling with automatic multi-step agent loops
- **Middleware Pipeline** — Composable middleware for logging, rate limiting, caching, guardrails, cost tracking
- **Phoenix Theme UI** — Bootstrap 5 chat interface with HTMX interactions (no React/JS frameworks)
- **Parts-Based Messages** — JSONField storage matching Vercel's UIMessage format (text, tool calls, images, etc.)
- **Conversation Management** — Sidebar, history, voting, artifacts panel
- **Provider Registry** — Slash-notation model resolution (`"openai/gpt-4o"`, `"anthropic/claude-sonnet-4-20250514"`)

## Architecture

```
Phoenix UI (HTMX + WebSocket)
    │
    ├─ ChatSDKConsumer (WebSocket) ── real-time streaming
    └─ HTMX Views (HTTP) ─────────── sidebar, voting, conversations
         │
         ▼
    ChatService (orchestrator)
         │
         ▼
    Middleware Pipeline
    [Logging → RateLimit → Cache → Guardrails]
         │
         ▼
    Provider Adapter (OpenAI / Anthropic / Azure / Custom)
         │
         ├─ Tool Registry ── execute tools ── re-invoke LLM
         │
         ▼
    Django ORM (PostgreSQL)
```

## Quick Start

### 1. Install

Copy `chat_sdk/` into your Django project, or add the repo as a submodule.

```bash
# As submodule
git submodule add https://github.com/Saurav-Bayone/django-chat-sdk.git chat-sdk
```

### 2. Configure

```python
# settings.py
INSTALLED_APPS = [
    # ...
    'channels',
    'chat_sdk',
]

CHAT_SDK = {
    'DEFAULT_PROVIDER': 'openai',
    'DEFAULT_MODEL': 'gpt-4o',
    'MAX_TOOL_STEPS': 10,
    'PROVIDERS': {
        'openai': {
            'class': 'chat_sdk.providers.OpenAIProvider',
            'api_key': os.environ.get('OPENAI_API_KEY'),
        },
    },
    'MIDDLEWARE': [
        'chat_sdk.middleware.LoggingMiddleware',
        'chat_sdk.middleware.RateLimitMiddleware',
    ],
}
```

### 3. URLs + WebSocket Routing

```python
# urls.py
urlpatterns = [
    path('chat/', include('chat_sdk.urls')),
]

# asgi.py
import chat_sdk.routing

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(
        URLRouter(chat_sdk.routing.websocket_urlpatterns)
    ),
})
```

### 4. Migrate & Go

```bash
python manage.py makemigrations chat_sdk
python manage.py migrate
python manage.py setup_chat_sdk  # verify configuration
```

Navigate to `/chat/` and start chatting.

## Providers

| Provider | Class | Config |
|----------|-------|--------|
| OpenAI | `OpenAIProvider` | `api_key` |
| Anthropic | `AnthropicProvider` | `api_key` |
| Azure OpenAI | `AzureOpenAIProvider` | `api_key`, `endpoint`, `api_version` |
| Groq | `GroqProvider` | `api_key` |
| Ollama | `OllamaProvider` | (local, no key needed) |
| Together AI | `TogetherProvider` | `api_key` |
| Any OpenAI-compatible | `OpenAICompatibleProvider` | `api_key`, `base_url` |

### Custom Provider

```python
from chat_sdk.providers.base import BaseProvider, GenerateResult

class MyProvider(BaseProvider):
    provider_name = "my_provider"

    async def generate(self, messages, **kwargs) -> GenerateResult:
        # Call your API
        ...

    async def stream(self, messages, **kwargs):
        yield {"type": "text_delta", "text": "Hello"}
```

See [docs/04_adapter_guide.md](docs/04_adapter_guide.md) for the full guide.

## Tool Calling

```python
from chat_sdk.services import chat_tool
from pydantic import BaseModel, Field

class SearchParams(BaseModel):
    query: str = Field(description="Search query")

@chat_tool(name="search", description="Search the database", parameters=SearchParams)
async def search(query: str):
    results = await do_search(query)
    return {"results": results}

# Register globally
from chat_sdk.services.tool_registry import default_registry
default_registry.register(search)
```

The SDK handles the multi-step loop automatically: LLM calls tool → execute → inject result → re-invoke LLM.

See [examples/custom_tools.md](examples/custom_tools.md) for more examples.

## Middleware

Built-in middleware:

| Middleware | Purpose |
|-----------|---------|
| `LoggingMiddleware` | Log requests, responses, latency, token usage |
| `RateLimitMiddleware` | Token bucket rate limiting (RPM + TPM) |
| `CacheMiddleware` | Cache identical prompts via Django cache |
| `GuardrailsMiddleware` | Block prompt injection and unsafe content |

### Custom Middleware

```python
from chat_sdk.middleware.base import BaseMiddleware

class CostTracker(BaseMiddleware):
    name = "cost_tracker"

    async def transform_params(self, params):
        # Modify params before LLM call
        return params

    async def wrap_stream(self, stream, params):
        async for chunk in stream:
            yield chunk  # transform, filter, or log chunks
```

See [docs/05_middleware_guide.md](docs/05_middleware_guide.md) for the full guide.

## WebSocket Protocol

**Client → Server:**
```json
{"type": "chat_message", "text": "Hello!", "conversation_id": "uuid"}
{"type": "stop"}
```

**Server → Client (streaming):**
```json
{"type": "stream_start", "message_id": "uuid"}
{"type": "text_delta", "text": "Hello"}
{"type": "tool_call_start", "tool_call_id": "id", "tool_name": "search"}
{"type": "tool_output", "tool_call_id": "id", "output": {"results": [...]}}
{"type": "stream_end", "finish_reason": "stop", "usage": {"prompt_tokens": 10}}
```

## Project Structure

```
chat_sdk/
├── models/          # Conversation, Message, Vote, Artifact
├── services/        # ChatService, MessageConverter, ToolRegistry
├── providers/       # BaseProvider, OpenAI, Anthropic, Azure, OpenAI-compatible
├── middleware/       # Pipeline, Logging, RateLimit, Cache, Guardrails
├── consumers/       # WebSocket ChatSDKConsumer
├── templates/       # Phoenix theme (chat interface, sidebar, messages, input)
├── templatetags/    # Template filters (message_text, role_class, etc.)
├── views.py         # HTMX views (sidebar, voting, conversations)
├── urls.py          # HTTP routing
├── routing.py       # WebSocket routing
└── admin.py         # Django admin registration
```

## Documentation

| Doc | Content |
|-----|---------|
| [Research Findings](docs/00_research_findings.md) | Vercel AI SDK analysis and design decisions |
| [Architecture Plan](docs/01_architecture_plan.md) | Full architecture diagram, components, streaming flow |
| [Feature Mapping](docs/02_feature_mapping.md) | Vercel concept → Django equivalent (40+ mappings) |
| [Usage Guide](docs/03_usage_guide.md) | Installation, configuration, programmatic usage |
| [Adapter Guide](docs/04_adapter_guide.md) | Creating custom provider adapters |
| [Middleware Guide](docs/05_middleware_guide.md) | Creating custom middleware |

## Requirements

- Python 3.10+
- Django 4.2+
- Django Channels 4.x
- PostgreSQL (recommended)
- Redis (for Channels layer + caching)

**Python packages:** `openai`, `anthropic` (install only the providers you use), `pydantic`

## Inspired By

- [Vercel AI SDK](https://github.com/vercel/ai) — Core architecture, provider pattern, middleware system
- [Vercel AI Chatbot](https://github.com/vercel/chatbot) — UI components, database schema, streaming protocol

## License

MIT
