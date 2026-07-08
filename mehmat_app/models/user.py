"""Custom Telegram-authenticated user model."""
from __future__ import annotations

from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.utils import timezone

from mehmat_app.constants import RankTier
from mehmat_app.managers import UserManager


class User(AbstractBaseUser, PermissionsMixin):
    """A user of the Mini App, identified by their Telegram account.

    Authentication is performed via Telegram ``initData`` rather than a
    password, so passwords are unusable for regular users. Only staff created
    through the CLI have usable passwords for the Django admin.
    """

    telegram_id = models.BigIntegerField(unique=True, db_index=True)
    username = models.CharField(max_length=64, blank=True)
    first_name = models.CharField(max_length=128, blank=True)
    last_name = models.CharField(max_length=128, blank=True)
    photo_url = models.URLField(max_length=512, blank=True)
    language_code = models.CharField(max_length=16, blank=True)

    # Application-level admin flag (distinct from Django ``is_staff`` which
    # governs access to the Django admin site).
    is_admin = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    date_joined = models.DateTimeField(default=timezone.now)

    # Gamification / progress counters. These are denormalised aggregates kept
    # in sync by the scoring service inside a transaction.
    points = models.PositiveIntegerField(default=0, db_index=True)
    current_rank = models.CharField(
        max_length=16,
        choices=RankTier.choices,
        default=RankTier.NOVICE,
    )
    streak = models.PositiveIntegerField(default=0)
    completed_tests = models.PositiveIntegerField(default=0)
    last_activity_date = models.DateField(null=True, blank=True)

    objects = UserManager()

    USERNAME_FIELD = "telegram_id"
    REQUIRED_FIELDS: list[str] = []

    class Meta:
        verbose_name = "user"
        verbose_name_plural = "users"
        ordering = ("-points", "id")
        indexes = [
            models.Index(fields=["-points", "completed_tests"]),
        ]

    def __str__(self) -> str:
        return self.username or f"tg:{self.telegram_id}"

    @property
    def full_name(self) -> str:
        """Return the user's full display name."""
        return " ".join(part for part in (self.first_name, self.last_name) if part)
