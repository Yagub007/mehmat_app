"""Administrator API: dashboard, user management and audit log.

Every endpoint here requires application-admin rights and every mutating action
is recorded to :class:`~mehmat_app.models.AdminAuditLog` via the admin service.
"""
from __future__ import annotations

import django_filters
from django.db.models import QuerySet
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema
from rest_framework import filters, mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.generics import ListAPIView
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from mehmat_app.models import AdminAuditLog, Submission, User
from mehmat_app.permissions import IsAdminUser
from mehmat_app.selectors.admin import dashboard_overview
from mehmat_app.selectors.statistics import user_statistics
from mehmat_app.serializers.achievements import AchievementSerializer
from mehmat_app.serializers.admin import (
    AdminFlagSerializer,
    AdminUserDetailSerializer,
    AdminUserListSerializer,
    AdminUserUpdateSerializer,
    AuditLogSerializer,
    PointsAdjustSerializer,
    PointsSetSerializer,
)
from mehmat_app.serializers.submissions import SubmissionListSerializer
from mehmat_app.services import admin as admin_service


def _client_ip(request: Request) -> str | None:
    """Best-effort extraction of the client IP, honouring a proxy header."""
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


@extend_schema(tags=["admin"])
class AdminDashboardView(APIView):
    """Aggregate headline stats, charts and recent activity for the dashboard."""

    permission_classes = [IsAdminUser]

    def get(self, request: Request) -> Response:
        days = min(max(int(request.query_params.get("days", 14)), 7), 60)
        return Response(dashboard_overview(days=days))


class AdminUserFilterSet(django_filters.FilterSet):
    """Filter users by admin/active flags and rank tier."""

    is_admin = django_filters.BooleanFilter(field_name="is_admin")
    is_active = django_filters.BooleanFilter(field_name="is_active")
    current_rank = django_filters.CharFilter(field_name="current_rank")

    class Meta:
        model = User
        fields = ["is_admin", "is_active", "current_rank"]


@extend_schema(tags=["admin"])
class AdminUserViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Manage users: list/search/filter, view, edit, moderation actions, delete."""

    permission_classes = [IsAdminUser]
    queryset = User.objects.all().order_by("-date_joined")
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = AdminUserFilterSet
    search_fields = ["username", "first_name", "last_name", "telegram_id"]
    ordering_fields = ["date_joined", "points", "completed_tests", "streak", "last_login"]

    def get_serializer_class(self):
        if self.action == "retrieve":
            return AdminUserDetailSerializer
        return AdminUserListSerializer

    # -- Editing -----------------------------------------------------------
    @action(detail=True, methods=["patch"])
    def edit(self, request: Request, pk: str | None = None) -> Response:
        """Partially update a user's editable fields."""
        target = self.get_object()
        serializer = AdminUserUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        admin_service.apply_edits(
            request.user, target, serializer.validated_data, ip=_client_ip(request)
        )
        return Response(AdminUserDetailSerializer(target).data)

    # -- Points ------------------------------------------------------------
    @action(detail=True, methods=["post"], url_path="points/adjust")
    def adjust_points(self, request: Request, pk: str | None = None) -> Response:
        target = self.get_object()
        serializer = PointsAdjustSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        admin_service.adjust_points(
            request.user, target, serializer.validated_data["delta"], ip=_client_ip(request)
        )
        return Response(AdminUserDetailSerializer(target).data)

    @action(detail=True, methods=["post"], url_path="points/set")
    def set_points(self, request: Request, pk: str | None = None) -> Response:
        target = self.get_object()
        serializer = PointsSetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        admin_service.set_points(
            request.user, target, serializer.validated_data["points"], ip=_client_ip(request)
        )
        return Response(AdminUserDetailSerializer(target).data)

    # -- Resets ------------------------------------------------------------
    @action(detail=True, methods=["post"], url_path="reset/(?P<field>points|streak|completed_tests)")
    def reset(self, request: Request, pk: str | None = None, field: str = "") -> Response:
        target = self.get_object()
        admin_service.reset_field(request.user, target, field, ip=_client_ip(request))
        return Response(AdminUserDetailSerializer(target).data)

    # -- Moderation --------------------------------------------------------
    @action(detail=True, methods=["post"])
    def ban(self, request: Request, pk: str | None = None) -> Response:
        target = self.get_object()
        admin_service.set_active(request.user, target, False, ip=_client_ip(request))
        return Response(AdminUserDetailSerializer(target).data)

    @action(detail=True, methods=["post"])
    def unban(self, request: Request, pk: str | None = None) -> Response:
        target = self.get_object()
        admin_service.set_active(request.user, target, True, ip=_client_ip(request))
        return Response(AdminUserDetailSerializer(target).data)

    @action(detail=True, methods=["post"], url_path="admin")
    def set_admin(self, request: Request, pk: str | None = None) -> Response:
        """Grant or revoke admin rights (`{"value": true|false}`)."""
        target = self.get_object()
        serializer = AdminFlagSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        admin_service.set_admin(
            request.user, target, serializer.validated_data["value"], ip=_client_ip(request)
        )
        return Response(AdminUserDetailSerializer(target).data)

    # -- History -----------------------------------------------------------
    @action(detail=True, methods=["get"])
    def statistics(self, request: Request, pk: str | None = None) -> Response:
        return Response(user_statistics(self.get_object()))

    @action(detail=True, methods=["get"])
    def submissions(self, request: Request, pk: str | None = None) -> Response:
        target = self.get_object()
        qs = (
            Submission.objects.filter(user=target)
            .select_related("test")
            .order_by("-submitted_at")[:50]
        )
        return Response(SubmissionListSerializer(qs, many=True).data)

    @action(detail=True, methods=["get"])
    def achievements(self, request: Request, pk: str | None = None) -> Response:
        target = self.get_object()
        unlocked = target.achievements.select_related("achievement").order_by(
            "-unlocked_at"
        )
        data = [
            {
                **AchievementSerializer(ua.achievement).data,
                "unlocked_at": ua.unlocked_at,
            }
            for ua in unlocked
        ]
        return Response(data)

    # -- Delete (audit-logged) --------------------------------------------
    def destroy(self, request: Request, *args, **kwargs) -> Response:
        target = self.get_object()
        admin_service.delete_user(request.user, target, ip=_client_ip(request))
        return Response(status=status.HTTP_204_NO_CONTENT)


class AuditLogFilterSet(django_filters.FilterSet):
    """Filter the audit log by admin, action and target."""

    admin = django_filters.NumberFilter(field_name="admin_id")
    action = django_filters.CharFilter(field_name="action", lookup_expr="icontains")
    target_type = django_filters.CharFilter(field_name="target_type")
    target_id = django_filters.CharFilter(field_name="target_id")

    class Meta:
        model = AdminAuditLog
        fields = ["admin", "action", "target_type", "target_id"]


@extend_schema(tags=["admin"])
class AuditLogListView(ListAPIView):
    """Read-only, paginated view over the administrator audit trail."""

    permission_classes = [IsAdminUser]
    serializer_class = AuditLogSerializer
    queryset = AdminAuditLog.objects.select_related("admin").all()
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_class = AuditLogFilterSet
    search_fields = ["action", "target_label"]

    def get_queryset(self) -> QuerySet[AdminAuditLog]:
        return super().get_queryset()
