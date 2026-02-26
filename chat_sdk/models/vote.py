from django.conf import settings
from django.db import models


class Vote(models.Model):
    """
    User feedback on a message. Equivalent to Vercel's Vote_v2 table.
    Composite primary key on (message, user).
    """

    message = models.ForeignKey(
        "chat_sdk.Message",
        on_delete=models.CASCADE,
        related_name="votes",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="chat_sdk_votes",
    )
    is_upvoted = models.BooleanField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("message", "user")]

    def __str__(self):
        vote = "up" if self.is_upvoted else "down"
        return f"Vote({vote}) on {self.message_id} by {self.user}"
