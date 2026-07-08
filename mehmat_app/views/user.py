"""User profile, statistics and achievement views."""
from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import generics
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from mehmat_app.selectors.statistics import user_statistics
from mehmat_app.serializers.achievements import AchievementSerializer
from mehmat_app.serializers.user import (
    StatisticsSerializer,
    UserSerializer,
    UserUpdateSerializer,
)
from mehmat_app.views.achievements import AchievementListView


@extend_schema(tags=["profile"])
class ProfileView(generics.RetrieveUpdateAPIView):
    """Retrieve (GET) or partially update (PATCH) the current user's profile."""

    http_method_names = ["get", "patch", "head", "options"]

    def get_object(self):
        return self.request.user

    def get_serializer_class(self):
        if self.request.method == "PATCH":
            return UserUpdateSerializer
        return UserSerializer

    def update(self, request, *args, **kwargs):
        # Always run as a partial update; the profile is edited field-by-field.
        kwargs["partial"] = True
        super().update(request, *args, **kwargs)
        # Return the full, canonical profile representation after updating.
        return Response(UserSerializer(self.get_object()).data)


@extend_schema(tags=["profile"], responses={200: StatisticsSerializer})
class StatisticsView(APIView):
    """Return aggregate performance statistics for the current user."""

    def get(self, request: Request) -> Response:
        data = user_statistics(request.user)
        return Response(StatisticsSerializer(data).data)


@extend_schema(tags=["profile"], responses={200: AchievementSerializer(many=True)})
class UserAchievementsView(AchievementListView):
    """List all achievements with the current user's unlock status.

    Shares its logic with :class:`AchievementListView`; exposed under the
    profile namespace for frontend convenience.
    """
