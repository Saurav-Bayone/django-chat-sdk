# Chat SDK Development Skill

You are an expert in the Django Chat SDK, a Vercel AI Chat SDK equivalent built for Django
with Phoenix Bootstrap theme, HTMX, and Django Channels.

## When to Use This Skill

Use this skill when the user wants to:
- Add or modify chat functionality using the Chat SDK
- Create custom AI provider adapters
- Implement chat tools (function calling)
- Customize chat UI templates
- Add middleware to the chat pipeline
- Debug WebSocket/streaming issues
- Integrate the Chat SDK into a Django project

## Architecture Knowledge

The Chat SDK follows this architecture:

```
Phoenix UI → WebSocket Consumer → ChatService → Middleware Pipeline → Provider Adapter → LLM API
                                       ↓
                                  Tool Registry → Execute tools → Re-invoke LLM
                                       ↓
                                  Django ORM → Message persistence
```

### Key Files

- `chat_sdk/services/chat_service.py` - Core orchestrator (stream_message, generate_message)
- `chat_sdk/providers/base.py` - BaseProvider ABC (generate, stream)
- `chat_sdk/providers/registry.py` - Provider registry (resolve, get_provider)
- `chat_sdk/middleware/base.py` - BaseMiddleware ABC (transform_params, wrap_stream)
- `chat_sdk/middleware/pipeline.py` - Middleware chain execution
- `chat_sdk/consumers/chat_consumer.py` - WebSocket consumer
- `chat_sdk/services/tool_registry.py` - Tool registration and execution
- `chat_sdk/services/message_converter.py` - UIMessage ↔ ModelMessage conversion
- `chat_sdk/models/` - Conversation, Message, Vote, Artifact models
- `chat_sdk/templates/chat_sdk/` - Phoenix theme templates

### Message Format

Messages use a parts-based storage model (JSONField):

```python
# User message
parts = [{"type": "text", "text": "What's the weather?"}]

# Assistant message with tool call
parts = [
    {"type": "text", "text": "Let me check..."},
    {"type": "tool_call", "tool_call_id": "call_1", "tool_name": "weather", "args": {"city": "SF"}},
    {"type": "tool_result", "tool_call_id": "call_1", "result": {"temp": 72}},
    {"type": "text", "text": "It's 72°F in San Francisco."},
]
```

### Stream Event Types

```python
StreamEvent.stream_start(message_id)
StreamEvent.text_delta(text)
StreamEvent.tool_call_start(tool_call_id, tool_name)
StreamEvent.tool_output(tool_call_id, output)
StreamEvent.step_start(step)
StreamEvent.step_finish(step, finish_reason, usage)
StreamEvent.stream_end(finish_reason, usage)
StreamEvent.error(message)
```

## Common Tasks

### Creating a New Provider

1. Subclass `BaseProvider` from `chat_sdk/providers/base.py`
2. Implement `async generate()` and `async stream()` methods
3. Stream must yield dicts: `{"type": "text_delta", "text": "..."}` etc.
4. Register in settings `CHAT_SDK.PROVIDERS` or via `provider_registry.register()`

### Creating a New Tool

```python
from chat_sdk.services import chat_tool
from pydantic import BaseModel, Field

class Params(BaseModel):
    query: str = Field(description="Search query")

@chat_tool(name="search", description="Search the database", parameters=Params)
async def search_tool(query: str):
    results = await do_search(query)
    return {"results": results}

# Register
from chat_sdk.services.tool_registry import default_registry
default_registry.register(search_tool)
```

### Creating Custom Middleware

```python
from chat_sdk.middleware.base import BaseMiddleware

class MyMiddleware(BaseMiddleware):
    name = "my_middleware"

    async def transform_params(self, params):
        # Modify params before LLM call
        return params

    async def wrap_stream(self, stream, params):
        async for chunk in stream:
            # Transform chunks
            yield chunk
```

### Customizing Templates

Override templates by placing them in your project's template directory:
`templates/chat_sdk/components/message_bubble.html`

Templates use Phoenix Bootstrap theme classes and Feather icons.

## Project Conventions

- **No raw JavaScript**: Use HTMX for interactions, WebSocket for streaming
- **No Ajax**: HTMX handles all HTTP partial updates
- **Phoenix theme**: Bootstrap 5 with Phoenix classes (btn-phoenix-primary, etc.)
- **Feather icons**: `<span data-feather="icon-name"></span>`
- **SimpleBars**: Scrollable areas use `data-simplebar` attribute
- **Django ORM**: Never raw SQL, always use the ORM
- **Async**: Providers and services use async/await
- **Poetry**: Always `poetry run python manage.py ...`

## Documentation

- `docs/00_research_findings.md` - Vercel AI SDK research
- `docs/01_architecture_plan.md` - Full architecture diagram
- `docs/02_feature_mapping.md` - Vercel → Django mapping table
- `docs/03_usage_guide.md` - How to use the SDK
- `docs/04_adapter_guide.md` - Creating provider adapters
- `docs/05_middleware_guide.md` - Creating middleware
