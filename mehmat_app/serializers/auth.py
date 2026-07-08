"""Serializers for Telegram authentication."""
from __future__ import annotations

from rest_framework import serializers

from mehmat_app.serializers.user import UserSerializer


class TelegramAuthSerializer(serializers.Serializer):
    """Accepts the raw ``initData`` string from the Telegram Mini App."""

    init_data = serializers.CharField(
        write_only=True,
        trim_whitespace=False,
        help_text="Raw Telegram WebApp initData query string.",
    )


class TokenPairSerializer(serializers.Serializer):
    """Response payload containing JWT tokens and the authenticated user."""

    access = serializers.CharField(read_only=True)
    refresh = serializers.CharField(read_only=True)
    user = UserSerializer(read_only=True)
    created = serializers.BooleanField(read_only=True)
