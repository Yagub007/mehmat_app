"""Achievement serializers."""
from __future__ import annotations

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from mehmat_app.models import Achievement


class AchievementSerializer(serializers.ModelSerializer):
    """An achievement definition plus the requesting user's unlock status."""

    is_unlocked = serializers.SerializerMethodField()
    unlocked_at = serializers.SerializerMethodField()

    class Meta:
        model = Achievement
        fields = (
            "id",
            "code",
            "title",
            "description",
            "icon",
            "ordering",
            "is_unlocked",
            "unlocked_at",
        )
        read_only_fields = fields

    def _user_achievement(self, obj: Achievement):
        # ``unlocked`` is prefetched to a single-element list per achievement.
        unlocked = getattr(obj, "unlocked_for_user", None)
        if unlocked:
            return unlocked[0]
        return None

    def get_is_unlocked(self, obj: Achievement) -> bool:
        return self._user_achievement(obj) is not None

    @extend_schema_field(OpenApiTypes.DATETIME)
    def get_unlocked_at(self, obj: Achievement):
        ua = self._user_achievement(obj)
        return ua.unlocked_at if ua else None
