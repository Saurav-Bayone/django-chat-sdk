"""
HTTP views for Chat SDK.

Handles the main chat interface page and HTMX partial endpoints.
WebSocket handles the actual streaming - these views handle page rendering
and HTMX-powered UI updates.
"""

from __future__ import annotations

import json

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET, require_POST

from .models import Conversation, Message, Vote
from .providers.registry import provider_registry


@login_required
def chat_interface(request, conversation_id=None):
    """Main chat interface page."""
    conversation = None
    messages = []

    if conversation_id:
        conversation = get_object_or_404(
            Conversation, id=conversation_id, user=request.user
        )
        messages = conversation.messages.order_by("created_at")

    conversations = Conversation.objects.filter(
        user=request.user, is_archived=False
    ).order_by("-updated_at")[:50]

    return render(request, "chat_sdk/chat_interface.html", {
        "conversation": conversation,
        "messages": messages,
        "conversations": conversations,
        "providers": provider_registry.list_providers(),
    })


@login_required
def htmx_sidebar(request):
    """HTMX partial: conversation sidebar list."""
    conversations = Conversation.objects.filter(
        user=request.user, is_archived=False
    ).order_by("-updated_at")[:50]

    return render(request, "chat_sdk/components/sidebar.html", {
        "conversations": conversations,
    })


@login_required
def htmx_messages(request, conversation_id):
    """HTMX partial: message list for a conversation."""
    conversation = get_object_or_404(
        Conversation, id=conversation_id, user=request.user
    )
    messages = conversation.messages.order_by("created_at")

    return render(request, "chat_sdk/components/message_list.html", {
        "conversation": conversation,
        "messages": messages,
    })


@login_required
@require_POST
def htmx_new_conversation(request):
    """HTMX: create a new conversation."""
    conversation = Conversation.objects.create(
        user=request.user,
        title="New Conversation",
        model_id=request.POST.get("model_id", ""),
    )

    # Return updated sidebar
    conversations = Conversation.objects.filter(
        user=request.user, is_archived=False
    ).order_by("-updated_at")[:50]

    response = render(request, "chat_sdk/components/sidebar.html", {
        "conversations": conversations,
        "active_conversation": conversation,
    })

    # Trigger client-side navigation
    response["HX-Trigger"] = json.dumps({
        "conversationCreated": {"id": str(conversation.id)}
    })

    return response


@login_required
@require_POST
def htmx_delete_conversation(request, conversation_id):
    """HTMX: delete a conversation."""
    Conversation.objects.filter(
        id=conversation_id, user=request.user
    ).delete()

    # Return updated sidebar
    conversations = Conversation.objects.filter(
        user=request.user, is_archived=False
    ).order_by("-updated_at")[:50]

    return render(request, "chat_sdk/components/sidebar.html", {
        "conversations": conversations,
    })


@login_required
@require_POST
def htmx_vote(request, message_id):
    """HTMX: vote on a message."""
    message = get_object_or_404(Message, id=message_id)

    # Verify user owns the conversation
    if message.conversation.user != request.user:
        return HttpResponse(status=403)

    is_upvoted = request.POST.get("is_upvoted", "true").lower() == "true"

    vote, created = Vote.objects.update_or_create(
        message=message,
        user=request.user,
        defaults={"is_upvoted": is_upvoted},
    )

    icon = "thumbs-up" if is_upvoted else "thumbs-down"
    cls = "text-success" if is_upvoted else "text-danger"

    return HttpResponse(
        f'<span class="vote-indicator {cls}" data-feather="{icon}"></span>',
        content_type="text/html",
    )


@login_required
@require_GET
def api_models(request):
    """API: list available models."""
    models = []
    for provider_name in provider_registry.list_providers():
        models.append({
            "provider": provider_name,
            "id": f"{provider_name}/default",
        })

    return JsonResponse({"models": models})


@login_required
@require_GET
def api_conversations(request):
    """API: list conversations as JSON."""
    conversations = Conversation.objects.filter(
        user=request.user, is_archived=False
    ).order_by("-updated_at")[:50]

    data = [
        {
            "id": str(c.id),
            "title": c.title,
            "model_id": c.model_id,
            "message_count": c.messages.count(),
            "created_at": c.created_at.isoformat(),
            "updated_at": c.updated_at.isoformat(),
        }
        for c in conversations
    ]

    return JsonResponse({"conversations": data})
