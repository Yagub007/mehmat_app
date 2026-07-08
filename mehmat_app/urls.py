"""API v1 URL routing for the Mehmat backend."""
from __future__ import annotations

from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from mehmat_app.views.achievements import AchievementListView
from mehmat_app.views.auth import TelegramAuthView
from mehmat_app.views.leaderboard import LeaderboardView, MyRankView
from mehmat_app.views.materials import MaterialViewSet
from mehmat_app.views.notifications import NotificationViewSet
from mehmat_app.views.submissions import SubmissionViewSet
from mehmat_app.views.tests import TestViewSet
from mehmat_app.views.user import (
    ProfileView,
    StatisticsView,
    UserAchievementsView,
)

router = DefaultRouter()
router.register("materials", MaterialViewSet, basename="material")
router.register("tests", TestViewSet, basename="test")
router.register("submissions", SubmissionViewSet, basename="submission")
router.register("notifications", NotificationViewSet, basename="notification")

auth_patterns = [
    path("telegram/", TelegramAuthView.as_view(), name="telegram-auth"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
]

profile_patterns = [
    path("", ProfileView.as_view(), name="profile"),
    path("statistics/", StatisticsView.as_view(), name="profile-statistics"),
    path("achievements/", UserAchievementsView.as_view(), name="profile-achievements"),
]

leaderboard_patterns = [
    path("", LeaderboardView.as_view(), name="leaderboard"),
    path("me/", MyRankView.as_view(), name="leaderboard-me"),
]

schema_patterns = [
    path("", SpectacularAPIView.as_view(), name="schema"),
    path("swagger/", SpectacularSwaggerView.as_view(url_name="v1:schema"), name="swagger"),
    path("redoc/", SpectacularRedocView.as_view(url_name="v1:schema"), name="redoc"),
]

urlpatterns = [
    path("auth/", include(auth_patterns)),
    path("profile/", include(profile_patterns)),
    path("leaderboard/", include(leaderboard_patterns)),
    path("achievements/", AchievementListView.as_view(), name="achievements"),
    path("schema/", include(schema_patterns)),
    path("", include(router.urls)),
]
