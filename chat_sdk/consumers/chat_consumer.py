"""
WebSocket consumer for real-time chat streaming.

Equivalent to Vercel's SSE streaming endpoint + useChat client interaction.
Uses Django Channels' AsyncJsonWebsocketConsumer.

WebSocket message protocol:
    Client → Server:
        {"type": "chat_message", "text": "Hello", "conversation_id": "uuid", ...}
        {"type": "create_conversation", "title": "...", "model_id": "..."}
        {"type": "list_conversations"}
        {"type": "vote", "message_id": "uuid", "is_upvoted": true}
        {"type": "stop"}

    Server → Client:
        {"type": "stream_start", "message_id": "uuid"}
        {"type": "text_delta", "text": "..."}
        {"type": "tool_call_start", "tool_call_id": "...", "tool_name": "..."}
        {"type": "tool_output", "tool_call_id": "...", "output": {...}}
        {"type": "stream_end", "finish_reason": "stop", "usage": {...}}
        {"type": "error", "message": "..."}
        {"type": "conversations", "data": [...]}
        {"type": "connection_ready"}
"""

from __future__ import annotations

import logging
import uuid

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from ..models import Conversation, Message, Vote
from ..services.chat_service import ChatService

logger = logging.getLogger(__name__)


class ChatSDKConsumer(AsyncJsonWebsocketConsumer):
    """
    WebSocket consumer for the Chat SDK.

    Handles real-time streaming chat, conversation management,
    and message voting over WebSocket.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._chat_service = None
        self._current_stream = None
        self._stop_requested = False

    @property
    def chat_service(self) -> ChatService:
        if self._chat_service is None:
            self._chat_service = ChatService()
        return self._chat_service

    async def connect(self):
        """Accept WebSocket connection and authenticate."""
        self.user = self.scope.get("user")

        if not self.user or not self.user.is_authenticated:
            await self.close(code=4001)
            return

        # Optional conversation_id from URL
        self.conversation_id = self.scope["url_route"]["kwargs"].get("conversation_id")

        await self.accept()
        await self.send_json({"type": "connection_ready"})
        logger.info(f"Chat SDK WebSocket connected: user={self.user.id}")

    async def disconnect(self, close_code):
        """Handle WebSocket disconnect."""
        self._stop_requested = True
        logger.info(f"Chat SDK WebSocket disconnected: user={self.user.id}, code={close_code}")

    async def receive_json(self, content):
        """Route incoming messages to handlers."""
        msg_type = content.get("type", "")

        handlers = {
            "chat_message": self.handle_chat_message,
            "create_conversation": self.handle_create_conversation,
            "list_conversations": self.handle_list_conversations,
            "delete_conversation": self.handle_delete_conversation,
            "vote": self.handle_vote,
            "stop": self.handle_stop,
        }

        handler = handlers.get(msg_type)
        if handler:
            try:
                await handler(content)
            except Exception as e:
                logger.exception(f"Error handling {msg_type}")
                await self.send_json({"type": "error", "message": str(e)})
        else:
            await self.send_json({"type": "error", "message": f"Unknown type: {msg_type}"})

    async def handle_chat_message(self, content):
        """Process a chat message and stream the response."""
        conversation_id = content.get("conversation_id") or self.conversation_id
        text = content.get("text", "").strip()
        attachments = content.get("attachments", [])
        model_id = content.get("model_id")
        system_prompt = content.get("system_prompt")

        if not text:
            await self.send_json({"type": "error", "message": "Empty message"})
            return

        # Get or create conversation
        conversation = await self._get_or_create_conversation(
            conversation_id, model_id
        )

        self._stop_requested = False

        # Stream response
        async for event in self.chat_service.stream_message(
            conversation=conversation,
            user_text=text,
            attachments=attachments,
            model_id=model_id,
            system_prompt=system_prompt,
        ):
            if self._stop_requested:
                await self.send_json({"type": "stream_end", "finish_reason": "cancelled"})
                break

            await self.send_json(event.to_dict())

        # Auto-generate title for new conversations
        if not conversation_id:
            await self.chat_service.generate_title(conversation)
            await self.send_json({
                "type": "conversation_updated",
                "conversation_id": str(conversation.id),
                "title": conversation.title,
            })

    async def handle_create_conversation(self, content):
        """Create a new conversation."""
        conversation = await self._create_conversation(
            title=content.get("title", "New Conversation"),
            model_id=content.get("model_id", ""),
            system_prompt=content.get("system_prompt", ""),
        )

        await self.send_json({
            "type": "conversation_created",
            "conversation": {
                "id": str(conversation.id),
                "title": conversation.title,
                "model_id": conversation.model_id,
                "created_at": conversation.created_at.isoformat(),
            },
        })

    async def handle_list_conversations(self, content):
        """List user's conversations."""
        conversations = await self._list_conversations()
        await self.send_json({
            "type": "conversations",
            "data": conversations,
        })

    async def handle_delete_conversation(self, content):
        """Delete a conversation."""
        conversation_id = content.get("conversation_id")
        if conversation_id:
            await self._delete_conversation(conversation_id)
            await self.send_json({
                "type": "conversation_deleted",
                "conversation_id": conversation_id,
            })

    async def handle_vote(self, content):
        """Record a vote on a message."""
        message_id = content.get("message_id")
        is_upvoted = content.get("is_upvoted", True)

        if message_id:
            await self._save_vote(message_id, is_upvoted)
            await self.send_json({
                "type": "vote_recorded",
                "message_id": message_id,
                "is_upvoted": is_upvoted,
            })

    async def handle_stop(self, content):
        """Stop the current stream."""
        self._stop_requested = True

    # --- Database helpers ---

    @database_sync_to_async
    def _get_or_create_conversation(self, conversation_id, model_id=None):
        if conversation_id:
            try:
                return Conversation.objects.get(
                    id=conversation_id, user=self.user
                )
            except Conversation.DoesNotExist:
                pass

        return Conversation.objects.create(
            user=self.user,
            model_id=model_id or "",
        )

    @database_sync_to_async
    def _create_conversation(self, title, model_id, system_prompt):
        return Conversation.objects.create(
            user=self.user,
            title=title,
            model_id=model_id,
            system_prompt=system_prompt,
        )

    @database_sync_to_async
    def _list_conversations(self):
        conversations = Conversation.objects.filter(
            user=self.user, is_archived=False
        ).order_by("-updated_at")[:50]

        return [
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

    @database_sync_to_async
    def _delete_conversation(self, conversation_id):
        Conversation.objects.filter(
            id=conversation_id, user=self.user
        ).delete()

    @database_sync_to_async
    def _save_vote(self, message_id, is_upvoted):
        Vote.objects.update_or_create(
            message_id=message_id,
            user=self.user,
            defaults={"is_upvoted": is_upvoted},
        )
