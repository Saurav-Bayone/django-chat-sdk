import uuid

from django.conf import settings
from django.db import models


class Artifact(models.Model):
    """
    Generated artifacts (documents, code, images). Equivalent to Vercel's Document table.

    Artifacts are side-products of chat conversations - code snippets, documents,
    or generated images that can be displayed in a side panel.
    """

    class Kind(models.TextChoices):
        TEXT = "text", "Text Document"
        CODE = "code", "Code"
        IMAGE = "image", "Image"
        MARKDOWN = "markdown", "Markdown"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(
        "chat_sdk.Conversation",
        on_delete=models.CASCADE,
        related_name="artifacts",
        null=True,
        blank=True,
    )
    message = models.ForeignKey(
        "chat_sdk.Message",
        on_delete=models.SET_NULL,
        related_name="artifacts",
        null=True,
        blank=True,
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="chat_sdk_artifacts",
    )
    title = models.CharField(max_length=255)
    content = models.TextField(blank=True, default="")
    kind = models.CharField(
        max_length=10,
        choices=Kind.choices,
        default=Kind.TEXT,
    )
    language = models.CharField(
        max_length=50,
        blank=True,
        default="",
        help_text="Programming language for code artifacts",
    )
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} ({self.kind})"
