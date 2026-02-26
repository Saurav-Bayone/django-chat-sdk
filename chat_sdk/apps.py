from django.apps import AppConfig


class ChatSdkConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "chat_sdk"
    verbose_name = "Chat SDK"

    def ready(self):
        from .providers.registry import provider_registry
        provider_registry.auto_discover()
