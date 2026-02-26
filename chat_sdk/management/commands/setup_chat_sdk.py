"""
Management command to set up Chat SDK in a Django project.

Usage:
    poetry run python manage.py setup_chat_sdk
"""

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Set up Chat SDK: run migrations and verify configuration"

    def handle(self, *args, **options):
        self.stdout.write("Chat SDK Setup")
        self.stdout.write("=" * 40)

        # Check INSTALLED_APPS
        from django.conf import settings
        if "chat_sdk" not in settings.INSTALLED_APPS:
            self.stdout.write(self.style.WARNING(
                "chat_sdk is not in INSTALLED_APPS. Add it to your settings."
            ))
        else:
            self.stdout.write(self.style.SUCCESS("chat_sdk found in INSTALLED_APPS"))

        # Check CHAT_SDK config
        config = getattr(settings, "CHAT_SDK", None)
        if not config:
            self.stdout.write(self.style.WARNING(
                "CHAT_SDK setting not found. Add configuration to your settings."
            ))
        else:
            self.stdout.write(self.style.SUCCESS(f"CHAT_SDK config found with keys: {list(config.keys())}"))

        # Check providers
        providers = config.get("PROVIDERS", {}) if config else {}
        if providers:
            for name, prov_config in providers.items():
                cls = prov_config.get("class", "missing")
                self.stdout.write(f"  Provider: {name} -> {cls}")
        else:
            self.stdout.write(self.style.WARNING("  No providers configured"))

        # Check channels
        try:
            import channels
            self.stdout.write(self.style.SUCCESS(f"Django Channels {channels.__version__} installed"))
        except ImportError:
            self.stdout.write(self.style.ERROR("Django Channels not installed (required for WebSocket)"))

        # Check middleware
        middleware = config.get("MIDDLEWARE", []) if config else []
        if middleware:
            self.stdout.write(f"  Middleware: {len(middleware)} configured")
            for mw in middleware:
                self.stdout.write(f"    - {mw}")
        else:
            self.stdout.write("  No middleware configured")

        self.stdout.write("")
        self.stdout.write("Next steps:")
        self.stdout.write("  1. Run: poetry run python manage.py makemigrations chat_sdk")
        self.stdout.write("  2. Run: poetry run python manage.py migrate")
        self.stdout.write("  3. Add URL patterns to your urls.py")
        self.stdout.write("  4. Add WebSocket routing to your asgi.py")
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Setup check complete!"))
