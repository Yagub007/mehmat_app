"""Scoped throttles for sensitive endpoints."""
from __future__ import annotations

from rest_framework.throttling import AnonRateThrottle, UserRateThrottle


class TelegramAuthThrottle(AnonRateThrottle):
    """Limit anonymous Telegram authentication attempts."""

    scope = "telegram_auth"


class TestSubmitThrottle(UserRateThrottle):
    """Limit how frequently a user may submit tests (per authenticated user)."""

    scope = "test_submit"
