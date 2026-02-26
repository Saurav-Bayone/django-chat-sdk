"""HTTP URL routing for Chat SDK views."""

from django.urls import path

from . import views

app_name = "chat_sdk"

urlpatterns = [
    # Main chat interface
    path("", views.chat_interface, name="chat_interface"),
    path("c/<uuid:conversation_id>/", views.chat_interface, name="chat_with_conversation"),

    # HTMX partials
    path("htmx/sidebar/", views.htmx_sidebar, name="htmx_sidebar"),
    path("htmx/conversation/<uuid:conversation_id>/messages/", views.htmx_messages, name="htmx_messages"),
    path("htmx/conversation/new/", views.htmx_new_conversation, name="htmx_new_conversation"),
    path("htmx/conversation/<uuid:conversation_id>/delete/", views.htmx_delete_conversation, name="htmx_delete_conversation"),
    path("htmx/message/<uuid:message_id>/vote/", views.htmx_vote, name="htmx_vote"),

    # API endpoints (JSON)
    path("api/models/", views.api_models, name="api_models"),
    path("api/conversations/", views.api_conversations, name="api_conversations"),
]
