from django.contrib import admin

from .models import Artifact, Conversation, Message, Vote


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ["title", "user", "model_id", "visibility", "message_count", "created_at"]
    list_filter = ["visibility", "is_archived", "created_at"]
    search_fields = ["title", "user__email"]
    readonly_fields = ["id", "created_at", "updated_at"]

    def message_count(self, obj):
        return obj.messages.count()


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ["short_text", "role", "conversation", "created_at"]
    list_filter = ["role", "created_at"]
    readonly_fields = ["id", "created_at"]

    def short_text(self, obj):
        return obj.get_text_content()[:80]


@admin.register(Vote)
class VoteAdmin(admin.ModelAdmin):
    list_display = ["message", "user", "is_upvoted", "created_at"]
    list_filter = ["is_upvoted"]


@admin.register(Artifact)
class ArtifactAdmin(admin.ModelAdmin):
    list_display = ["title", "kind", "user", "conversation", "created_at"]
    list_filter = ["kind", "created_at"]
    search_fields = ["title"]
    readonly_fields = ["id", "created_at", "updated_at"]
