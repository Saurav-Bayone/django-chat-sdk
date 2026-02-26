# Basic Integration Example

## Integrating Chat SDK into a Django Project

### 1. Add to INSTALLED_APPS

```python
# settings/base.py
INSTALLED_APPS = [
    # ...
    'channels',
    'chat_sdk',
]
```

### 2. Configure CHAT_SDK

```python
# settings/base.py
CHAT_SDK = {
    'DEFAULT_PROVIDER': 'azure_openai',
    'DEFAULT_MODEL': 'gpt-4o',
    'MAX_TOOL_STEPS': 10,
    'PROVIDERS': {
        'azure_openai': {
            'class': 'chat_sdk.providers.AzureOpenAIProvider',
            'api_key': env('AZURE_OPENAI_API_KEY'),
            'endpoint': env('AZURE_OPENAI_ENDPOINT'),
            'api_version': '2024-06-01',
        },
    },
    'MIDDLEWARE': [
        'chat_sdk.middleware.LoggingMiddleware',
        'chat_sdk.middleware.RateLimitMiddleware',
    ],
}
```

### 3. URL Configuration

```python
# urls.py
urlpatterns = [
    path('chat/', include('chat_sdk.urls')),
]
```

### 4. ASGI WebSocket Routing

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
        )
    ),
})
```

### 5. Run Migrations

```bash
poetry run python manage.py makemigrations chat_sdk
poetry run python manage.py migrate
```

### 6. Access the Chat

Navigate to `/chat/` and start chatting!

## TalentAI-Specific Integration

For TalentAI, the existing ASGI configuration in `talent_ai_project/asgi.py`
already supports WebSocket routing. Add the chat_sdk patterns:

```python
# talent_ai_project/asgi.py
import chat_sdk.routing

# In the URLRouter
websocket_urlpatterns = [
    *intelligence.chat.routing.websocket_urlpatterns,
    *chat_sdk.routing.websocket_urlpatterns,  # Add this
    # ... other patterns
]
```

The templates automatically extend `base.html` and use the Phoenix theme
that's already configured in TalentAI.
