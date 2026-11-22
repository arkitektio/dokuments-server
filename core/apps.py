from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"

    def ready(self) -> None:
        # Connects the file signals that feed the `files` subscription: without this import
        # they were never registered, and the subscription never heard of a file.
        from core import signals  # noqa: F401
