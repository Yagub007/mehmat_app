"""Serializers for the administrator API (dashboard + user management)."""
from __future__ import annotations

from rest_framework import serializers

from mehmat_app.models import AdminAuditLog, User


class AdminUserListSerializer(serializers.ModelSerializer):
    """Compact user row for the admin users table."""

    full_name = serializers.CharField(read_only=True)

    class Meta:
        model = User
        fields = (
            "id",
            "telegram_id",
            "username",
            "full_name",
            "photo_url",
            "is_admin",
            "is_active",
            "points",
            "current_rank",
            "streak",
            "completed_tests",
            "date_joined",
            "last_login",
        )
        read_only_fields = fields


class AdminUserDetailSerializer(AdminUserListSerializer):
    """Full user detail, including editable identity fields."""

    class Meta(AdminUserListSerializer.Meta):
        fields = AdminUserListSerializer.Meta.fields + (
            "first_name",
            "last_name",
            "language_code",
        )
        read_only_fields = (
            "id",
            "telegram_id",
            "full_name",
            "photo_url",
            "current_rank",
            "date_joined",
            "last_login",
        )


class AdminUserUpdateSerializer(serializers.ModelSerializer):
    """Validated set of admin-editable fields for a user."""

    class Meta:
        model = User
        fields = (
            "first_name",
            "last_name",
            "username",
            "language_code",
            "points",
            "streak",
            "completed_tests",
            "is_admin",
            "is_active",
        )
        extra_kwargs = {field: {"required": False} for field in fields}


class PointsAdjustSerializer(serializers.Serializer):
    """Payload for adding/removing points relative to the current total."""

    delta = serializers.IntegerField()
    reason = serializers.CharField(required=False, allow_blank=True, max_length=255)


class PointsSetSerializer(serializers.Serializer):
    """Payload for setting points to an absolute value."""

    points = serializers.IntegerField(min_value=0)


class AdminFlagSerializer(serializers.Serializer):
    """Boolean payload used by ban/unban and grant/revoke-admin actions."""

    value = serializers.BooleanField()


class AuditLogSerializer(serializers.ModelSerializer):
    """Read-only representation of an audit-log entry."""

    admin_name = serializers.SerializerMethodField()

    class Meta:
        model = AdminAuditLog
        fields = (
            "id",
            "admin",
            "admin_name",
            "action",
            "target_type",
            "target_id",
            "target_label",
            "changes",
            "ip_address",
            "created_at",
        )
        read_only_fields = fields

    def get_admin_name(self, obj: AdminAuditLog) -> str:
        if obj.admin is None:
            return "—"
        return obj.admin.username or obj.admin.full_name or f"tg:{obj.admin.telegram_id}"
