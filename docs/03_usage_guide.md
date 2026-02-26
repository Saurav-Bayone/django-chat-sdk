# Chat SDK Usage Guide

## Quick Start

### 1. Installation

Add the chat-sdk to your Django project:

```python
# settings.py
INSTALLED_APPS = [
    # ... existing apps
    'chat_sdk',
]
```

### 2. Configuration

Add the `CHAT_SDK` configuration to your settings:

```python
# settings.py
CHAT_SDK = {
    'DEFAULT_PROVIDER': 'azure_openai',
    'DEFAULT_MODEL': 'gpt-4o',
    'MAX_CONVERSATION_MESSAGES': 100,
    'MAX_TOOL_STEPS': 10,
    'ENABLE_ARTIFACTS': True,
    'ENABLE_VOTING': True,
    'PROVIDERS': {
        'azure_openai': {
            'class': 'chat_sdk.providers.AzureOpenAIProvider',
            'api_key': env('AZURE_OPENAI_API_KEY'),
            'endpoint': env('AZURE_OPENAI_ENDPOINT'),
            'api_version': '2024-06-01',
        },
        'openai': {
            'class': 'chat_sdk.providers.OpenAIProvider',
            'api_key': env('OPENAI_API_KEY'),
        },
        'anthropic': {
            'class': 'chat_sdk.providers.AnthropicProvider',
            'api_key': env('ANTHROPIC_API_KEY'),
        },
    },
    'MIDDLEWARE': [
        'chat_sdk.middleware.LoggingMiddleware',
        'chat_sdk.middleware.RateLimitMiddleware',
    ],
    'RATE_LIMIT': {
        'requests_per_minute': 30,
        'tokens_per_minute': 100000,
    },
}
```

### 3. URL Configuration

```python
# urls.py
from django.urls import path, include

urlpatterns = [
    # ... existing patterns
    path('chat-sdk/', include('chat_sdk.urls')),
]
```

### 4. WebSocket Routing

```python
# asgi.py
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
import chat_sdk.routing

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(
        URLRouter(
            chat_sdk.routing.websocket_urlpatterns
            # + other websocket routes
        )
    ),
})
```

### 5. Run Migrations

```bash
poetry run python manage.py makemigrations chat_sdk
poetry run python manage.py migrate
```

### 6. Verify Setup

```bash
poetry run python manage.py setup_chat_sdk
```

## Using the Chat Interface

Navigate to `/chat-sdk/` to access the chat interface. Features:

- **Sidebar**: Lists all your conversations. Click to switch.
- **Model Selector**: Choose the AI provider/model in the header.
- **Message Input**: Type and press Enter to send (Shift+Enter for newline).
- **Streaming**: Responses stream in real-time via WebSocket.
- **Stop Button**: Cancel a streaming response at any time.
- **Voting**: Thumbs up/down on assistant messages for feedback.

## Programmatic Usage

### ChatService (Server-Side)

```python
from chat_sdk.services import ChatService
from chat_sdk.models import Conversation

# Create service
service = ChatService()

# Stream a message (async)
async for event in service.stream_message(conversation, "Hello!"):
    print(event.type, event.data)

# Generate without streaming
message = await service.generate_message(conversation, "Hello!")
print(message.get_text_content())
```

### Direct Provider Access

```python
from chat_sdk.providers import provider_registry

# Get a provider
provider = provider_registry.get_provider("openai", "gpt-4o")

# Generate
result = await provider.generate(
    messages=[{"role": "user", "content": "Hello"}],
    temperature=0.7,
)
print(result.content)

# Stream
async for chunk in provider.stream(messages=[...]):
    if chunk["type"] == "text_delta":
        print(chunk["text"], end="")
```

### Slash-Notation Model Resolution

```python
# Use slash notation like Vercel's AI Gateway
provider = provider_registry.resolve("anthropic/claude-sonnet-4-20250514")
provider = provider_registry.resolve("openai/gpt-4o")
provider = provider_registry.resolve("azure_openai/gpt-4o-deployment")
```

### Tool Registration

```python
from chat_sdk.services import ToolRegistry, chat_tool
from pydantic import BaseModel, Field

class WeatherParams(BaseModel):
    city: str = Field(description="City name")
    unit: str = Field(default="celsius")

@chat_tool(
    name="get_weather",
    description="Get current weather for a city",
    parameters=WeatherParams,
)
async def get_weather(city: str, unit: str = "celsius"):
    # Your implementation
    return {"temperature": 72, "condition": "sunny"}

# Register globally
from chat_sdk.services.tool_registry import default_registry
default_registry.register(get_weather)

# Or per-service
service = ChatService(tool_registry=my_registry)
```

## WebSocket Protocol

### Client → Server Messages

```json
// Send a chat message
{"type": "chat_message", "text": "Hello!", "conversation_id": "uuid"}

// Create a new conversation
{"type": "create_conversation", "title": "My Chat", "model_id": "openai/gpt-4o"}

// List conversations
{"type": "list_conversations"}

// Vote on a message
{"type": "vote", "message_id": "uuid", "is_upvoted": true}

// Stop current stream
{"type": "stop"}
```

### Server → Client Messages

```json
// Stream lifecycle
{"type": "stream_start", "message_id": "uuid"}
{"type": "text_delta", "text": "Hello"}
{"type": "tool_call_start", "tool_call_id": "id", "tool_name": "weather"}
{"type": "tool_output", "tool_call_id": "id", "output": {"temp": 72}}
{"type": "stream_end", "finish_reason": "stop", "usage": {"prompt_tokens": 10}}

// Errors
{"type": "error", "message": "Something went wrong"}

// Connection
{"type": "connection_ready"}
```

## Customization

### Custom Templates

Override any template by placing your version in your project's template directory:

```
your_project/templates/chat_sdk/
├── chat_interface.html      # Override full page
└── components/
    ├── message_bubble.html  # Override message rendering
    ├── input_area.html      # Override input area
    └── sidebar.html         # Override sidebar
```

### Custom System Prompts

Set per-conversation or globally:

```python
# Per conversation
conversation = Conversation.objects.create(
    user=request.user,
    system_prompt="You are a helpful recruiter assistant.",
)

# Or in the message
service.stream_message(
    conversation,
    "Hello",
    system_prompt="You are an expert in talent acquisition.",
)
```

## Architecture Reference

See `01_architecture_plan.md` for the full architecture diagram and component details.
See `02_feature_mapping.md` for the Vercel → Django mapping.
