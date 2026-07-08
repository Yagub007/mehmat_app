"""Achievement catalogue views."""
from __future__ import annotations

from django.db.models import Prefetch
from drf_spectacular.utils import extend_schema
from rest_framework import generics

from mehmat_app.models import Achievement, UserAchievement
from mehmat_app.serializers.achievements import AchievementSerializer


@extend_schema(tags=["achievements"])
class AchievementListView(generics.ListAPIView):
    """List every achievement with the current user's unlock status."""

    serializer_class = AchievementSerializer
    pagination_class = None

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Achievement.objects.none()
        user_unlocked = UserAchievement.objects.filter(user=self.request.user)
        return Achievement.objects.prefetch_related(
            Prefetch(
                "unlocked_by",
                queryset=user_unlocked,
                to_attr="unlocked_for_user",
            )
        )
