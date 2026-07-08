"""Achievement models."""
from __future__ import annotations

from django.conf import settings
from django.db import models

from mehmat_app.constants import AchievementCode


class Achievement(models.Model):
    """A definition of an unlockable achievement.

    Rows are seeded via a data migration and keyed by a stable ``code`` so the
    achievement service can reference them without relying on primary keys.
    """

    code = models.CharField(
        max_length=50,
        choices=AchievementCode.choices,
        unique=True,
    )
    title = models.CharField(max_length=120)
    description = models.CharField(max_length=255, blank=True)
    icon = models.CharField(
        max_length=64,
        blank=True,
        help_text="Emoji or icon identifier for the frontend.",
    )
    ordering = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ("ordering", "id")

    def __str__(self) -> str:
        return self.title


class UserAchievement(models.Model):
    """Join table recording which achievements a user has unlocked."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="achievements",
    )
    achievement = models.ForeignKey(
        Achievement,
        on_delete=models.CASCADE,
        related_name="unlocked_by",
    )
    unlocked_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-unlocked_at",)
        constraints = [
            models.UniqueConstraint(
                fields=["user", "achievement"],
                name="unique_user_achievement",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user_id} -> {self.achievement_id}"
