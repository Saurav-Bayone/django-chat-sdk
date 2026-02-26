"""WebSocket URL routing for Chat SDK."""

from django.urls import re_path

from .consumers.chat_consumer import ChatSDKConsumer

websocket_urlpatterns = [
    re_path(r"ws/chat-sdk/$", ChatSDKConsumer.as_asgi()),
    re_path(r"ws/chat-sdk/(?P<conversation_id>[0-9a-f-]+)/$", ChatSDKConsumer.as_asgi()),
]
