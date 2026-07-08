"""Notification serializers."""
from __future__ import annotations

from rest_framework import serializers

from mehmat_app.models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    """Read representation of a notification."""

    class Meta:
        model = Notification
        fields = ("id", "title", "message", "is_read", "created_at")
        read_only_fields = fields
