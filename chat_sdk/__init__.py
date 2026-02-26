"""
Django Chat SDK - A Vercel AI Chat SDK equivalent for Django.

Provides a complete chat interface with:
- Multi-provider AI support (OpenAI, Anthropic, Azure OpenAI)
- WebSocket streaming with Django Channels
- Phoenix Bootstrap theme UI components
- HTMX-powered interactions
- Middleware pipeline (logging, caching, rate limiting, guardrails)
- Tool calling with Pydantic schema validation
- Message persistence with parts-based storage
"""

__version__ = "0.1.0"

default_app_config = "chat_sdk.apps.ChatSdkConfig"
