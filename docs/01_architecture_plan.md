# Chat SDK Architecture Plan

**Date:** 2026-02-25
**Stack:** Django 4.2+ / Django Channels / PostgreSQL / Phoenix Theme / HTMX

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        Phoenix Theme UI                         │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────────────┐  │
│  │ Sidebar  │ │  Chat    │ │  Input   │ │   Artifacts       │  │
│  │ (convos) │ │ Messages │ │  Area    │ │   Panel           │  │
│  └──────────┘ └──────────┘ └──────────┘ └───────────────────┘  │
│         HTMX Swap          WebSocket Stream    HTMX OOB Swap   │
└───────────┬─────────────────────┬─────────────────┬─────────────┘
            │                     │                 │
┌───────────▼─────────────────────▼─────────────────▼─────────────┐
│                     Django Views + Consumers                     │
│  ┌──────────────┐  ┌──────────────────┐  ┌───────────────────┐  │
│  │ HTMX Views   │  │ ChatConsumer     │  │ SSE View          │  │
│  │ (sidebar,    │  │ (WebSocket)      │  │ (fallback)        │  │
│  │  history)    │  │                  │  │                   │  │
│  └──────────────┘  └──────────────────┘  └───────────────────┘  │
└───────────┬─────────────────────┬─────────────────┬─────────────┘
            │                     │                 │
┌───────────▼─────────────────────▼─────────────────▼─────────────┐
│                         Chat Service                             │
│  ┌──────────────┐  ┌──────────────────┐  ┌───────────────────┐  │
│  │ Conversation │  │ Message          │  │ Tool              │  │
│  │ Manager      │  │ Processor        │  │ Registry          │  │
│  └──────────────┘  └──────────────────┘  └───────────────────┘  │
└───────────┬─────────────────────┬─────────────────┬─────────────┘
            │                     │                 │
┌───────────▼─────────────────────▼─────────────────▼─────────────┐
│                     Middleware Pipeline                           │
│  ┌──────┐ ┌──────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐  │
│  │ Log  │→│ Rate │→│ Guard    │→│ Cache    │→│ Cost Track   │  │
│  └──────┘ └──────┘ └──────────┘ └──────────┘ └──────────────┘  │
└───────────┬─────────────────────────────────────────────────────┘
            │
┌───────────▼─────────────────────────────────────────────────────┐
│                     Provider Adapters                            │
│  ┌──────────┐ ┌──────────────┐ ┌───────────┐ ┌──────────────┐  │
│  │ OpenAI   │ │ Azure OpenAI │ │ Anthropic │ │ OpenAI-Compat│  │
│  │ Adapter  │ │ Adapter      │ │ Adapter   │ │ Base Adapter │  │
│  └──────────┘ └──────────────┘ └───────────┘ └──────────────┘  │
└─────────────────────────────────────────────────────────────────┘
            │
┌───────────▼─────────────────────────────────────────────────────┐
│                     Django Models (PostgreSQL)                    │
│  ┌──────────┐ ┌──────────┐ ┌──────┐ ┌──────────┐ ┌──────────┐ │
│  │Conversa- │ │ Message  │ │ Vote │ │ Artifact │ │ToolResult│ │
│  │tion      │ │          │ │      │ │          │ │          │ │
│  └──────────┘ └──────────┘ └──────┘ └──────────┘ └──────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

## Directory Structure

```
chat-sdk/
├── docs/                           # Documentation
│   ├── 00_research_findings.md
│   ├── 01_architecture_plan.md     # This file
│   ├── 02_feature_mapping.md
│   ├── 03_usage_guide.md
│   ├── 04_adapter_guide.md
│   └── 05_middleware_guide.md
├── chat_sdk/                       # Django app
│   ├── __init__.py
│   ├── apps.py
│   ├── urls.py
│   ├── routing.py                  # WebSocket routing
│   ├── views.py                    # HTTP/HTMX views
│   ├── admin.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── conversation.py         # Conversation model
│   │   ├── message.py              # Message model (parts-based)
│   │   ├── vote.py                 # Message voting
│   │   └── artifact.py             # Generated artifacts
│   ├── services/
│   │   ├── __init__.py
│   │   ├── chat_service.py         # Core chat orchestration
│   │   ├── message_converter.py    # UIMessage ↔ ModelMessage
│   │   └── tool_registry.py        # Tool definitions + execution
│   ├── consumers/
│   │   ├── __init__.py
│   │   └── chat_consumer.py        # WebSocket consumer
│   ├── providers/
│   │   ├── __init__.py
│   │   ├── base.py                 # BaseProvider ABC
│   │   ├── registry.py             # Provider registry
│   │   ├── openai_provider.py      # OpenAI adapter
│   │   ├── anthropic_provider.py   # Anthropic adapter
│   │   ├── azure_openai_provider.py # Azure OpenAI adapter
│   │   └── openai_compatible.py    # Base for compatible APIs
│   ├── middleware/
│   │   ├── __init__.py
│   │   ├── base.py                 # BaseMiddleware ABC
│   │   ├── pipeline.py             # Middleware pipeline runner
│   │   ├── logging_middleware.py
│   │   ├── rate_limit_middleware.py
│   │   ├── cache_middleware.py
│   │   └── guardrails_middleware.py
│   ├── templates/chat_sdk/
│   │   ├── base.html               # SDK base (extends project base)
│   │   ├── chat_interface.html     # Full chat page
│   │   ├── components/
│   │   │   ├── sidebar.html        # Conversation sidebar
│   │   │   ├── message_list.html   # Scrollable message area
│   │   │   ├── message_bubble.html # Single message
│   │   │   ├── input_area.html     # Message input + attachments
│   │   │   ├── chat_header.html    # Model selector + controls
│   │   │   ├── artifacts_panel.html # Side panel
│   │   │   ├── tool_result.html    # Tool call display
│   │   │   └── typing_indicator.html
│   │   └── partials/
│   │       ├── message_stream.html # Streaming message fragment
│   │       └── conversation_item.html
│   ├── templatetags/
│   │   ├── __init__.py
│   │   └── chat_sdk_tags.py        # Template filters
│   ├── management/
│   │   └── commands/
│   │       ├── __init__.py
│   │       └── setup_chat_sdk.py   # Initial setup command
│   └── tests/
│       ├── __init__.py
│       ├── test_models.py
│       ├── test_services.py
│       ├── test_providers.py
│       ├── test_consumers.py
│       └── test_middleware.py
├── examples/
│   ├── basic_integration.md
│   ├── custom_provider.md
│   └── custom_tools.md
├── skill/
│   └── chat-sdk-skill.md           # Claude Code skill
└── README.md                       # (Not created unless requested)
```

