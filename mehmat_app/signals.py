"""Signal handlers.

Handlers are connected from :meth:`MehmatAppConfig.ready`.
"""
from __future__ import annotations

from django.db.models.signals import post_save
from django.dispatch import receiver

from mehmat_app.models import Notification, User


@receiver(post_save, sender=User, dispatch_uid="user_welcome_notification")
def create_welcome_notification(sender, instance: User, created: bool, **kwargs) -> None:
    """Send a one-time welcome notification when a user first registers."""
    if not created:
        return
    Notification.objects.create(
        user=instance,
        title="Welcome to Mehmat! 🎓",
        message=(
            "Start preparing for the NMT Mathematics exam. Take a test to earn "
            "your first points and climb the leaderboard!"
        ),
    )
