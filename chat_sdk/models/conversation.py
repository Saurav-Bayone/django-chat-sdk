import uuid

from django.conf import settings
from django.db import models


class Conversation(models.Model):
    """
    A chat conversation session. Equivalent to Vercel's Chat table.

    Each conversation belongs to a user and contains an ordered list of messages.
    Supports visibility controls (private/public) and metadata storage.
    """

    class Visibility(models.TextChoices):
        PRIVATE = "private", "Private"
        PUBLIC = "public", "Public"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="chat_sdk_conversations",
    )
    title = models.CharField(max_length=255, default="New Conversation")
    visibility = models.CharField(
        max_length=10,
        choices=Visibility.choices,
        default=Visibility.PRIVATE,
    )
    system_prompt = models.TextField(blank=True, default="")
    model_id = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text="Provider/model identifier, e.g. 'azure_openai/gpt-4o'",
    )
    metadata = models.JSONField(default=dict, blank=True)
    is_archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["user", "-updated_at"]),
            models.Index(fields=["user", "is_archived"]),
        ]

    def __str__(self):
        return f"{self.title} ({self.user})"

    @property
    def message_count(self):
        return self.messages.count()

    def get_messages_for_model(self):
        """Return messages in the format needed for LLM API calls."""
        from ..services.message_converter import MessageConverter
        messages = self.messages.order_by("created_at")
        return MessageConverter.to_model_messages(messages)