## Component Responsibilities

### Models Layer
- **Conversation**: User-scoped chat sessions with title, visibility, metadata
- **Message**: Parts-based storage (JSON) matching Vercel UIMessage format
- **Vote**: User feedback on messages (upvote/downvote)
- **Artifact**: Generated documents, code, images linked to conversations

### Service Layer
- **ChatService**: Orchestrates the full chat flow - receives message, runs middleware,
  calls provider, handles tool loops, persists results, streams to client
- **MessageConverter**: Converts between UI format (stored in DB) and model format
  (sent to LLM provider). Equivalent to `convertToModelMessages()`
- **ToolRegistry**: Register/discover tools with Pydantic schemas, execute tools,
  inject results back into conversation

### Consumer Layer
- **ChatConsumer**: AsyncJsonWebsocketConsumer handling real-time chat via WebSocket.
  Manages streaming responses, tool call UI updates, typing indicators.

### Provider Layer
- **BaseProvider**: ABC with `generate()` and `stream()` methods
- **Provider Registry**: Map string identifiers to provider instances
- Concrete adapters for OpenAI, Anthropic, Azure OpenAI
- **OpenAICompatibleProvider**: Base class for any OpenAI-compatible API

### Middleware Layer
- **Pipeline**: Runs a chain of middleware before/after LLM calls
- Built-in: logging, rate limiting, caching, guardrails, cost tracking
- Custom middleware by subclassing `BaseMiddleware`

### Template Layer
- Phoenix theme components (Bootstrap 5, SimpleBars, Feather icons)
- HTMX for non-streaming interactions (sidebar, conversation management)
- WebSocket for streaming chat messages
- OOB swaps for updating multiple UI regions simultaneously

## Integration with TalentAI

The SDK is designed as a **reusable Django app** that can be installed into any
Django project. For TalentAI specifically:

1. Add `'chat_sdk'` to `INSTALLED_APPS`
2. Include `chat_sdk.urls` in URL conf
3. Include `chat_sdk.routing` in ASGI WebSocket routes
4. Configure providers via Django settings
5. Templates extend the project's `base.html`

The SDK can also work standalone or in other Django projects with minimal configuration.

## Streaming Flow

```
User types message → WebSocket send
    ↓
ChatConsumer.receive_json()
    ↓
ChatService.process_message()
    ↓
Middleware Pipeline (before)
    ↓
Provider.stream(messages)
    ↓
For each chunk:
    → ChatConsumer.send_json({type: "text-delta", ...})
    → Client JS appends to message bubble
    ↓
On tool call:
    → ChatConsumer.send_json({type: "tool-call-start", ...})
    → Execute tool
    → ChatConsumer.send_json({type: "tool-output", ...})
    → Re-invoke provider with tool result
    ↓
On finish:
    → ChatConsumer.send_json({type: "finish", ...})
    → Middleware Pipeline (after)
    → Persist message to DB
```

## Configuration (Django Settings)

```python
CHAT_SDK = {
    'DEFAULT_PROVIDER': 'azure_openai',
    'DEFAULT_MODEL': 'gpt-4o',
    'MAX_CONVERSATION_MESSAGES': 100,
    'MAX_TOOL_STEPS': 10,
    'ENABLE_ARTIFACTS': True,
    'ENABLE_VOTING': True,
    'ENABLE_ATTACHMENTS': True,
    'FILE_UPLOAD_MAX_SIZE': 10 * 1024 * 1024,  # 10MB
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
        'chat_sdk.middleware.GuardrailsMiddleware',
    ],
    'RATE_LIMIT': {
        'requests_per_minute': 30,
        'tokens_per_minute': 100000,
    },
}
```
