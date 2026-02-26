import uuid

from django.db import models


class Message(models.Model):
    """
    A single message in a conversation. Equivalent to Vercel's Message_v2 table.

    Messages use a parts-based storage model (JSONField) matching the Vercel AI SDK's
    UIMessage format. Parts can include text, tool calls, tool results, images, etc.

    Example parts structure:
    [
        {"type": "text", "text": "What's the weather in SF?"},
        {
            "type": "tool_call",
            "tool_call_id": "call_123",
            "tool_name": "get_weather",
            "args": {"city": "San Francisco"}
        },
        {
            "type": "tool_result",
            "tool_call_id": "call_123",
            "result": {"temp": 72, "condition": "sunny"}
        }
    ]
    """

    class Role(models.TextChoices):
        USER = "user", "User"
        ASSISTANT = "assistant", "Assistant"
        SYSTEM = "system", "System"
        TOOL = "tool", "Tool"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(
        "chat_sdk.Conversation",
        on_delete=models.CASCADE,
        related_name="messages",
    )
    role = models.CharField(max_length=10, choices=Role.choices)
    parts = models.JSONField(
        default=list,
        help_text="Message parts array: text, tool_call, tool_result, image, etc.",
    )
    attachments = models.JSONField(
        default=list,
        blank=True,
        help_text="File attachments: [{name, url, content_type, size}]",
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Usage stats, finish reason, model info, etc.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["conversation", "created_at"]),
        ]

    def __str__(self):
        text = self.get_text_content()[:50]
        return f"[{self.role}] {text}"

    def get_text_content(self):
        """Extract plain text from parts."""
        texts = []
        for part in self.parts:
            if isinstance(part, dict) and part.get("type") == "text":
                texts.append(part.get("text", ""))
            elif isinstance(part, str):
                texts.append(part)
        return " ".join(texts)

    def get_tool_calls(self):
        """Extract tool call parts."""
        return [p for p in self.parts if isinstance(p, dict) and p.get("type") == "tool_call"]

    def get_tool_results(self):
        """Extract tool result parts."""
        return [p for p in self.parts if isinstance(p, dict) and p.get("type") == "tool_result"]

    @classmethod
    def create_user_message(cls, conversation, text, attachments=None):
        """Convenience factory for user messages."""
        return cls.objects.create(
            conversation=conversation,
            role=cls.Role.USER,
            parts=[{"type": "text", "text": text}],
            attachments=attachments or [],
        )

    @classmethod
    def create_assistant_message(cls, conversation, text, metadata=None):
        """Convenience factory for assistant messages."""
        return cls.objects.create(
            conversation=conversation,
            role=cls.Role.ASSISTANT,
            parts=[{"type": "text", "text": text}],
            metadata=metadata or {},
        )
