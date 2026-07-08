"""Leaderboard views."""
from __future__ import annotations

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from mehmat_app.pagination import LeaderboardPagination
from mehmat_app.selectors.leaderboard import (
    DEFAULT_ORDERING,
    LEADERBOARD_ORDERINGS,
    leaderboard_queryset,
    rank_for_user,
)
from mehmat_app.serializers.leaderboard import (
    LeaderboardEntrySerializer,
    MyRankSerializer,
)


@extend_schema(
    tags=["leaderboard"],
    parameters=[
        OpenApiParameter(
            name="ordering",
            enum=sorted(LEADERBOARD_ORDERINGS.keys()),
            description="Ranking criterion (default: points).",
        )
    ],
)
class LeaderboardView(generics.ListAPIView):
    """Paginated ranking of users by points, completion time or tests done."""

    serializer_class = LeaderboardEntrySerializer
    pagination_class = LeaderboardPagination

    def get_queryset(self):
        ordering = self.request.query_params.get("ordering", DEFAULT_ORDERING)
        return leaderboard_queryset(ordering)


@extend_schema(tags=["leaderboard"], responses={200: MyRankSerializer})
class MyRankView(APIView):
    """Return the authenticated user's current leaderboard position."""

    def get(self, request: Request) -> Response:
        user = request.user
        data = {
            "position": rank_for_user(user),
            "points": user.points,
            "current_rank": user.current_rank,
            "completed_tests": user.completed_tests,
        }
        return Response(MyRankSerializer(data).data)
