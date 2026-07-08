"""Custom model managers."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.contrib.auth.base_user import BaseUserManager

if TYPE_CHECKING:  # pragma: no cover - typing only
    from mehmat_app.models.user import User


class UserManager(BaseUserManager):
    """Manager for the Telegram-authenticated custom user model."""

    use_in_migrations = True

    def create_user(
        self,
        telegram_id: int,
        password: str | None = None,
        **extra_fields: Any,
    ) -> "User":
        """Create and persist a regular user identified by ``telegram_id``."""
        if telegram_id is None:
            raise ValueError("The telegram_id must be set.")
        user = self.model(telegram_id=telegram_id, **extra_fields)
        # Telegram users authenticate via initData, not a password. A password
        # is only meaningful for staff created via the CLI.
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(
        self,
        telegram_id: int,
        password: str | None = None,
        **extra_fields: Any,
    ) -> "User":
        """Create and persist a superuser with full admin access."""
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_admin", True)
        extra_fields.setdefault("is_active", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(telegram_id, password=password, **extra_fields)
