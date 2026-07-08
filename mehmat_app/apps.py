"""App configuration for the Mehmat NMT backend."""
from django.apps import AppConfig


class MehmatAppConfig(AppConfig):
    """Primary application configuration."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "mehmat_app"
    verbose_name = "Mehmat NMT Mathematics"

    def ready(self) -> None:
        """Connect signal handlers once the app registry is populated."""
        from mehmat_app import signals  # noqa: F401  (import registers signals)
